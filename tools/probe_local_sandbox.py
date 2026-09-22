"""Opt-in real Docker/HTTP sandbox acceptance. Only random owned disposable projects.

Run with backend's uv Python: uv run python ../tools/probe_local_sandbox.py --disposable
No authoring .env, test settings, source bind mounts, or shared Docker cleanup.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast, overload

# Direct script execution starts with tools/, not the repository root, on sys.path.
# The Task1 helper then installs backend/ before the core imports below.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.probe_local_database import ROOT, report_failure, snapshot

# isort: split
# The helper above must install backend/ before these imports.
from core.local_database import LocalPostgres
from core.local_database import backup as archive_backup

DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]


def row_fingerprint(env: dict[str, str], database: str) -> str:
    """Restart persistence ignores PostgreSQL sequence WAL reservation gaps."""
    import psycopg
    from psycopg import sql

    digest = hashlib.sha256()
    with psycopg.connect(
        dbname=database,
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=env["POSTGRES_PORT"],
        options="-c default_transaction_read_only=on",
    ) as conn:
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"
        ).fetchall()
        for (table,) in tables:
            rows = conn.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY 1").format(
                    sql.Identifier(table)
                )
            ).fetchall()
            digest.update(repr((table, rows)).encode())
    return digest.hexdigest()


def clean_environment(home: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "DOCKER_CONFIG": str(home / "docker"),
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(ROOT / "backend"),
        "DJANGO_SETTINGS_MODULE": "bardi.settings.development",
        "PROCEDURE_VERSION_REVIEW_MODE": "solo",
        "DJANGO_SECRET_KEY": uuid.uuid4().hex,
    }


def browser_environment(origin: str, private: Path) -> dict[str, str]:
    """Allow browser runtime locations, never ambient application settings or secrets."""
    parsed = urllib.parse.urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not parsed.port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid disposable browser origin")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(private),
        "LANG": "C.UTF-8",
        "CI": "1",
        "BARDI_REAL_E2E_ORIGIN": origin,
        "BARDI_REAL_E2E_DISPOSABLE": "1",
        "PLAYWRIGHT_BROWSERS_PATH": str(
            Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "ms-playwright"
        ),
    }
    for key in ("PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def assert_browser_success(payload: bytes) -> None:
    """Require the private reporter's complete summary, not merely exit status zero."""
    try:
        report = json.loads(payload)
        assert report == {
            "suite": "real-national-id",
            "passed": 3,
            "failed": 0,
            "errors": 0,
            "failingIds": [],
            "status": "passed",
        }
    except ValueError, KeyError, TypeError, AssertionError:
        raise RuntimeError("browser acceptance incomplete") from None


def run_browser(origin: str, private: Path) -> None:
    env = browser_environment(origin, private)
    result = command(
        [
            "node",
            str(ROOT / "frontend/node_modules/@playwright/test/cli.js"),
            "test",
            "--config",
            str(ROOT / "frontend/playwright.real.config.ts"),
            "--workers=1",
            "--retries=0",
            "--output",
            str(private / "browser-output"),
        ],
        env=env,
    )
    assert_browser_success(result.stdout)
    print(json.dumps({"stage": "browser_tests_passed", "passed": 3}), flush=True)


def browser_phase(
    fixture: list[str], target: dict[str, str], database: str, origin: str, private: Path
) -> None:
    command(fixture + ["prepare-renewal", database], env=target)
    before = snapshot(target, database)
    try:
        run_browser(origin, private)
    finally:
        assert snapshot(target, database) == before, "browser database mutation"


def free_ports(count: int) -> list[int]:
    with contextlib.ExitStack() as stack:
        sockets = [stack.enter_context(socket.socket()) for _ in range(count)]
        for listener in sockets:
            listener.bind(("127.0.0.1", 0))
        return [listener.getsockname()[1] for listener in sockets]


def command(
    args: list[str], *, env: dict[str, str], check: bool = True, input: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=ROOT, env=env, input=input, capture_output=True, timeout=600)
    if check and result.returncode:
        # Do not surface private SQL, credentials, command output, or stderr.
        raise RuntimeError("probe command failed")
    return result


class SourcePostgres(LocalPostgres):
    """Task1 archive operations on the probe's exact checked synthetic source."""

    def __init__(self, compose: list[str], project: str, config: Path, env: dict[str, str]) -> None:
        self.env = env
        self.docker = DOCKER
        self.container = (
            command(compose + ["ps", "-q", "postgres"], env=env).stdout.decode().strip()
        )
        assert re.fullmatch(r"[a-f0-9]{12,64}", self.container)
        info = json.loads(command(DOCKER + ["inspect", self.container], env=env).stdout)[0]
        labels = info["Config"]["Labels"]
        assert labels["com.docker.compose.project"] == project
        assert labels["com.docker.compose.service"] == "postgres"
        assert labels["com.docker.compose.project.config_files"] == str(config)
        assert labels["com.docker.compose.project.working_dir"] == str(ROOT)
        assert info["State"]["Running"]
        self.source = env["POSTGRES_DB"]
        self.user = env["POSTGRES_USER"]

    def exec(
        self,
        args: list[str],
        *,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | int = subprocess.PIPE,
    ) -> bytes:
        result = subprocess.run(
            self.docker + ["exec", "-i", "-e", "PGCONNECT_TIMEOUT=10", self.container] + args,
            env=self.env,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=True,
        )
        return result.stdout if isinstance(result.stdout, bytes) else b""


def assert_owned_empty(project: str, env: dict[str, str]) -> None:
    for kind, args in (
        ("container", ["ps", "-aq"]),
        ("volume", ["volume", "ls", "-q"]),
        ("network", ["network", "ls", "-q"]),
    ):
        result = command(
            DOCKER + args + ["--filter", f"label=com.docker.compose.project={project}"], env=env
        )
        if result.stdout.strip():
            raise RuntimeError(f"owned {kind} resources remain or preexist")


def cleanup_project(project: str, config: Path, services: set[str], env: dict[str, str]) -> None:
    """Verify every selected resource before deleting exact owned IDs, not a prefix."""
    assert re.fullmatch(r"bardi-sandbox-(?:source-probe-)?[a-f0-9]{32}", project)
    selected = {}
    for kind, listing in (
        ("container", ["ps", "-aq"]),
        ("volume", ["volume", "ls", "-q"]),
        ("network", ["network", "ls", "-q"]),
    ):
        names = (
            command(
                DOCKER + listing + ["--filter", f"label=com.docker.compose.project={project}"],
                env=env,
            )
            .stdout.decode()
            .split()
        )
        selected[kind] = names
        if not names:
            continue
        records = json.loads(command(DOCKER + [kind, "inspect", *names], env=env).stdout)
        for record in records:
            labels = record["Config"]["Labels"] if kind == "container" else record["Labels"]
            assert labels["com.docker.compose.project"] == project
            if kind == "container":
                assert labels["com.docker.compose.project.config_files"] == str(config)
                assert labels["com.docker.compose.project.working_dir"] == str(ROOT)
                assert labels["com.docker.compose.service"] in services
            else:
                suffix = "postgres_data" if kind == "volume" else "default"
                assert record["Name"] == f"{project}_{suffix}"
                assert labels[f"com.docker.compose.{kind}"] == suffix
    for kind in ("container", "volume", "network"):
        if selected[kind]:
            flags = ["-f"] if kind == "container" else []
            command(DOCKER + [kind, "rm", *flags, *selected[kind]], env=env)
    assert_owned_empty(project, env)


def http(
    opener: urllib.request.OpenerDirector,
    url: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with opener.open(request, timeout=20) as response:
        return response.status, response.read().decode()


def wait_for_tcp(env: dict[str, str]) -> None:
    """initdb may take over 30s here; require authenticated final TCP readiness."""
    import psycopg

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            connection = psycopg.connect(
                dbname=env["POSTGRES_DB"],
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                host="127.0.0.1",
                port=env["POSTGRES_PORT"],
                connect_timeout=2,
                options="-c default_transaction_read_only=on",
            )
        except psycopg.OperationalError:
            time.sleep(0.25)
        else:
            connection.close()
            return
    raise TimeoutError("synthetic TCP readiness") from None


def wait_http(url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            http(urllib.request.build_opener(), url)
            return
        except OSError, urllib.error.URLError:
            time.sleep(0.25)
    raise TimeoutError("HTTP readiness")


def login(admin: str, sandbox_id: str) -> None:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    url = admin + "login/?next=/admin/"
    _, body = http(opener, url)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)
    assert token and "LOCAL QUESTIONNAIRE SANDBOX" in body
    values = {"username": "sandbox-probe", "password": "synthetic-probe-only", "next": "/admin/"}
    try:
        http(opener, url, urllib.parse.urlencode(values).encode(), {"Referer": url})
    except urllib.error.HTTPError as error:
        try:
            assert error.code == 403
        finally:
            error.close()
    else:
        raise AssertionError("CSRF-free login accepted")
    values["csrfmiddlewaretoken"] = token.group(1)
    _, body = http(opener, url, urllib.parse.urlencode(values).encode(), {"Referer": url})
    assert "LOCAL QUESTIONNAIRE SANDBOX" in body and "Log out" in body
    names = {cookie.name for cookie in jar}
    assert {f"bardi_sandbox_{sandbox_id}_csrf", f"bardi_sandbox_{sandbox_id}_session"} <= names
    assert not {"csrftoken", "sessionid"} & names


def planning(frontend: str, facts: dict[str, bool], service: str = "research") -> dict[str, Any]:
    _, body = http(
        urllib.request.build_opener(),
        frontend + "/v1/planning",
        json.dumps(
            {
                "service_id": service,
                "facts": facts,
                "locale": "en",
                "evaluation_context": {"evaluation_date": "2026-01-01"},
            }
        ).encode(),
        {"Content-Type": "application/json", "Origin": frontend},
    )
    return cast(dict[str, Any], json.loads(body))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable", action="store_true", required=True)
    parser.add_argument("--with-browser", action="store_true")
    options = parser.parse_args()
    started = time.monotonic()
    stages = []

    def stage(name: str) -> None:
        stages.append(name)
        print(
            json.dumps({"stage": name, "elapsed_seconds": round(time.monotonic() - started, 2)}),
            flush=True,
        )

    with tempfile.TemporaryDirectory(prefix="bardi-sandbox-probe-") as temporary:
        private = Path(temporary)
        env = clean_environment(private)
        project = "bardi-sandbox-source-probe-" + uuid.uuid4().hex
        source_port, frontend_port, backend_port, postgres_port = free_ports(4)
        env.update(
            COMPOSE_PROJECT_NAME=project,
            COMPOSE_ENV_FILES="/dev/null",
            COMPOSE_DISABLE_ENV_FILE="1",
            POSTGRES_DB="bardi_probe",
            POSTGRES_USER="bardi_probe",
            POSTGRES_PASSWORD=uuid.uuid4().hex,
            POSTGRES_HOST="127.0.0.1",
            POSTGRES_PORT=str(source_port),
        )
        override = private / "source.yaml"
        override.write_text(
            "services:\n  postgres:\n    image: postgres:17\n    environment:\n"
            "      POSTGRES_DB: ${POSTGRES_DB}\n      POSTGRES_USER: ${POSTGRES_USER}\n"
            "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}\n"
            '    ports: ["127.0.0.1:${POSTGRES_PORT}:5432"]\n'
            '    volumes: ["postgres_data:/var/lib/postgresql/data"]\n'
            "    logging:\n      driver: none\nvolumes:\n  postgres_data:\n"
        )
        compose = DOCKER + [
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            "/dev/null",
            "-p",
            project,
            "-f",
            str(override),
        ]
        state_path = private / "sandbox"
        cli = [
            sys.executable,
            str(ROOT / "tools/local_sandbox.py"),
            "--state-directory",
            str(state_path),
        ]
        fixture = [sys.executable, str(ROOT / "tools/sandbox_probe_fixture.py")]
        owned_source = False
        before = None

        @overload
        def sandbox(*args: str, check: Literal[True] = True) -> dict[str, Any]: ...

        @overload
        def sandbox(*args: str, check: Literal[False]) -> None: ...

        def sandbox(*args: str, check: bool = True) -> dict[str, Any] | None:
            result = command(cli + list(args), env=env, check=check)
            if not check:
                assert result.returncode != 0
                return None
            return cast(dict[str, Any], json.loads(result.stdout))

        def manifest() -> dict[str, Any]:
            return cast(dict[str, Any], json.loads((state_path / "manifest.json").read_text()))

        def target_env() -> dict[str, str]:
            m = manifest()
            return {
                **env,
                "POSTGRES_DB": m["active"],
                "POSTGRES_USER": "sandbox",
                "POSTGRES_PASSWORD": m["password"],
                "POSTGRES_PORT": str(m["ports"]["postgres"]),
            }

        def backup(directory: Path, database: str | None = None) -> str:
            source = SourcePostgres(compose, project, override, env)
            if database is not None:
                assert database == "bardi_probe_incompatible"
                source.source = database
            return cast(str, archive_backup(source, directory)["path"])

        try:
            stage("synthetic_source")
            assert_owned_empty(project, env)
            owned_source = True
            command(compose + ["up", "-d", "--wait", "postgres"], env=env)
            wait_for_tcp(env)
            command(fixture + ["seed"], env=env)
            before = snapshot(env, env["POSTGRES_DB"])
            archive = backup(private / "archives")
            stage("initial_restore_build")
            result = sandbox(
                "start",
                "--archive",
                archive,
                "--frontend-port",
                str(frontend_port),
                "--backend-port",
                str(backend_port),
                "--postgres-port",
                str(postgres_port),
                "--review-mode",
                "solo",
            )
            first = manifest()["active"]
            target = target_env()
            assert snapshot(target, first) == before  # Before login, sessions, or any writes.
            assert snapshot(env, env["POSTGRES_DB"]) == before
            stage("http_and_publication")
            frontend, admin = result["frontend"], result["admin"]
            wait_http(admin)
            for locale, notice in (
                ("en", "Copied data for local testing only"),
                ("ar", "دي بيانات منسوخة للتجربة المحلية بس"),
            ):
                wait_http(frontend + "/" + locale)
                _, body = http(urllib.request.build_opener(), frontend + "/" + locale)
                assert notice in body and "sandbox-notice" in body
            assert planning(frontend, {"synthetic_ready": True})["type"] != "plan"
            login(admin, manifest()["id"])
            command(fixture + ["blocked"], env=target)
            assert planning(frontend, {"synthetic_ready": True}, "risk-research")["type"] != "plan"
            question = planning(frontend, {})
            assert question["type"] == "next_question" and question["question"]["id"] == "ready"
            command(fixture + ["publish"], env=target)
            plan = planning(frontend, {"synthetic_ready": True})
            assert plan["type"] == "plan" and plan["procedure_version_id"] == "draft"
            command(fixture + ["withdraw"], env=target)
            assert planning(frontend, {"synthetic_ready": True})["type"] != "plan"
            if options.with_browser:
                stage("real_browser_journeys")
                browser_phase(fixture, target, first, frontend, private)
            edited = snapshot(target, first)
            edited_rows = row_fingerprint(target, first)
            assert edited != before
            stage("resume_persistence")
            sandbox("start")
            assert manifest()["active"] == first and snapshot(target, first) == edited
            sandbox("stop")
            sandbox("start")
            assert manifest()["active"] == first
            assert row_fingerprint(target, first) == edited_rows
            edited = snapshot(target, first)
            stage("refresh_generation")
            sandbox("refresh", archive, "--confirm")
            second = manifest()["active"]
            assert second != first
            target = target_env()
            assert snapshot(target, second) == before and snapshot(target, first) == edited
            stage("rejected_refresh")
            invalid = private / "invalid.dump"
            invalid.write_bytes(b"not a PostgreSQL archive")
            invalid.chmod(0o600)
            sandbox("refresh", str(invalid), "--confirm", check=False)
            assert manifest()["active"] == second and snapshot(target, second) == before
            sandbox("start")
            # An incompatible archive is generated from an owned clone, never by
            # altering the synthetic control source (or an authoring database).
            import psycopg
            from psycopg import sql

            with psycopg.connect(
                dbname="postgres",
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                host="127.0.0.1",
                port=source_port,
                autocommit=True,
            ) as conn:
                conn.execute(
                    sql.SQL("CREATE DATABASE bardi_probe_incompatible TEMPLATE {}").format(
                        sql.Identifier(env["POSTGRES_DB"])
                    )
                )
            with psycopg.connect(
                dbname="bardi_probe_incompatible",
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                host="127.0.0.1",
                port=source_port,
            ) as conn:
                conn.execute(
                    "INSERT INTO django_migrations(app,name,applied) "
                    "VALUES ('probe_unknown','0001_unknown',now())"
                )
            incompatible = backup(private / "incompatible", "bardi_probe_incompatible")
            sandbox("refresh", incompatible, "--confirm", check=False)
            assert manifest()["active"] == second and snapshot(target, second) == before
            sandbox("start")
            # Refreshing a stopped sandbox must not launch its applications.
            sandbox("stop")
            result = sandbox("refresh", archive, "--confirm")
            assert result["status"] == "stopped" and manifest()["active"] != second
            sandbox("start")
            assert snapshot(target_env(), manifest()["active"]) == before
            assert snapshot(target, second) == before and snapshot(target, first) == edited
            assert snapshot(env, env["POSTGRES_DB"]) == before
            stage("acceptance_complete")
        except Exception as error:
            report_failure(error)
            raise
        finally:
            # Independently attempt both exact-project cleanups even after failure.
            cleanup_errors = []
            if before is not None:
                try:
                    assert snapshot(env, env["POSTGRES_DB"]) == before
                except Exception as error:
                    cleanup_errors.append(error)
            if (state_path / "manifest.json").exists():
                try:
                    cleanup_project(
                        "bardi-sandbox-" + manifest()["id"],
                        ROOT / "compose.sandbox.yaml",
                        {"postgres", "backend", "frontend"},
                        env,
                    )
                except Exception as error:
                    cleanup_errors.append(error)
            if owned_source:
                try:
                    cleanup_project(project, override, {"postgres"}, env)
                except Exception as error:
                    cleanup_errors.append(error)
            if cleanup_errors:
                for cleanup_error in cleanup_errors:
                    report_failure(cleanup_error)
                raise RuntimeError("owned cleanup or source integrity failed") from None
            stage("owned_cleanup_complete")
    print(
        json.dumps(
            {
                "status": "probe_passed",
                "stages": stages,
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        report_failure(error)
        raise SystemExit(1) from None
