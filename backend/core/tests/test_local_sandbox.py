"""Database-free safety and generation-transition regressions; never touch Docker."""

import contextlib
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from core import local_sandbox as local
from core.sandbox_state import State


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.state = State(self.path, create=True)
        self.addCleanup(self.state.close)

    def test_atomic_private_manifest_and_lock_inode_retained(self) -> None:
        inode = (self.path / "lock").stat().st_ino
        self.assertIsNone(self.state.read())
        self.state.commit({"active": "one"})
        self.state.commit({"active": "two"})
        self.assertEqual(self.state.read(), {"active": "two"})
        self.assertEqual((self.path / "manifest.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.path / "lock").stat().st_ino, inode)
        with self.assertRaises(BlockingIOError):
            State(self.path)
        self.assertEqual(sorted(p.name for p in self.path.iterdir()), ["lock", "manifest.json"])

    def test_private_files_reject_symlink_hardlink_nonregular_and_mode(self) -> None:
        target = self.path / "manifest.json"
        outside = self.path / "other"
        outside.write_text("{}")
        outside.chmod(0o600)
        for kind in ("symlink", "hardlink", "fifo", "public"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    target.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, target)
                elif kind == "fifo":
                    os.mkfifo(target, 0o600)
                else:
                    target.write_text("{}")
                    target.chmod(0o644)
                with self.assertRaises((OSError, local.LocalDatabaseError)):
                    self.state.read()
                with self.assertRaises((OSError, local.LocalDatabaseError)):
                    self.state.commit({"changed": True})
                target.unlink()
        self.assertEqual(outside.read_text(), "{}")

    def test_replace_failure_retains_old_and_cleans_temporary(self) -> None:
        self.state.commit({"active": "old"})
        with patch("core.sandbox_state.os.replace", side_effect=OSError("secret")):
            with self.assertRaises(OSError):
                self.state.commit({"active": "new"})
        self.assertEqual(self.state.read(), {"active": "old"})
        self.assertFalse(list(self.path.glob("*.tmp")))

    def test_ambiguous_fsync_commit_is_not_rolled_back(self) -> None:
        self.state.commit({"active": "old"})
        real_sync = os.fsync

        def sync(fd: int) -> None:
            if fd == self.state.fd:
                raise OSError("ambiguous")
            real_sync(fd)

        with patch("core.sandbox_state.os.fsync", side_effect=sync):
            with self.assertRaises(OSError):
                self.state.commit({"active": "new"})
        self.assertEqual(self.state.read(), {"active": "new"})

    def test_directory_and_lock_replacement_refused(self) -> None:
        lock = self.path / "lock"
        lock.rename(self.path / "retained-lock")
        lock.touch(mode=0o600)
        with self.assertRaises(local.LocalDatabaseError):
            self.state.commit({})
        lock.unlink()
        (self.path / "retained-lock").rename(lock)
        old = self.path / "nested"
        old.mkdir(mode=0o700)
        nested = State(old, create=True)
        try:
            old.rename(self.path / "moved")
            old.mkdir(mode=0o700)
            with self.assertRaises(local.LocalDatabaseError):
                nested.commit({})
            self.assertEqual(list(old.iterdir()), [])
        finally:
            nested.close()


class SandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MagicMock(spec=State)
        self.m = local.new_manifest(local.parser().parse_args(["start", "--archive", "input.dump"]))
        self.sandbox = local.Sandbox(self.state, self.m)

    def resources(self) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        s = self.sandbox
        volume = {
            "Name": s.volume,
            "CreatedAt": "unique-creation-time",
            "Mountpoint": "/own/data",
            "Labels": {
                "com.docker.compose.project": s.project,
                "com.docker.compose.volume": "postgres_data",
                "bardi.sandbox.id": self.m["id"],
            },
            "Driver": "local",
            "Scope": "local",
            "Options": None,
        }
        self.m["volume"] = copy.deepcopy(volume)
        network = {
            "Name": s.network,
            "Labels": {
                "com.docker.compose.project": s.project,
                "com.docker.compose.network": "default",
                "bardi.sandbox.id": self.m["id"],
            },
            "Driver": "bridge",
            "Scope": "local",
            "Options": {},
            "Containers": {},
        }
        self.m["active"] = "bardi_restore_" + "1" * 32
        self.m["cluster"] = "12345"
        containers = []
        for service, target in local.TARGET_PORTS.items():
            c: dict[str, Any] = {
                "Id": service,
                "Name": f"/{s.project}-{service}-1",
                "Config": {
                    "WorkingDir": "/app",
                    "Entrypoint": ["docker-entrypoint.sh"] if service == "frontend" else None,
                    "Image": "postgres:17" if service == "postgres" else f"{s.project}-{service}",
                    "Env": [f"{k}={v}" for k, v in s.expected_environment(service).items()]
                    + ([f"POSTGRES_DB={self.m['active']}"] if service == "backend" else []),
                    "Cmd": (
                        [
                            "sh",
                            "-c",
                            "PGOPTIONS='-c default_transaction_read_only=on' "
                            "python backend/manage.py sandbox_check && "
                            "python backend/manage.py runserver 0.0.0.0:8000 --noreload --insecure",
                        ]
                        if service == "backend"
                        else ["./node_modules/.bin/next", "dev", "--hostname", "0.0.0.0"]
                    ),
                    "Labels": {
                        "com.docker.compose.project": s.project,
                        "com.docker.compose.service": service,
                        "com.docker.compose.project.working_dir": str(local.ROOT),
                        "com.docker.compose.project.config_files": str(local.COMPOSE),
                        "com.docker.compose.oneoff": "False",
                    },
                },
                "HostConfig": {
                    "NetworkMode": s.network,
                    "LogConfig": {"Type": "none"},
                    "PortBindings": {
                        target: [{"HostIp": "127.0.0.1", "HostPort": str(self.m["ports"][service])}]
                    },
                },
                "NetworkSettings": {"Networks": {s.network: {}}},
                "Mounts": [],
                "State": {"Running": True, "Health": {"Status": "healthy"}},
            }
            if service == "postgres":
                c["Mounts"] = [
                    {
                        "Type": "volume",
                        "Name": s.volume,
                        "Destination": "/var/lib/postgresql/data",
                        "Source": "/own/data",
                    }
                ]
            containers.append(c)
        return volume, network, containers

    def guard_fixture(
        self, volume: dict[str, Any], network: dict[str, Any], containers: list[dict[str, Any]]
    ) -> contextlib.ExitStack:
        stack = contextlib.ExitStack()
        stack.enter_context(
            patch.object(
                self.sandbox,
                "resources",
                side_effect=lambda kind, name: [volume] if kind == "volume" else [network],
            )
        )
        stack.enter_context(patch.object(self.sandbox, "containers", return_value=containers))
        stack.enter_context(patch.object(self.sandbox, "run", return_value=b"postgres\n"))
        return stack

    def test_exact_topology_and_truthful_status(self) -> None:
        v, n, containers = self.resources()
        self.m["active"] = "bardi_restore_" + "1" * 32
        with self.guard_fixture(v, n, containers):
            self.assertEqual(set(self.sandbox.guard()), set(local.PORTS))
            self.assertEqual(self.sandbox.status(), "running")
            containers[0]["State"]["Health"]["Status"] = "unhealthy"
            self.assertEqual(self.sandbox.status(), "interrupted-or-unavailable")
            for c in containers:
                c["State"]["Running"] = False
            self.assertEqual(self.sandbox.status(), "stopped")

    def test_hostile_container_identity_mount_network_port_and_logging_refused(self) -> None:
        mutations = [
            ("Config", "Labels", {"com.docker.compose.project": "authoring"}),
            ("Config", "Image", "authoring-backend"),
            ("HostConfig", "Binds", ["/authoring:/app"]),
            ("HostConfig", "VolumesFrom", ["authoring"]),
            ("HostConfig", "Privileged", True),
            ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
            ("HostConfig", "NetworkMode", "host"),
            ("HostConfig", "RestartPolicy", {"Name": "always"}),
            ("HostConfig", "LogConfig", {"Type": "json-file"}),
            (
                "HostConfig",
                "PortBindings",
                {"3000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "13000"}]},
            ),
            ("NetworkSettings", "Networks", {"authoring_default": {}}),
        ]
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                v, n, containers = self.resources()
                containers[0][section][key] = value
                with (
                    self.guard_fixture(v, n, containers),
                    self.assertRaises(local.LocalDatabaseError),
                ):
                    self.sandbox.guard()
        for service_index in (0, 2):
            v, n, containers = self.resources()
            containers[service_index]["Mounts"] = [{"Type": "bind", "Source": "/authoring"}]
            with self.guard_fixture(v, n, containers), self.assertRaises(local.LocalDatabaseError):
                self.sandbox.guard()

    def test_missing_replaced_uncommitted_volume_and_foreign_members_fail_closed(self) -> None:
        for change in (
            "missing",
            "replaced",
            "uncommitted",
            "network",
            "consumer",
            "foreign_network",
        ):
            with self.subTest(change=change):
                v, n, c = self.resources()
                if change == "replaced":
                    v["CreatedAt"] = "replacement"
                if change == "uncommitted":
                    self.m["volume"] = None
                if change == "network":
                    n["Containers"] = {"foreign": {}}
                if change == "foreign_network":
                    n["Labels"]["com.docker.compose.project"] = "authoring"
                with self.guard_fixture(v, n, c):
                    if change == "missing":
                        self.sandbox.resources = MagicMock(return_value=[])  # type: ignore[method-assign]
                    if change == "consumer":
                        self.sandbox.run = MagicMock(return_value=b"foreign")  # type: ignore[method-assign]
                    with self.assertRaises(local.LocalDatabaseError):
                        self.sandbox.guard()

    def test_service_environment_single_variable_mutations(self) -> None:
        for service in local.PORTS:
            keys = list(self.sandbox.expected_environment(service))
            if service == "backend":
                keys += ["POSTGRES_DB", "PGOPTIONS"]
            for key in keys:
                with self.subTest(service=service, key=key):
                    v, n, containers = self.resources()
                    c = next(c for c in containers if c["Id"] == service)
                    c["Config"]["Env"] = [
                        e for e in c["Config"]["Env"] if not e.startswith(key + "=")
                    ] + [key + "=wrong"]
                    with (
                        self.guard_fixture(v, n, containers),
                        self.assertRaises(local.LocalDatabaseError),
                    ):
                        self.sandbox.status()

    def test_stopped_retained_generation_allowed_but_not_running(self) -> None:
        v, n, containers = self.resources()
        self.m["active"] = "bardi_restore_" + "2" * 32
        with self.guard_fixture(v, n, containers):
            with self.assertRaisesRegex(local.LocalDatabaseError, "uncommitted_running_generation"):
                self.sandbox.status()
            for c in containers:
                c["State"]["Running"] = False
            self.assertEqual(self.sandbox.status(), "stopped")

    def validation_fixture(self) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        v, n, containers = self.resources()
        c = copy.deepcopy(next(c for c in containers if c["Id"] == "backend"))
        c["Id"] = "validation-id"
        c["Name"] = "/" + self.sandbox.validation_name
        c["Config"]["Labels"]["com.docker.compose.oneoff"] = "True"
        c["Config"]["Env"].append("PGOPTIONS=-c default_transaction_read_only=on")
        c["Config"]["Cmd"] = ["python", "backend/manage.py", "sandbox_check"]
        c["HostConfig"]["PortBindings"] = {}
        containers.append(c)
        return v, n, containers

    def test_interrupted_validation_reload_retry_without_restore(self) -> None:
        v, n, containers = self.validation_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            state = State(Path(temporary), create=True)
            try:
                state.commit(self.m)
                manifest = state.read()
                assert manifest is not None
                self.sandbox = local.Sandbox(state, manifest)
                with (
                    self.guard_fixture(v, n, containers),
                    patch.object(local, "restore") as restore,
                ):
                    self.assertEqual(self.sandbox.status(), "interrupted-or-unavailable")
                    with (
                        patch.object(self.sandbox, "compose"),
                        patch.object(self.sandbox, "postgres"),
                        patch.object(self.sandbox, "compatible"),
                        patch.object(self.sandbox, "apps"),
                    ):
                        self.sandbox.start(None)
                    assert isinstance(self.sandbox.run, MagicMock)
                    self.sandbox.run.assert_any_call(["container", "rm", "-f", "validation-id"])
                    restore.assert_not_called()
                    committed = state.read()
                    assert committed is not None
                    self.assertEqual(committed["active"], self.m["active"])
            finally:
                state.close()

    def test_apps_remove_only_stopped_canonical_apps_before_no_recreate(self) -> None:
        v, n, containers = self.resources()
        for c in containers:
            if c["Id"] != "postgres":
                c["State"]["Running"] = False
        with self.guard_fixture(v, n, containers), patch.object(self.sandbox, "compose") as compose:
            self.sandbox.apps()
            assert isinstance(self.sandbox.run, MagicMock)
            removals = [
                call.args[0] for call in self.sandbox.run.call_args_list if "rm" in call.args[0]
            ]
            self.assertEqual(
                removals, [["container", "rm", "frontend"], ["container", "rm", "backend"]]
            )
            self.assertEqual(compose.call_args_list[0].args[0], ["stop", "frontend", "backend"])
            for call in compose.call_args_list[1:]:
                self.assertIn("--no-recreate", call.args[0])
                self.assertNotIn("--force-recreate", call.args[0])

    def test_validation_cleanup_refuses_one_field_mutations(self) -> None:
        for section, key, value in [
            ("Config", "Cmd", ["python", "backend/manage.py", "migrate"]),
            ("Config", "Entrypoint", ["sh"]),
            ("Config", "WorkingDir", "/other"),
            ("HostConfig", "PortBindings", {"8000/tcp": []}),
            ("HostConfig", "LogConfig", {"Type": "json-file"}),
        ]:
            v, n, containers = self.validation_fixture()
            containers[-1][section][key] = value
            with self.guard_fixture(v, n, containers), self.assertRaises(local.LocalDatabaseError):
                self.sandbox.reconcile_validation()

    @unittest.skipUnless(
        os.environ.get("BARDI_TEST_REAL_BUILD") == "1", "opt-in local Docker build"
    )
    def test_real_nonroot_cached_minimal_build(self) -> None:
        self.assertNotEqual(os.getuid(), 0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            state = State(path / "state", create=True)
            context = path / "context"
            context.mkdir()
            (context / "Dockerfile").write_text("FROM scratch\nWORKDIR /app\nCOPY marker /marker\n")
            (context / "marker").write_text("sandbox-build-regression\n")
            sandbox = local.Sandbox(state, self.m)
            image = sandbox.project + "-build-proof"
            try:
                ids = []
                execute = subprocess.run
                for attempt in range(2):
                    with tempfile.TemporaryFile() as build_log:

                        def capture(*args: Any, **kwargs: Any) -> Any:
                            kwargs["stderr"] = build_log
                            return execute(*args, **kwargs)

                        with patch.object(local.subprocess, "run", side_effect=capture):
                            sandbox.run(
                                [
                                    "build",
                                    "--provenance=false",
                                    "--progress=plain",
                                    "-t",
                                    image,
                                    str(context),
                                ]
                            )
                        if attempt:
                            build_log.seek(0)
                            self.assertIn(b"CACHED", build_log.read())
                    ids.append(sandbox.inspect("image", [image])[0]["Id"])
                self.assertEqual(ids[0], ids[1])
                # Real Compose-created inspection state after interrupted validation.
                sandbox.run(["image", "tag", image, sandbox.project + "-backend"])
                sandbox.initialize_volume()
                sandbox.m["cluster"] = "12345"
                sandbox.m["active"] = "bardi_restore_" + "1" * 32
                state.commit(sandbox.m)
                with self.assertRaises(local.LocalDatabaseError):
                    sandbox.compose(
                        [
                            "run",
                            "--name",
                            sandbox.validation_name,
                            "--no-deps",
                            "-T",
                            "-e",
                            "PGOPTIONS=-c default_transaction_read_only=on",
                            "backend",
                            "python",
                            "backend/manage.py",
                            "sandbox_check",
                        ]
                    )
                manifest = state.read()
                assert manifest is not None
                sandbox = local.Sandbox(state, manifest)
                self.assertEqual(sandbox.status(), "interrupted-or-unavailable")
                with (
                    patch.object(sandbox, "postgres"),
                    patch.object(sandbox, "compose"),
                    patch.object(sandbox, "compatible"),
                    patch.object(sandbox, "apps"),
                    patch.object(local, "restore") as restore,
                ):
                    sandbox.start(None)
                    restore.assert_not_called()
                self.assertNotIn("validation", sandbox.guard())
                # Only this disposable test's positively guarded, empty resources.
                sandbox.guard()
                sandbox.run(["network", "rm", sandbox.network])
                sandbox.run(["volume", "rm", sandbox.volume])
                sandbox.run(["image", "rm", sandbox.project + "-backend"])
            finally:
                sandbox.run(["image", "rm", image])
                state.close()

    def test_ambient_environment_never_reaches_subprocess(self) -> None:
        hostile = {
            "DOCKER_HOST": "ssh://remote",
            "DOCKER_CONTEXT": "production",
            "COMPOSE_FILE": "compose.yaml",
            "POSTGRES_DB": "authoring",
            "DJANGO_SETTINGS_MODULE": "bardi.settings.test",
            "NEXT_PUBLIC_SECRET": "secret",
            "PGOPTIONS": "host=remote",
            "PATH": "/hostile",
        }
        with patch.dict(os.environ, hostile), patch.object(local.subprocess, "run") as run:
            run.return_value.stdout = b"ok"
            self.assertEqual(self.sandbox.run(["version"]), b"ok")
            kwargs = run.call_args.kwargs
            home = kwargs["env"]["HOME"]
            self.assertNotEqual(home, "/nonexistent")
            self.assertIn(home, run.call_args.args[0])
            self.assertFalse(Path(home).exists())
            self.assertEqual(set(kwargs["env"]), {"PATH", "HOME", "LANG"})
            self.assertEqual(kwargs["timeout"], 600)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertIn("unix:///var/run/docker.sock", run.call_args.args[0])
            self.assertNotIn("secret", str(run.call_args))
            run.side_effect = subprocess.CalledProcessError(1, ["secret"])
            with self.assertRaisesRegex(local.LocalDatabaseError, "sandbox_command_failed"):
                self.sandbox.run(["version"])

    def test_candidate_failure_retains_authoritative_old_generation(self) -> None:
        for stage in ("restore", "check", "commit"):
            self.m["active"] = "old"
            self.state.reset_mock()
            self.state.commit.side_effect = OSError("failure") if stage == "commit" else None
            with (
                patch.object(local, "restore") as restore,
                patch.object(self.sandbox, "compatible") as check,
            ):
                if stage == "restore":
                    restore.side_effect = local.LocalDatabaseError("failed")
                if stage == "check":
                    check.side_effect = local.LocalDatabaseError("failed")
                with self.assertRaises((OSError, local.LocalDatabaseError)):
                    self.sandbox.candidate(MagicMock(), Path("input.dump"))
                if stage != "commit":
                    self.assertEqual(self.m["active"], "old")
                    self.state.commit.assert_not_called()
                else:
                    self.assertNotEqual(self.m["active"], "old")
                self.assertNotIn("DROP", str(restore.call_args_list))

    def test_retry_allocates_new_candidate_and_resume_never_restores(self) -> None:
        with patch.object(local, "restore") as restore, patch.object(self.sandbox, "compatible"):
            for _ in range(2):
                self.sandbox.candidate(MagicMock(), Path("input.dump"))
            self.assertNotEqual(
                restore.call_args_list[0].args[2], restore.call_args_list[1].args[2]
            )
        with (
            patch.object(self.sandbox, "compose") as compose,
            patch.object(self.sandbox, "reconcile_validation"),
            patch.object(self.sandbox, "postgres"),
            patch.object(self.sandbox, "compatible") as check,
            patch.object(self.sandbox, "apps"),
            patch.object(local, "restore") as restore,
        ):
            self.sandbox.start(None)
            restore.assert_not_called()
            check.assert_called_once_with(self.m["active"])
            self.assertIn(
                unittest.mock.call(["build", "backend", "frontend"]), compose.call_args_list
            )
            self.assertNotIn("--no-cache", str(compose.call_args_list))
            with self.assertRaises(local.LocalDatabaseError):
                self.sandbox.start(Path("input.dump"))

    def test_refresh_quiesces_before_restore_and_stopped_stays_stopped(self) -> None:
        for running in (True, False):
            self.m["active"] = "old"
            calls: list[str] = []
            with (
                patch.object(
                    self.sandbox, "guard", return_value={"backend": {"State": {"Running": running}}}
                ),
                patch.object(
                    self.sandbox,
                    "compose",
                    side_effect=lambda args, calls=calls: calls.append(" ".join(args)),
                ),
                patch.object(
                    self.sandbox,
                    "postgres",
                    side_effect=lambda calls=calls: calls.append("postgres"),
                ),
                patch.object(
                    self.sandbox,
                    "candidate",
                    side_effect=lambda db, path, calls=calls: calls.append("candidate"),
                ),
                patch.object(
                    self.sandbox, "apps", side_effect=lambda calls=calls: calls.append("apps")
                ),
            ):
                self.sandbox.refresh(Path("input.dump"))
            self.assertEqual(
                calls[:3], ["stop frontend backend", "postgres", "build backend frontend"]
            )
            self.assertEqual(calls[-2:], ["candidate", "apps" if running else "stop postgres"])

    def test_precommit_failure_does_not_restart_and_postcommit_failure_keeps_new(self) -> None:
        for failure in ("before", "after"):
            self.m["active"] = "old"
            with (
                patch.object(
                    self.sandbox, "guard", return_value={"backend": {"State": {"Running": True}}}
                ),
                patch.object(self.sandbox, "compose"),
                patch.object(self.sandbox, "postgres"),
                patch.object(local, "restore"),
                patch.object(self.sandbox, "compatible") as check,
                patch.object(self.sandbox, "apps") as apps,
            ):
                if failure == "before":
                    check.side_effect = local.LocalDatabaseError("check")
                else:
                    apps.side_effect = local.LocalDatabaseError("apps")
                with self.assertRaises(local.LocalDatabaseError):
                    self.sandbox.refresh(Path("input.dump"))
                if failure == "before":
                    self.assertEqual(self.m["active"], "old")
                    apps.assert_not_called()
                else:
                    self.assertNotEqual(self.m["active"], "old")
                    self.state.commit.assert_called()

    def test_compose_env_is_private_derived_and_descriptor_anchored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = State(Path(temporary), create=True)
            try:
                sandbox = local.Sandbox(state, self.m)
                with patch.object(sandbox, "guard"), patch.object(sandbox, "run") as run:
                    sandbox.compose(["build", "backend", "frontend"])
                    args = run.call_args.args[0]
                    self.assertIn(str(local.COMPOSE), args)
                    self.assertIn(sandbox.project, args)
                    self.assertIn(f"/proc/{os.getpid()}/fd/", " ".join(args))
                    self.assertNotIn(self.m["password"], " ".join(args))
                    env = Path(temporary) / "compose.env"
                    self.assertEqual(env.stat().st_mode & 0o777, 0o600)
                    self.assertIn(f"SANDBOX_PASSWORD={self.m['password']}", env.read_text())
                    self.assertNotIn("PGOPTIONS", env.read_text())
            finally:
                state.close()

    def test_initialized_volume_is_never_created_again(self) -> None:
        self.m["volume"] = {"proof": "retained"}
        with patch.object(self.sandbox, "guard"), patch.object(self.sandbox, "run") as run:
            self.sandbox.initialize_volume()
            run.assert_not_called()
        with (
            patch.object(self.sandbox, "guard", side_effect=local.LocalDatabaseError("missing")),
            patch.object(self.sandbox, "run") as run,
        ):
            with self.assertRaises(local.LocalDatabaseError):
                self.sandbox.initialize_volume()
            run.assert_not_called()

    def test_cluster_identity_change_refused_before_restore(self) -> None:
        self.m["cluster"] = "12345"
        with (
            patch.object(self.sandbox, "initialize_volume"),
            patch.object(self.sandbox, "compose"),
            patch.object(local, "SandboxPostgres") as adapter,
        ):
            adapter.return_value.sql.return_value = b"99999\n"
            with self.assertRaisesRegex(local.LocalDatabaseError, "cluster_identity_changed"):
                self.sandbox.postgres()
            self.state.commit.assert_not_called()

    def test_adapter_rechecks_container_and_reuses_task1_restore_boundary(self) -> None:
        with (
            patch.object(
                self.sandbox,
                "guard",
                return_value={"postgres": {"Id": "owned", "State": {"Running": True}}},
            ) as guard,
            patch.object(self.sandbox, "run") as run,
        ):
            adapter = local.SandboxPostgres(self.sandbox)
            self.assertIsInstance(adapter, local.LocalPostgres)
            self.assertIs(local.SandboxPostgres.validate, local.LocalPostgres.validate)
            self.assertEqual(adapter.source, "postgres")
            adapter.exec(["pg_restore", "--list"])
            self.assertEqual(
                run.call_args.args[0],
                ["exec", "-i", "-e", "PGCONNECT_TIMEOUT=10", "owned", "pg_restore", "--list"],
            )
            run.reset_mock()
            guard.return_value = {"postgres": {"Id": "replacement"}}
            with self.assertRaises(local.LocalDatabaseError):
                adapter.exec(["pg_restore", "--list"])
            run.assert_not_called()

    def test_validation_only_gets_read_only_option(self) -> None:
        with patch.object(self.sandbox, "compose") as compose:
            self.sandbox.compatible("bardi_restore_candidate")
            args = compose.call_args.args[0]
            self.assertIn("PGOPTIONS=-c default_transaction_read_only=on", args)
            self.assertIn("sandbox_check", args)
            self.assertNotIn("migrate", args)
            self.assertEqual(compose.call_args.kwargs["database"], "bardi_restore_candidate")

    def test_stop_only_stops_and_configuration_changes_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            state = State(path, create=True)
            state.commit(self.m)
            state.close()
            with (
                patch.object(local.Sandbox, "compose") as compose,
                patch.object(local.Sandbox, "reconcile_validation"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(local.main(["--state-directory", temporary, "stop"]), 0)
                compose.assert_called_once_with(["stop", "frontend", "backend", "postgres"])
            for option in (["--review-mode", "solo"], ["--backend-port", "18000"]):
                with (
                    patch.object(local.Sandbox, "start") as start,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(
                        local.main(["--state-directory", temporary, "start", *option]), 1
                    )
                    start.assert_not_called()
            self.assertEqual(json.loads((path / "manifest.json").read_text()), self.m)

    def test_compose_and_build_context_contract(self) -> None:
        text = local.COMPOSE.read_text()
        for forbidden in (
            "env_file:",
            "restart:",
            "external:",
            "docker.sock",
            "migrate",
            "--no-cache",
        ):
            self.assertNotIn(forbidden, text)
        self.assertEqual(text.count("driver: none"), 3)
        self.assertEqual(text.count('"127.0.0.1:${SANDBOX_'), 3)
        self.assertIn('BARDI_SANDBOX: "1"', text)
        self.assertNotIn("NEXT_PUBLIC", text)
        for path in (local.ROOT / ".dockerignore", local.ROOT / "frontend/.dockerignore"):
            self.assertIn(".env*", path.read_text().splitlines())
            self.assertIn("**/.env*", path.read_text().splitlines())

    def test_cli_options_ports_and_no_delete_command(self) -> None:
        for options in (
            ["--frontend-port", "0"],
            ["--backend-port", "13000"],
            ["--postgres-port", "65536"],
        ):
            with self.assertRaises(local.LocalDatabaseError):
                local.new_manifest(local.parser().parse_args(["start", *options]))
        for arguments in (["refresh", "x"], ["delete"], ["start", "--state-directory", "/tmp/x"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                local.parser().parse_args(arguments)

    def test_status_is_inspection_only_and_errors_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            absent = Path(temporary) / "missing"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(local.main(["--state-directory", str(absent), "status"]), 0)
            self.assertFalse(absent.exists())
            self.assertEqual(json.loads(output.getvalue())["status"], "not-initialized")
            path = Path(temporary)
            state = State(path, create=True)
            state.commit(self.m)
            state.close()
            before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in path.iterdir()}
            with (
                patch.object(local.Sandbox, "guard", return_value={}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(local.main(["--state-directory", str(path), "status"]), 0)
            self.assertEqual(
                before, {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in path.iterdir()}
            )
            with (
                patch.object(local.Sandbox, "guard", side_effect=ValueError("private data")),
                contextlib.redirect_stderr(io.StringIO()) as output,
            ):
                self.assertEqual(local.main(["--state-directory", str(path), "status"]), 1)
            self.assertNotIn("private data", output.getvalue())
