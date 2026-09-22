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
from tools.sandbox_probe_fixture import assert_renewal_target, pack


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

    def test_browser_environment_is_minimized_and_uses_private_home(self) -> None:
        with patch.dict(
            os.environ,
            {
                "POSTGRES_PASSWORD": "secret",
                "NODE_OPTIONS": "--require=hostile",
                "PLAYWRIGHT_JSON_OUTPUT_FILE": "/tmp/leak",
                "HOME": "/ambient",
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": "/usr/bin/chromium",
                "PLAYWRIGHT_BROWSERS_PATH": "/cache/browsers",
            },
            clear=True,
        ):
            env = probe.browser_environment("http://127.0.0.1:1234", Path("/private"))
        self.assertEqual(env["HOME"], "/private")
        self.assertEqual(env["PLAYWRIGHT_BROWSERS_PATH"], "/cache/browsers")
        self.assertEqual(env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"], "/usr/bin/chromium")
        self.assertEqual(env["BARDI_REAL_E2E_DISPOSABLE"], "1")
        for key in ("POSTGRES_PASSWORD", "NODE_OPTIONS", "PLAYWRIGHT_JSON_OUTPUT_FILE"):
            self.assertNotIn(key, env)
        for origin in (
            "https://example.com",
            "http://127.0.0.1",
            "http://u@localhost:12",
            "http://localhost:12/path",
            "http://localhost:12?secret",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                probe.browser_environment(origin, Path("/private"))

    @staticmethod
    def browser_report() -> dict[str, object]:
        return {
            "suite": "real-national-id",
            "passed": 3,
            "failed": 0,
            "errors": 0,
            "failingIds": [],
            "status": "passed",
        }

    def test_browser_requires_three_actual_passes(self) -> None:
        report = self.browser_report()
        probe.assert_browser_success(json.dumps(report).encode())
        for field, value in (
            ("passed", 0),
            ("passed", 2),
            ("failed", 1),
            ("errors", 1),
        ):
            broken = self.browser_report()
            broken[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                probe.assert_browser_success(json.dumps(broken).encode())
        for payload in (
            b"private invalid output",
            b"{}",
            json.dumps({**report, "errors": ["private"]}).encode(),
            json.dumps({**report, "suites": []}).encode(),
            json.dumps(report).replace('"passed"', '"skipped"').encode(),
        ):
            with self.assertRaisesRegex(RuntimeError, "^browser acceptance incomplete$"):
                probe.assert_browser_success(payload)

    def test_browser_uses_local_cli_and_captures_report(self) -> None:
        result = subprocess.CompletedProcess([], 0, json.dumps(self.browser_report()).encode())
        with patch.object(probe, "command", return_value=result) as command:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                probe.run_browser("http://127.0.0.1:1234", Path("/private"))
        argv = command.call_args.args[0]
        self.assertEqual(
            argv[:2], ["node", str(probe.ROOT / "frontend/node_modules/@playwright/test/cli.js")]
        )
        self.assertFalse(any(arg.startswith("--reporter") for arg in argv))
        self.assertIn("--retries=0", argv)
        self.assertEqual(argv[-1], "/private/browser-output")
        self.assertEqual(json.loads(output.getvalue())["passed"], 3)

    def test_browser_failure_still_checks_database_and_propagates(self) -> None:
        with (
            patch.object(probe, "command") as command,
            patch.object(probe, "snapshot", return_value="same") as snapshot,
            patch.object(probe, "run_browser", side_effect=RuntimeError("browser failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "browser failed"):
                probe.browser_phase(["fixture"], {}, "database", "origin", Path("/private"))
        command.assert_called_once_with(["fixture", "prepare-renewal", "database"], env={})
        self.assertEqual(snapshot.call_count, 2)

    def test_browser_database_mutation_fails(self) -> None:
        with (
            patch.object(probe, "command"),
            patch.object(probe, "snapshot", side_effect=["before", "after"]),
            patch.object(probe, "run_browser"),
        ):
            with self.assertRaisesRegex(AssertionError, "browser database mutation"):
                probe.browser_phase(["fixture"], {}, "database", "origin", Path("/private"))

    def test_renewal_fixture_rejects_source_and_mismatched_targets(self) -> None:
        expected = "bardi_restore_" + "a" * 32
        database = {"NAME": expected, "USER": "sandbox", "HOST": "127.0.0.1"}
        assert_renewal_target(database, expected)
        for field, value in (
            ("NAME", "bardi_probe"),
            ("NAME", "bardi_restore_" + "b" * 32),
            ("USER", "authoring"),
            ("HOST", "remote"),
        ):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                assert_renewal_target({**database, field: value}, expected)
        for name in (None, "bardi_probe", "bardi_restore_bad"):
            with self.assertRaises(AssertionError):
                assert_renewal_target(database, name)

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
            for arguments, code in (([], 2), (["--with-browser"], 2), (["--help"], 0)):
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
