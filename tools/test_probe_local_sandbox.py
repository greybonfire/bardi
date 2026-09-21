"""Probe contract regressions, not a mocked claim of Docker acceptance."""

import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tools import probe_local_sandbox as probe
from tools.sandbox_probe_fixture import pack


class ProbeTests(unittest.TestCase):
    def test_environment_ignores_ambient_authoring_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {
                    "POSTGRES_DB": "authoring",
                    "DOCKER_HOST": "tcp://remote",
                    "DJANGO_SETTINGS_MODULE": "bardi.settings.test",
                    "PGOPTIONS": "bad",
                },
            ):
                env = probe.clean_environment(Path(temporary))
            self.assertEqual(env["DJANGO_SETTINGS_MODULE"], "bardi.settings.development")
            self.assertEqual(env["PROCEDURE_VERSION_REVIEW_MODE"], "solo")
            self.assertNotIn("POSTGRES_DB", env)
            self.assertNotIn("DOCKER_HOST", env)
            self.assertNotIn("PGOPTIONS", env)
            Path(env["HOME"], "writable").touch()
            self.assertEqual(probe.DOCKER, ["docker", "--host", "unix:///var/run/docker.sock"])

    def test_ports_distinct_and_bindable_on_loopback(self) -> None:
        ports = probe.free_ports(4)
        self.assertEqual(len(set(ports)), 4)
        with contextlib.ExitStack() as stack:
            for port in ports:
                listener = stack.enter_context(socket.socket())
                listener.bind(("127.0.0.1", port))

    def test_failed_command_never_exposes_output(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "^probe command failed$"):
            probe.command(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('private sql'); sys.stderr.write('password'); sys.exit(2)",
                ],
                env=os.environ.copy(),
            )

    def test_failure_report_is_data_free(self) -> None:
        output = io.StringIO()
        try:
            raise subprocess.CalledProcessError(
                2, ["password"], output=b"private sql", stderr=b"secret"
            )
        except Exception as error:
            with contextlib.redirect_stderr(output):
                probe.report_failure(error)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "probe_failed")
        for secret in ("password", "private sql", "secret"):
            self.assertNotIn(secret, output.getvalue())

    def test_fixture_has_independent_identities_and_all_four_risks(self) -> None:
        ordinary, blocked = pack(), pack("risk-")
        self.assertFalse(any(ordinary["risks"].values()))
        self.assertEqual(
            set(blocked["risks"]),
            {"legal", "military", "custody_guardianship", "contested_identity"},
        )
        self.assertTrue(all(blocked["risks"].values()))
        for data in (ordinary, blocked):
            self.assertEqual(
                data["version"]["procedure"], data["catalog"]["procedures"][0]["semantic_id"]
            )
            self.assertEqual(
                data["service_setup"]["service"], data["catalog"]["services"][0]["semantic_id"]
            )
            self.assertEqual(
                data["version"]["applicability"],
                data["service_setup"]["candidates"][0]["selection_predicate"],
            )
        self.assertNotEqual(ordinary["version"]["semantic_id"], blocked["version"]["semantic_id"])
        ordinary["version"]["text_en"] = "changed"
        self.assertEqual(pack()["version"]["text_en"], "Research")

    def test_login_uses_csrf_and_namespace_over_real_http(self) -> None:
        identity = "a" * 32
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Set-Cookie", f"bardi_sandbox_{identity}_csrf=token; Path=/")
                self.end_headers()
                self.wfile.write(
                    b'LOCAL QUESTIONNAIRE SANDBOX <input name="csrfmiddlewaretoken" value="token">'
                )

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                observed.append(body)
                accepted = b"csrfmiddlewaretoken=token" in body
                self.send_response(200 if accepted else 403)
                if accepted:
                    self.send_header(
                        "Set-Cookie", f"bardi_sandbox_{identity}_session=value; Path=/"
                    )
                self.end_headers()
                self.wfile.write(b"LOCAL QUESTIONNAIRE SANDBOX Log out")

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                probe.login(f"http://127.0.0.1:{server.server_port}/admin/", identity)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(len(observed), 2)
        self.assertNotIn(b"csrfmiddlewaretoken", observed[0])
        self.assertIn(b"csrfmiddlewaretoken=token", observed[1])

    def test_cleanup_checks_all_identities_before_any_removal(self) -> None:
        project = "bardi-sandbox-" + "a" * 32
        config = probe.ROOT / "compose.sandbox.yaml"
        calls = []

        def command(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            calls.append(args)
            if "inspect" in args:
                # Even a label-filter match must be rejected if its identity differs.
                payload = [
                    {
                        "Config": {
                            "Labels": {
                                "com.docker.compose.project": "unrelated-authoring",
                                "com.docker.compose.project.config_files": str(config),
                                "com.docker.compose.project.working_dir": str(probe.ROOT),
                                "com.docker.compose.service": "postgres",
                            }
                        }
                    }
                ]
                return subprocess.CompletedProcess(args, 0, json.dumps(payload).encode())
            return subprocess.CompletedProcess(args, 0, b"container-id\n")

        with patch.object(probe, "command", side_effect=command):
            with self.assertRaises(AssertionError):
                probe.cleanup_project(project, config, {"postgres"}, {})
        self.assertFalse(any("rm" in args for args in calls))
        self.assertTrue(
            all(
                f"label=com.docker.compose.project={project}" in args
                for args in calls
                if "inspect" not in args
            )
        )

    def test_cleanup_rejects_non_disposable_project_without_commands(self) -> None:
        with patch.object(probe, "command") as command:
            with self.assertRaises(AssertionError):
                probe.cleanup_project("bardi", probe.ROOT / "compose.yaml", {"postgres"}, {})
            command.assert_not_called()

    def test_tcp_readiness_retries_authenticated_read_only_endpoint(self) -> None:
        from unittest.mock import Mock

        import psycopg

        connection = Mock()
        env = {
            "POSTGRES_DB": "bardi_probe",
            "POSTGRES_USER": "probe",
            "POSTGRES_PASSWORD": "private",
            "POSTGRES_PORT": "15432",
        }
        with (
            patch.object(
                psycopg, "connect", side_effect=[psycopg.OperationalError(), connection]
            ) as connect,
            patch.object(probe.time, "sleep"),
        ):
            probe.wait_for_tcp(env)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(connect.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(connect.call_args.kwargs["options"], "-c default_transaction_read_only=on")
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 2)
        connection.close.assert_called_once()

    def test_cli_requires_explicit_disposable_consent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = probe.clean_environment(Path(temporary))
            # No inherited PYTHONPATH: direct execution must bootstrap itself.
            env.pop("PYTHONPATH")
            cli = [sys.executable, str(probe.ROOT / "tools/probe_local_sandbox.py")]
            for arguments, code in (([], 2), (["--help"], 0)):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        cli + arguments, capture_output=True, env=env, cwd=temporary
                    )
                    self.assertEqual(result.returncode, code, result.stderr.decode())
                    self.assertIn(b"--disposable", result.stderr if code else result.stdout)
            result = subprocess.run(
                [sys.executable, "-c", "import tools.probe_local_sandbox"],
                capture_output=True,
                env=env,
                cwd=probe.ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
