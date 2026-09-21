"""Database-free regression tests for the local recovery boundary."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import local_database as local


class LocalDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = MagicMock(spec=local.LocalPostgres)
        self.db.source = "bardi"
        self.db.connection.return_value = ["--host=/var/run/postgresql", "--port=5432"]
        self.db.sql.return_value = b""
        self.archive = self.directory / "input.dump"
        self.archive.write_bytes(b"PGDMPexample")

    def dump(self, args: list[str], **kwargs: object) -> bytes:
        stream = kwargs["stdout"]
        stream.write(b"PGDMPexample")  # type: ignore[attr-defined]
        return b""

    def test_streamed_private_backup(self) -> None:
        self.db.exec.side_effect = self.dump
        result = local.backup(self.db, self.directory)
        path = Path(str(result["path"]))
        self.assertEqual(path.read_bytes(), b"PGDMPexample")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result["bytes"], 12)
        self.assertFalse(list(self.directory.glob("*.partial")))
        self.assertIn("--format=custom", self.db.exec.call_args.args[0])
        self.db.validate.assert_called_once()

    def test_failure_and_interrupt_cleanup(self) -> None:
        for failure in [local.LocalDatabaseError("failed"), KeyboardInterrupt()]:
            self.db.exec.side_effect = failure
            with self.assertRaises(type(failure)):
                local.backup(self.db, self.directory)
            self.assertEqual(list(self.directory.iterdir()), [self.archive])
        self.db.exec.side_effect = self.dump
        self.db.validate.side_effect = local.LocalDatabaseError("invalid")
        with self.assertRaises(local.LocalDatabaseError):
            local.backup(self.db, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [self.archive])

    def test_publication_never_clobbers(self) -> None:
        self.db.exec.side_effect = self.dump
        with patch.object(local.os, "link", side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):
                local.backup(self.db, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [self.archive])

    def test_exclusive_partial_failure_does_not_remove_unowned_file(self) -> None:
        with (
            patch.object(local.os, "open", side_effect=FileExistsError),
            patch.object(Path, "unlink") as unlink,
        ):
            with self.assertRaises(FileExistsError):
                local.backup(self.db, self.directory)
            unlink.assert_not_called()

    def test_subprocess_receives_rewound_archive_descriptor(self) -> None:
        # Buffered Python reads can leave the underlying fd at EOF even after seek(0).
        db = object.__new__(local.LocalPostgres)
        received = []

        def consume(args: list[str], **kwargs: object) -> bytes:
            stream = kwargs["stdin"]
            received.append(os.read(stream.fileno(), 100))  # type: ignore[attr-defined]
            return b""

        with (
            self.archive.open("rb", buffering=0) as archive,
            patch.object(db, "exec", side_effect=consume),
        ):
            db.validate(archive)
            self.assertEqual(os.read(archive.fileno(), 100), b"PGDMPexample")
        self.assertEqual(received, [b"PGDMPexample", b"PGDMPexample"])

    def test_directory_guards(self) -> None:
        unsafe = self.directory / "unsafe"
        unsafe.mkdir(mode=0o755)
        # mkdir's mode is masked by the caller; this fixture must actually be unsafe.
        unsafe.chmod(0o755)
        link = self.directory / "link"
        link.symlink_to(self.directory, target_is_directory=True)
        git = self.directory / "worktree"
        git.mkdir(mode=0o700)
        (git / ".git").write_text("gitdir: elsewhere")
        for path in [unsafe, link / "backups", git / "backups", local.ROOT / "backups"]:
            with self.subTest(path=path), self.assertRaises(local.LocalDatabaseError):
                local.private_directory(path)
        with patch.object(local.os, "getuid", return_value=-1):
            with self.assertRaises(local.LocalDatabaseError):
                local.private_directory(self.directory)

    def test_ancestor_permissions_and_ownership(self) -> None:
        parent = self.directory / "parent"
        parent.mkdir()
        child = parent / "private"
        child.mkdir(mode=0o700)
        for mode in [0o777, 0o770, 0o707]:
            parent.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(local.LocalDatabaseError):
                local.backup(self.db, child)
            self.assertEqual(list(child.iterdir()), [])
        parent.chmod(0o1777)
        self.assertEqual(local.private_directory(child), child)
        # A foreign-owned sticky ancestor can still rename its children.
        real_fstat = os.fstat
        parent_inode = parent.stat().st_ino

        def foreign_owner(fd: int) -> os.stat_result:
            info = real_fstat(fd)
            if info.st_ino == parent_inode:
                fields = list(info)
                fields[4] = os.getuid() + 10000
                return os.stat_result(fields)
            return info

        with patch.object(local.os, "fstat", side_effect=foreign_owner):
            with self.assertRaises(local.LocalDatabaseError):
                local.private_directory(child)
        self.db.exec.assert_not_called()

    def test_private_nested_creation(self) -> None:
        # Work under the caller's temporary directory, including an explicit TMPDIR.
        nested = self.directory / "new" / "backups"
        self.db.exec.side_effect = self.dump
        result = local.backup(self.db, nested)
        self.assertEqual(Path(str(result["path"])).read_bytes(), b"PGDMPexample")
        self.assertEqual(nested.stat().st_mode & 0o7777, 0o700)
        self.assertEqual(nested.parent.stat().st_mode & 0o7777, 0o700)

    def test_substitution_is_anchored_and_never_reports_wrong_path(self) -> None:
        for stage in ["create", "publish", "fsync", "dump_failure"]:
            for symlink in [True, False]:
                with self.subTest(stage=stage, symlink=symlink):
                    self.check_substitution(stage, symlink)

    def check_substitution(self, stage: str, symlink: bool) -> None:
        base = self.directory / f"{stage}-{symlink}"
        base.mkdir(mode=0o700)
        original = base / "backups"
        original.mkdir(mode=0o700)
        moved = base / "moved"
        replacement = base / "replacement"
        replacement.mkdir(mode=0o700)
        name = "bardi-20000101T000000Z-fixed.dump"
        for entry in [name, name + ".partial"]:
            (replacement / entry).write_bytes(b"unrelated")
        swapped = False
        real_open, real_link, real_fsync = os.open, os.link, os.fsync

        def swap() -> None:
            nonlocal swapped
            if swapped:
                return
            swapped = True
            original.rename(moved)
            if symlink:
                original.symlink_to(replacement, target_is_directory=True)
            else:
                replacement.rename(original)

        def opening(path: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
            if stage == "create" and flags & os.O_CREAT:
                swap()
            return real_open(path, flags, mode, dir_fd=dir_fd)

        def linking(
            src: str, dst: str, *, src_dir_fd: int, dst_dir_fd: int, follow_symlinks: bool
        ) -> None:
            if stage == "publish":
                swap()
            real_link(
                src,
                dst,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )

        def syncing(fd: int) -> None:
            if stage == "fsync":
                swap()
            real_fsync(fd)

        def dumping(args: list[str], **kwargs: object) -> None:
            self.dump(args, **kwargs)
            if stage == "dump_failure":
                swap()
                raise local.LocalDatabaseError("dump failed")

        self.db.exec.side_effect = dumping
        with (
            patch.object(local.os, "open", side_effect=opening),
            patch.object(local.os, "link", side_effect=linking),
            patch.object(local.os, "fsync", side_effect=syncing),
            patch.object(local, "datetime") as clock,
            patch.object(local.uuid, "uuid4") as unique,
        ):
            clock.now.return_value = datetime(2000, 1, 1, tzinfo=UTC)
            unique.return_value.hex = "fixed"
            with self.assertRaises(local.LocalDatabaseError):
                local.backup(self.db, original)
        self.assertTrue(swapped)
        self.assertEqual(list(moved.iterdir()), [])
        unrelated = replacement if symlink else original
        self.assertEqual(
            {p.name: p.read_bytes() for p in unrelated.iterdir()},
            {name: b"unrelated", name + ".partial": b"unrelated"},
        )

    def test_actual_name_collisions_preserve_existing_entries(self) -> None:
        self.db.exec.side_effect = self.dump
        with (
            patch.object(local, "datetime") as clock,
            patch.object(local.uuid, "uuid4") as unique,
        ):
            clock.now.return_value = datetime(2000, 1, 1, tzinfo=UTC)
            unique.return_value.hex = "fixed"
            name = "bardi-20000101T000000Z-fixed.dump"
            for suffix in ["", ".partial"]:
                existing = self.directory / (name + suffix)
                existing.write_bytes(b"unrelated")
                with self.assertRaises(FileExistsError):
                    local.backup(self.db, self.directory)
                self.assertEqual(existing.read_bytes(), b"unrelated")
                self.assertEqual(set(self.directory.iterdir()), {existing, self.archive})
                existing.unlink()

    def test_restore_guards_before_create(self) -> None:
        for target in [
            "bardi",
            "postgres",
            "template0",
            "template1",
            "bardi_restore_",
            "bardi_restore_X",
            "bardi_restore_x;DROP",
            "bardi_restore_" + "x" * 60,
        ]:
            with self.subTest(target=target), self.assertRaises(local.LocalDatabaseError):
                local.restore(self.db, self.archive, target)
        self.db.source = "bardi_restore_source"
        with self.assertRaises(local.LocalDatabaseError):
            local.restore(self.db, self.archive, self.db.source)
        self.db.sql.assert_not_called()
        self.db.validate.side_effect = local.LocalDatabaseError("bad archive")
        with self.assertRaises(local.LocalDatabaseError):
            local.restore(self.db, self.archive, "bardi_restore_new")
        self.db.sql.assert_not_called()

    def test_existing_and_create_race_never_restore_or_drop(self) -> None:
        self.db.sql.return_value = b"1\n"
        with self.assertRaises(local.LocalDatabaseError):
            local.restore(self.db, self.archive, "bardi_restore_new")
        self.db.exec.assert_not_called()
        self.db.sql.reset_mock()
        self.db.sql.side_effect = [b"", local.LocalDatabaseError("duplicate")]
        with self.assertRaises(local.LocalDatabaseError):
            local.restore(self.db, self.archive, "bardi_restore_new")
        self.db.exec.assert_not_called()
        self.assertEqual(self.db.sql.call_count, 2)

    def test_restore_flags_and_failure_retains_target(self) -> None:
        result = local.restore(self.db, self.archive, "bardi_restore_new")
        self.assertEqual(result["status"], "restored_unverified")
        args = self.db.exec.call_args.args[0]
        for flag in [
            "--single-transaction",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname=bardi_restore_new",
        ]:
            self.assertIn(flag, args)
        self.assertIn("TEMPLATE template0", self.db.sql.call_args.args[0])
        self.db.sql.reset_mock()
        self.db.exec.side_effect = local.LocalDatabaseError("secret")
        with self.assertRaisesRegex(local.LocalDatabaseError, "target retained"):
            local.restore(self.db, self.archive, "bardi_restore_new")
        self.assertEqual(self.db.sql.call_count, 2)
        self.assertNotIn("DROP", str(self.db.sql.call_args_list))

    def test_input_symlink_and_nonregular_refused(self) -> None:
        link = self.directory / "link"
        link.symlink_to(self.archive)
        fifo = self.directory / "fifo"
        os.mkfifo(fifo)
        for path in [link, fifo, self.directory]:
            with self.assertRaises((OSError, local.LocalDatabaseError)):
                local.restore(self.db, path, "bardi_restore_new")
        self.db.sql.assert_not_called()

    def test_real_validator_checks_full_archive_not_just_list(self) -> None:
        db = object.__new__(local.LocalPostgres)
        with patch.object(db, "exec") as execute:
            with self.assertRaises(local.LocalDatabaseError):
                db.validate(io.BytesIO(b"bad"))
            execute.assert_not_called()
            execute.side_effect = [b"", local.LocalDatabaseError("truncated")]
            with self.assertRaises(local.LocalDatabaseError):
                db.validate(io.BytesIO(b"PGDMPtruncated"))
            self.assertEqual(execute.call_args.args[0], ["pg_restore", "--file=/dev/null"])

    def test_redacted_process_and_cli_errors(self) -> None:
        with patch.object(
            local.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["secret"], stderr=b"password hash"),
        ):
            with self.assertRaisesRegex(local.LocalDatabaseError, "details suppressed"):
                local.run(["secret"])
        with patch.object(local, "LocalPostgres", side_effect=OSError("secret")):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(local.main(["backup"]), 1)
            self.assertNotIn("secret", output.getvalue())

    def test_local_docker_and_container_identity(self) -> None:
        context = json.dumps([{"Endpoints": {"docker": {"Host": "unix:///socket"}}}]).encode()
        info = [
            {
                "Config": {
                    "Labels": {
                        "com.docker.compose.service": "postgres",
                        "com.docker.compose.project.working_dir": str(local.ROOT),
                        "com.docker.compose.project.config_files": str(local.ROOT / "compose.yaml"),
                    }
                },
                "State": {"Running": True},
            }
        ]
        with patch.dict(os.environ, {"DOCKER_HOST": "ssh://remote"}):
            with self.assertRaises(local.LocalDatabaseError):
                local.LocalPostgres()
        with patch.dict(os.environ, {"DOCKER_HOST": ""}), patch.object(local, "run") as run:
            run.return_value = context.replace(b"unix:///socket", b"tcp://remote:2375")
            with self.assertRaises(local.LocalDatabaseError):
                local.LocalPostgres()
            run.side_effect = [context, b"a" * 64, json.dumps(info).encode(), b"bardi", b"bardi"]
            db = local.LocalPostgres()
            self.assertEqual(db.source, "bardi")
            self.assertEqual(db.docker, ["docker", "--host", "unix:///socket"])
            info[0]["Config"]["Labels"]["com.docker.compose.service"] = "backend"  # type: ignore[index]
            run.side_effect = [context, b"a" * 64, json.dumps(info).encode()]
            with self.assertRaises(local.LocalDatabaseError):
                local.LocalPostgres()
