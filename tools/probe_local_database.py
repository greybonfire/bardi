"""Opt-in real PostgreSQL recovery regression; owns only its random disposable project."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def command(args, *, env, input=None):
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        input=input,
        capture_output=True,
        check=True,
        timeout=180,
    ).stdout


def wait_for_tcp(env):
    """Wait for the final server, not initdb's temporary Unix-only server.

    Compose's inherited pg_isready healthcheck can pass before host TCP accepts
    connections. Use the same authenticated endpoint as the seed, read-only.
    The 30s retry window plus a final 2s connection attempt bounds this gate.
    """
    import psycopg

    deadline = time.monotonic() + 30
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
            time.sleep(0.1)
        else:
            connection.close()
            return
    raise TimeoutError("disposable PostgreSQL TCP readiness deadline exceeded") from None


def report_failure(error):
    """Emit locations only: exception text/locals/subprocess output may be secret."""
    print(
        json.dumps(
            {
                "status": "probe_failed",
                "exception": type(error).__name__,
                "frames": [
                    {"file": Path(frame.filename).name, "line": frame.lineno}
                    for frame in traceback.extract_tb(error.__traceback__)
                ],
            }
        ),
        file=sys.stderr,
    )


def snapshot(env, database):
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
        with conn.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
            tables = cursor.fetchall()
            for (table,) in tables:
                cursor.execute(
                    sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY 1").format(
                        sql.Identifier(table)
                    )
                )
                digest.update(repr((table, cursor.fetchall())).encode())
            cursor.execute(
                "SELECT sequencename, last_value FROM pg_sequences "
                "WHERE schemaname='public' ORDER BY 1"
            )
            digest.update(repr(cursor.fetchall()).encode())
            # PostgreSQL can move varchar[] casts to each array element on restore;
            # compare catalog identity/validation, not unstable deparsed CHECK text.
            cursor.execute(
                "SELECT conname, contype, convalidated, condeferrable, condeferred, "
                "conrelid::regclass::text, ARRAY(SELECT attname FROM unnest(conkey) "
                "WITH ORDINALITY AS k(num, ord) JOIN pg_attribute a ON "
                "a.attrelid=conrelid AND a.attnum=k.num ORDER BY ord) FROM pg_constraint "
                "WHERE connamespace='public'::regnamespace ORDER BY 1,6"
            )
            digest.update(repr(cursor.fetchall()).encode())
            cursor.execute(
                "SELECT tgname, tgenabled, pg_get_triggerdef(oid) FROM pg_trigger "
                "WHERE NOT tgisinternal ORDER BY 1,3"
            )
            digest.update(repr(cursor.fetchall()).encode())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable", action="store_true", required=True)
    parser.parse_args()
    # Reject remote endpoints before any provisioning, not just in the tested CLI.
    from core.local_database import run

    host = os.environ.get("DOCKER_HOST", "")
    context = json.loads(run(["docker", "context", "inspect"]))
    endpoint = context[0]["Endpoints"]["docker"]["Host"]
    if (host and not host.startswith("unix:///")) or not endpoint.startswith("unix:///"):
        raise RuntimeError("probe requires local Docker")
    project = "bardi-backup-probe-" + uuid.uuid4().hex
    env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": project,
        "POSTGRES_DB": "bardi_probe",
        "POSTGRES_USER": "bardi_probe",
        "POSTGRES_PASSWORD": uuid.uuid4().hex,
        "POSTGRES_HOST": "127.0.0.1",
        "DJANGO_SETTINGS_MODULE": "bardi.settings.test",
        "PYTHONPATH": str(ROOT / "backend"),
    }
    docker = ["docker", "--host", host or endpoint]
    existing = command(
        docker + ["ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"], env=env
    )
    volumes = command(
        docker + ["volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"],
        env=env,
    )
    assert not existing.strip() and not volumes.strip()
    with tempfile.TemporaryDirectory(prefix="bardi-backup-probe-") as temporary:
        temp = Path(temporary)
        override = temp / "override.yaml"
        override.write_text(
            'services:\n  postgres:\n    ports: !override ["127.0.0.1::5432"]\n'
            "    healthcheck:\n      start_period: 60s\n      retries: 24\n"
        )
        compose = docker + [
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            "/dev/null",
            "-p",
            project,
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
        ]
        try:
            command(compose + ["up", "-d", "--wait", "postgres"], env=env)
            address = command(compose + ["port", "postgres", "5432"], env=env).decode().strip()
            env["POSTGRES_PORT"] = address.rsplit(":", 1)[1]
            wait_for_tcp(env)
            seed = """
import django
django.setup()
from django.core.management import call_command
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
    assert cursor.fetchone()[0] == 0, "source must be fresh"
call_command("migrate", verbosity=0, interactive=False)
from knowledge.tests.test_procedure_versions import ProcedureVersionTests
from knowledge.publication import publish_procedure_version, withdraw_procedure_version
from django.contrib.auth.models import Permission
fixture = ProcedureVersionTests()
fixture.setUp()
fixture.actor.is_staff = True
fixture.actor.set_password("synthetic-probe-only")
fixture.actor.save()
fixture.actor.user_permissions.add(Permission.objects.get(codename="view_procedureversion"))
published = publish_procedure_version(fixture.draft().pk, actor=fixture.actor)
withdraw_procedure_version(published.pk, actor=fixture.actor)
fixture.draft("versions.unpublished", text_en="Synthetic draft guidance")
assert fixture.actor.user_permissions.count() == 1
assert published.audit_events.count() == 2
"""
            command([sys.executable, "-c", seed], env=env)
            before = snapshot(env, "bardi_probe")
            cli = [sys.executable, str(ROOT / "tools/local_database.py")]
            result = json.loads(
                command(cli + ["backup", "--directory", str(temp / "backups")], env=env)
            )
            archive = result["path"]
            target = "bardi_restore_probe"
            restored = json.loads(
                command(cli + ["restore", archive, "--database", target], env=env)
            )
            assert restored["status"] == "restored_unverified"
            assert snapshot(env, target) == before
            assert snapshot(env, "bardi_probe") == before
            for database in ["bardi_probe", target]:
                rejected = subprocess.run(
                    cli + ["restore", archive, "--database", database],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    timeout=180,
                )
                assert rejected.returncode == 1
            # Corruption must fail before target creation.
            broken = temp / "broken.dump"
            broken.write_bytes(Path(archive).read_bytes()[:-200])
            rejected = subprocess.run(
                cli + ["restore", str(broken), "--database", "bardi_restore_broken"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=180,
            )
            assert rejected.returncode == 1
            import psycopg

            with psycopg.connect(
                dbname="postgres",
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                host="127.0.0.1",
                port=env["POSTGRES_PORT"],
                autocommit=True,
            ) as conn:
                assert (
                    conn.execute(
                        "SELECT 1 FROM pg_database WHERE datname='bardi_restore_broken'"
                    ).fetchone()
                    is None
                )
                conn.execute("CREATE DATABASE bardi_restore_empty TEMPLATE template0")
            rejected = subprocess.run(
                cli + ["restore", archive, "--database", "bardi_restore_empty"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=180,
            )
            assert rejected.returncode == 1
            with psycopg.connect(
                dbname=target,
                user=env["POSTGRES_USER"],
                password=env["POSTGRES_PASSWORD"],
                host="127.0.0.1",
                port=env["POSTGRES_PORT"],
            ) as conn:
                for statement, error_type in [
                    (
                        "UPDATE knowledge_procedureversion SET text_en='forbidden' "
                        "WHERE state='withdrawn'",
                        psycopg.errors.RaiseException,
                    ),
                    (
                        "UPDATE knowledge_procedureversion SET state='invalid' WHERE state='draft'",
                        psycopg.DatabaseError,
                    ),
                ]:
                    try:
                        with conn.transaction():
                            conn.execute(statement)
                    except error_type:
                        pass
                    else:
                        raise AssertionError("restored invariant did not reject mutation")
            checks = {
                **env,
                "POSTGRES_DB": target,
                "PGOPTIONS": "-c default_transaction_read_only=on",
            }
            for check in [["migrate", "--check"], ["check"]]:
                command(
                    [sys.executable, "backend/manage.py", *check, "--settings=bardi.settings.test"],
                    env=checks,
                )
            assert snapshot(env, "bardi_probe") == before
            print(
                json.dumps(
                    {
                        "status": "probe_passed",
                        "coverage": (
                            "all public rows, password/permission, draft, publication audits, "
                            "sequences, constraints, triggers, migration/system checks, "
                            "source unchanged, rejection guards"
                        ),
                    }
                )
            )
        finally:
            command(compose + ["down", "-v", "--remove-orphans"], env=env)
            assert not command(
                docker + ["ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"],
                env=env,
            ).strip()
            assert not command(
                docker
                + ["volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"],
                env=env,
            ).strip()
            assert not command(
                docker
                + [
                    "network",
                    "ls",
                    "-q",
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                ],
                env=env,
            ).strip()
            print(json.dumps({"cleanup": "complete", "disposable_project": project}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        report_failure(error)
        raise SystemExit(1) from None
