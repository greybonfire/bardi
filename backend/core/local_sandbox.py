"""Guarded, reusable local questionnaire sandbox. Trusted archives only."""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from core.local_database import ROOT, LocalDatabaseError, LocalPostgres, restore
from core.sandbox_state import State

COMPOSE = ROOT / "compose.sandbox.yaml"
DEFAULT_STATE = Path.home() / ".local/state/bardi/questionnaire-sandbox"
PORTS = {"frontend": 13000, "backend": 18000, "postgres": 15432}
TARGET_PORTS = {"frontend": "3000/tcp", "backend": "8000/tcp", "postgres": "5432/tcp"}


def require(condition: object, code: str) -> None:
    if not condition:
        raise LocalDatabaseError(code)


def new_manifest(args: argparse.Namespace) -> dict[str, Any]:
    ports = {
        service: port
        if getattr(args, f"{service}_port") is None
        else getattr(args, f"{service}_port")
        for service, port in PORTS.items()
    }
    require(all(1 <= p <= 65535 for p in ports.values()), "invalid_ports")
    require(len(set(ports.values())) == 3, "duplicate_ports")
    return {
        "version": 1,
        "id": uuid.uuid4().hex,
        "ports": ports,
        "review_mode": args.review_mode or "solo",
        "password": secrets.token_hex(32),
        "secret": secrets.token_hex(48),
        "volume": None,
        "cluster": None,
        "active": None,
    }


def validate_manifest(m: dict[str, Any]) -> None:
    require(m["version"] == 1, "unsupported_state")
    for key, length in (("id", 32), ("password", 64), ("secret", 96)):
        require(re.fullmatch(rf"[a-f0-9]{{{length}}}", m[key]), "invalid_state")
    require(m["review_mode"] in {"solo", "independent"}, "invalid_state")
    require(set(m["ports"]) == set(PORTS), "invalid_state")
    require(all(type(p) is int and 1 <= p <= 65535 for p in m["ports"].values()), "invalid_state")
    require(len(set(m["ports"].values())) == 3, "invalid_state")
    require(
        m["active"] is None or re.fullmatch(r"bardi_restore_[a-f0-9]{32}", m["active"]),
        "invalid_state",
    )
    require(m["cluster"] is None or re.fullmatch(r"[0-9]+", m["cluster"]), "invalid_state")
    require(m["active"] is None or (m["volume"] and m["cluster"]), "invalid_state")


class Sandbox:
    def __init__(self, state: State, manifest: dict[str, Any]) -> None:
        validate_manifest(manifest)
        self.state, self.m = state, manifest
        self.project = f"bardi-sandbox-{manifest['id']}"
        self.volume = f"{self.project}_postgres_data"
        self.network = f"{self.project}_default"
        # Do not consult ambient context, DOCKER_HOST, TLS, credentials, or .env.
        self.docker = [
            "docker",
            "--host",
            "unix:///var/run/docker.sock",
        ]

    def run(
        self,
        args: list[str],
        *,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | int = subprocess.PIPE,
        pass_fds: tuple[int, ...] = (),
    ) -> bytes:
        self.state.verify_path()
        with tempfile.TemporaryDirectory(prefix="bardi-sandbox-docker-") as home:
            return self._run_private(args, home, stdin, stdout, pass_fds)

    def _run_private(
        self,
        args: list[str],
        home: str,
        stdin: BinaryIO | None,
        stdout: BinaryIO | int,
        pass_fds: tuple[int, ...],
    ) -> bytes:
        try:
            result = subprocess.run(
                self.docker + ["--config", home] + args,
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": home,
                    "LANG": "C.UTF-8",
                },
                stdin=stdin,
                stdout=stdout,
                stderr=subprocess.DEVNULL,
                timeout=600,
                check=True,
                pass_fds=pass_fds,
            )
        except OSError, subprocess.SubprocessError:
            raise LocalDatabaseError("sandbox_command_failed") from None
        return result.stdout if isinstance(result.stdout, bytes) else b""

    def inspect(self, kind: str, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        value: list[dict[str, Any]] = json.loads(self.run([kind, "inspect", *names]))
        return value

    def resources(self, kind: str, name: str) -> list[dict[str, Any]]:
        # Union catches foreign resources squatting on our names and project-labelled extras.
        names: set[str] = set()
        for selector in (f"label=com.docker.compose.project={self.project}", f"name={name}"):
            names.update(self.run([kind, "ls", "-q", "--filter", selector]).decode().split())
        return self.inspect(kind, sorted(names))

    def containers(self) -> list[dict[str, Any]]:
        names: set[str] = set()
        for selector in (
            f"label=com.docker.compose.project={self.project}",
            f"name={self.project}",
        ):
            names.update(
                self.run(["container", "ls", "-aq", "--filter", selector]).decode().split()
            )
        return self.inspect("container", sorted(names))

    @staticmethod
    def volume_proof(volume: dict[str, Any]) -> dict[str, Any]:
        return {
            key: volume[key]
            for key in ("Name", "CreatedAt", "Mountpoint", "Labels", "Driver", "Options", "Scope")
        }

    def check_volume_identity(self, volume: dict[str, Any]) -> None:
        labels = volume.get("Labels") or {}
        require(
            volume["Name"] == self.volume
            and volume["Driver"] == "local"
            and volume["Scope"] == "local"
            and not volume["Options"]
            and labels.get("com.docker.compose.project") == self.project
            and labels.get("com.docker.compose.volume") == "postgres_data"
            and labels.get("bardi.sandbox.id") == self.m["id"],
            "unexpected_volume",
        )

    @property
    def validation_name(self) -> str:
        return f"{self.project}-validation"

    def expected_environment(self, service: str) -> dict[str, str]:
        if service == "frontend":
            return {
                "BARDI_SANDBOX": "1",
                "BARDI_API_ORIGIN": "http://backend:8000",
                "BARDI_SITE_ORIGIN": f"http://127.0.0.1:{self.m['ports']['frontend']}",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
        values = {"POSTGRES_USER": "sandbox", "POSTGRES_PASSWORD": self.m["password"]}
        if service == "postgres":
            return {**values, "POSTGRES_DB": "postgres"}
        return {
            **values,
            "DJANGO_SETTINGS_MODULE": "bardi.settings.sandbox",
            "DJANGO_SECRET_KEY": self.m["secret"],
            "BARDI_SANDBOX": "1",
            "BARDI_SANDBOX_ID": self.m["id"],
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5432",
            "PROCEDURE_VERSION_REVIEW_MODE": self.m["review_mode"],
        }

    def guard(self) -> dict[str, dict[str, Any]]:
        volumes = self.resources("volume", self.volume)
        if self.m["volume"] is None:
            require(not volumes, "uncommitted_volume_refused")
        else:
            require(len(volumes) == 1, "initialized_volume_missing")
            self.check_volume_identity(volumes[0])
            require(
                self.volume_proof(volumes[0]) == self.m["volume"], "initialized_volume_replaced"
            )
        networks = self.resources("network", self.network)
        require(len(networks) <= 1, "unexpected_network")
        for network in networks:
            labels = network.get("Labels") or {}
            require(
                network["Name"] == self.network
                and labels.get("com.docker.compose.project") == self.project
                and labels.get("com.docker.compose.network") == "default"
                and labels.get("bardi.sandbox.id") == self.m["id"]
                and network["Driver"] == "bridge"
                and network["Scope"] == "local"
                and not network.get("Options")
                and not network.get("EnableIPv6"),
                "unexpected_network",
            )
        services: dict[str, dict[str, Any]] = {}
        containers = self.containers()
        ids = {c["Id"] for c in containers}
        for network in networks:
            require(set(network.get("Containers", {})) <= ids, "foreign_network_member")
        if volumes:
            consumers = (
                self.run(
                    ["container", "ls", "-aq", "--no-trunc", "--filter", f"volume={self.volume}"]
                )
                .decode()
                .split()
            )
            require(set(consumers) <= ids, "foreign_volume_consumer")
        for c in containers:
            labels = c["Config"].get("Labels") or {}
            service = str(labels.get("com.docker.compose.service", ""))
            transient = c["Name"] == f"/{self.validation_name}"
            key = "validation" if transient else service
            require(service in PORTS and key not in services, "unexpected_service")
            require(not transient or service == "backend", "unexpected_service")
            require(
                labels.get("com.docker.compose.project") == self.project
                and labels.get("com.docker.compose.project.working_dir") == str(ROOT)
                and labels.get("com.docker.compose.project.config_files") == str(COMPOSE)
                and labels.get("com.docker.compose.oneoff") == ("True" if transient else "False")
                and c["Name"]
                == (f"/{self.validation_name}" if transient else f"/{self.project}-{service}-1"),
                "unexpected_container_identity",
            )
            expected_image = "postgres:17" if service == "postgres" else f"{self.project}-{service}"
            require(c["Config"]["Image"] == expected_image, "unexpected_image")
            environment = dict(
                item.split("=", 1) for item in c["Config"].get("Env", []) if "=" in item
            )
            require(
                all(environment.get(k) == v for k, v in self.expected_environment(service).items()),
                "unexpected_service_environment",
            )
            if service == "backend":
                require(not c["Config"].get("Entrypoint"), "unexpected_application_entrypoint")
                require(c["Config"].get("WorkingDir") == "/app", "unexpected_application_directory")
                database = environment.get("POSTGRES_DB", "")
                require(
                    re.fullmatch(r"bardi_restore_[a-f0-9]{32}", database), "unexpected_database"
                )
                require(
                    transient or not c["State"]["Running"] or database == self.m["active"],
                    "uncommitted_running_generation",
                )
                require(
                    environment.get("PGOPTIONS")
                    == ("-c default_transaction_read_only=on" if transient else None),
                    "unexpected_database_options",
                )
                command = (
                    ["python", "backend/manage.py", "sandbox_check"]
                    if transient
                    else [
                        "sh",
                        "-c",
                        "PGOPTIONS='-c default_transaction_read_only=on' "
                        "python backend/manage.py sandbox_check && "
                        "python backend/manage.py runserver 0.0.0.0:8000 --noreload --insecure",
                    ]
                )
                require(c["Config"].get("Cmd") == command, "unexpected_application_command")
            elif service == "frontend":
                require(
                    c["Config"].get("Entrypoint") == ["docker-entrypoint.sh"]
                    and c["Config"].get("WorkingDir") == "/app",
                    "unexpected_application_entrypoint",
                )
                require(
                    c["Config"].get("Cmd")
                    == ["./node_modules/.bin/next", "dev", "--hostname", "0.0.0.0"],
                    "unexpected_application_command",
                )
            host = c["HostConfig"]
            require(
                not host.get("Privileged")
                and (
                    not host.get("Binds")
                    or (
                        service == "postgres"
                        and host["Binds"] == [f"{self.volume}:/var/lib/postgresql/data:rw"]
                    )
                )
                and not host.get("VolumesFrom")
                and not host.get("CapAdd")
                and not host.get("Devices")
                and host.get("NetworkMode") == self.network
                and host.get("RestartPolicy", {}).get("Name", "no") in {"no", ""}
                and host.get("LogConfig", {}).get("Type") == "none"
                and (
                    not host.get("PortBindings")
                    if transient
                    else host.get("PortBindings")
                    == {
                        TARGET_PORTS[service]: [
                            {"HostIp": "127.0.0.1", "HostPort": str(self.m["ports"][service])}
                        ]
                    }
                ),
                "unexpected_container_configuration",
            )
            require(
                set(c["NetworkSettings"]["Networks"]) == {self.network}, "unexpected_attachment"
            )
            mounts = c["Mounts"]
            if service == "postgres":
                require(
                    len(mounts) == 1
                    and mounts[0]["Type"] == "volume"
                    and mounts[0]["Name"] == self.volume
                    and mounts[0]["Destination"] == "/var/lib/postgresql/data"
                    and self.m["volume"] is not None
                    and mounts[0]["Source"] == self.m["volume"]["Mountpoint"],
                    "unexpected_postgres_mount",
                )
            else:
                require(not mounts, "unexpected_application_mount")
            services[key] = c
        return services

    def reconcile_validation(self) -> None:
        transient = self.guard().get("validation")
        if transient:
            self.run(["container", "rm", "-f", transient["Id"]])

    def remove_apps(self) -> None:
        self.compose(["stop", "frontend", "backend"])
        services = self.guard()
        for service in ("frontend", "backend"):
            if service in services:
                require(not services[service]["State"]["Running"], "application_not_stopped")
                self.run(["container", "rm", services[service]["Id"]])

    def compose(self, args: list[str], *, database: str | None = None) -> None:
        self.guard()
        values = {
            "SANDBOX_PROJECT": self.project,
            "SANDBOX_ID": self.m["id"],
            "SANDBOX_PASSWORD": self.m["password"],
            "SANDBOX_SECRET": self.m["secret"],
            "SANDBOX_REVIEW_MODE": self.m["review_mode"],
            "SANDBOX_DATABASE": database or self.m["active"] or "bardi_restore_" + "0" * 32,
            **{f"SANDBOX_{k.upper()}_PORT": str(v) for k, v in self.m["ports"].items()},
        }
        self.state.replace("compose.env", "".join(f"{k}={v}\n" for k, v in values.items()))
        fd = self.state.open("compose.env", os.O_RDONLY)
        try:
            self.run(
                [
                    "compose",
                    "--project-name",
                    self.project,
                    "--project-directory",
                    str(ROOT),
                    "--env-file",
                    f"/proc/{os.getpid()}/fd/{fd}",
                    "-f",
                    str(COMPOSE),
                    *args,
                ],
                stdout=subprocess.DEVNULL,
                pass_fds=(fd,),
            )
        finally:
            os.close(fd)

    def initialize_volume(self) -> None:
        self.guard()
        if self.m["volume"] is not None:
            return
        self.run(
            [
                "volume",
                "create",
                "--driver",
                "local",
                "--label",
                f"com.docker.compose.project={self.project}",
                "--label",
                "com.docker.compose.volume=postgres_data",
                "--label",
                f"bardi.sandbox.id={self.m['id']}",
                self.volume,
            ]
        )
        volume = self.inspect("volume", [self.volume])[0]
        self.check_volume_identity(volume)
        self.m["volume"] = self.volume_proof(volume)
        self.state.commit(self.m)

    def postgres(self) -> SandboxPostgres:
        self.initialize_volume()
        self.compose(
            [
                "up",
                "-d",
                "--no-deps",
                "--no-recreate",
                "--wait",
                "--wait-timeout",
                "120",
                "postgres",
            ]
        )
        db = SandboxPostgres(self)
        cluster = db.sql("SELECT system_identifier FROM pg_control_system()").decode().strip()
        require(re.fullmatch(r"[0-9]+", cluster), "invalid_cluster_identity")
        if self.m["cluster"] is not None:
            require(cluster == self.m["cluster"], "cluster_identity_changed")
        else:
            self.m["cluster"] = cluster
            self.state.commit(self.m)
        return db

    def compatible(self, database: str) -> None:
        self.compose(
            [
                "run",
                "--rm",
                "--name",
                self.validation_name,
                "--no-deps",
                "-T",
                "-e",
                "PGOPTIONS=-c default_transaction_read_only=on",
                "backend",
                "python",
                "backend/manage.py",
                "sandbox_check",
            ],
            database=database,
        )

    def apps(self) -> None:
        self.remove_apps()
        for service in ("backend", "frontend"):
            self.compose(
                [
                    "up",
                    "-d",
                    "--no-deps",
                    "--no-recreate",
                    "--wait",
                    "--wait-timeout",
                    "180",
                    service,
                ]
            )
        self.guard()

    def start(self, archive: Path | None) -> None:
        require(
            (self.m["active"] is None) == (archive is not None),
            "start_archive_requires_uninitialized_generation",
        )
        self.reconcile_validation()
        # Quiesce existing apps before code/schema compatibility checks.
        self.compose(["stop", "frontend", "backend"])
        db = self.postgres()
        self.compose(["build", "backend", "frontend"])
        if archive is not None:
            self.candidate(db, archive)
        else:
            self.compatible(self.m["active"])
        self.apps()

    def candidate(self, db: SandboxPostgres, archive: Path) -> None:
        candidate = "bardi_restore_" + uuid.uuid4().hex
        restore(db, archive, candidate)
        self.compatible(candidate)
        # Never roll back an ambiguous atomic commit. The on-disk manifest wins on retry.
        self.m["active"] = candidate
        self.state.commit(self.m)

    def refresh(self, archive: Path) -> None:
        require(self.m["active"] is not None, "refresh_requires_active_generation")
        self.reconcile_validation()
        services = self.guard()
        running = any(
            services.get(s, {}).get("State", {}).get("Running") for s in ("backend", "frontend")
        )
        self.compose(["stop", "frontend", "backend"])
        db = self.postgres()
        self.compose(["build", "backend", "frontend"])
        self.candidate(db, archive)
        if running:
            self.apps()
        else:
            self.compose(["stop", "postgres"])

    def status(self) -> str:
        services = self.guard()
        if self.m["active"] is None or "validation" in services:
            return "interrupted-or-unavailable"
        running = {s for s, c in services.items() if c["State"]["Running"]}
        if not running:
            return "stopped"
        if running == set(PORTS) and all(
            c["State"].get("Health", {}).get("Status") == "healthy" for c in services.values()
        ):
            return "running"
        return "interrupted-or-unavailable"


class SandboxPostgres(LocalPostgres):
    """Task1 archive/fresh-target guards, connected only to verified sandbox PostgreSQL."""

    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox
        services = sandbox.guard()
        require(
            "postgres" in services and services["postgres"]["State"]["Running"],
            "postgres_unavailable",
        )
        self.container = services["postgres"]["Id"]
        self.source, self.user = "postgres", "sandbox"

    def exec(
        self,
        args: list[str],
        *,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | int = subprocess.PIPE,
    ) -> bytes:
        services = self.sandbox.guard()
        require(services.get("postgres", {}).get("Id") == self.container, "postgres_changed")
        return self.sandbox.run(
            ["exec", "-i", "-e", "PGCONNECT_TIMEOUT=10", self.container, *args],
            stdin=stdin,
            stdout=stdout,
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--state-directory", type=Path, default=DEFAULT_STATE)
    sub = result.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--archive", type=Path)
    for service in PORTS:
        start.add_argument(f"--{service}-port", type=int)
    start.add_argument("--review-mode", choices=("solo", "independent"))
    refresh = sub.add_parser("refresh")
    refresh.add_argument("archive", type=Path)
    refresh.add_argument("--confirm", action="store_true", required=True)
    sub.add_parser("stop")
    sub.add_parser("status")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    state: State | None = None
    try:
        if args.command in {"status", "stop"} and not os.path.lexists(args.state_directory):
            print(json.dumps({"status": "not-initialized"}))
            return 0
        state = State(args.state_directory, create=args.command == "start")
        manifest = state.read()
        if manifest is None:
            if args.command in {"status", "stop"}:
                print(json.dumps({"status": "not-initialized"}))
                return 0
            require(
                args.command == "start" and args.archive is not None, "initial_archive_required"
            )
            manifest = new_manifest(args)
            state.commit(manifest)
        elif args.command == "start":
            require(
                args.review_mode is None and all(getattr(args, f"{s}_port") is None for s in PORTS),
                "initial_configuration_immutable",
            )
        sandbox = Sandbox(state, manifest)
        if args.command == "status":
            status = sandbox.status()
        elif args.command == "stop":
            sandbox.reconcile_validation()
            sandbox.compose(["stop", "frontend", "backend", "postgres"])
            status = "stopped"
        else:
            if args.command == "start":
                sandbox.start(args.archive)
            else:
                sandbox.refresh(args.archive)
            status = sandbox.status()
        print(
            json.dumps(
                {
                    "status": status,
                    "project": sandbox.project,
                    "database": manifest["active"],
                    "frontend": f"http://127.0.0.1:{manifest['ports']['frontend']}",
                    "admin": f"http://127.0.0.1:{manifest['ports']['backend']}/admin/",
                }
            )
        )
        return 0
    except (
        LocalDatabaseError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        KeyboardInterrupt,
    ):
        print(
            json.dumps(
                {
                    "status": "interrupted-or-unavailable",
                    "error": "sandbox_operation_failed",
                    "recovery": "data_retained; use start to resume the committed generation",
                }
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        if state is not None:
            state.close()
