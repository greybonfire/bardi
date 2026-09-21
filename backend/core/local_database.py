"""Local-only Compose backup/restore. Archives are trusted, private plaintext."""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parents[2]


class LocalDatabaseError(Exception):
    """A deliberately data-free operator error."""


def run(
    args: list[str], *, stdin: BinaryIO | None = None, stdout: BinaryIO | int = subprocess.PIPE
) -> bytes:
    try:
        result = subprocess.run(
            args,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            cwd=ROOT,
            timeout=600,
            check=True,
        )
        return result.stdout if isinstance(result.stdout, bytes) else b""
    except (OSError, subprocess.SubprocessError) as from_error:
        raise LocalDatabaseError("local command failed (details suppressed)") from from_error


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
        raise LocalDatabaseError("unsafe database configuration or identifier")
    return value


class LocalPostgres:
    def __init__(self) -> None:
        host = os.environ.get("DOCKER_HOST", "")
        if host and not host.startswith("unix:///"):
            raise LocalDatabaseError("only local Unix-socket Docker endpoints are supported")
        context = json.loads(run(["docker", "context", "inspect"]))
        endpoint = context[0]["Endpoints"]["docker"]["Host"]
        if not endpoint.startswith("unix:///"):
            raise LocalDatabaseError("remote Docker context refused")
        # Pin the inspected endpoint, regardless of subsequent context changes.
        self.docker = ["docker", "--host", host or endpoint]
        compose = self.docker + [
            "compose",
            "--project-directory",
            str(ROOT),
            "-f",
            str(ROOT / "compose.yaml"),
        ]
        container = run(compose + ["ps", "-q", "postgres"]).decode().strip()
        if not re.fullmatch(r"[a-f0-9]{12,64}", container):
            raise LocalDatabaseError("exactly one running Compose postgres is required")
        info = json.loads(run(self.docker + ["inspect", container]))[0]
        labels = info["Config"]["Labels"]
        if (
            labels.get("com.docker.compose.service") != "postgres"
            or Path(labels.get("com.docker.compose.project.working_dir", "")) != ROOT
            or str(ROOT / "compose.yaml")
            not in labels.get("com.docker.compose.project.config_files", "").split(",")
            or not info["State"]["Running"]
        ):
            raise LocalDatabaseError("container is not this repository's running postgres")
        self.container = container
        self.source = identifier(self.exec(["printenv", "POSTGRES_DB"]).decode().strip())
        self.user = identifier(self.exec(["printenv", "POSTGRES_USER"]).decode().strip())

    def exec(
        self,
        args: list[str],
        *,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | int = subprocess.PIPE,
    ) -> bytes:
        return run(
            self.docker + ["exec", "-i", "-e", "PGCONNECT_TIMEOUT=10", self.container] + args,
            stdin=stdin,
            stdout=stdout,
        )

    def connection(self) -> list[str]:
        return ["--host=/var/run/postgresql", "--port=5432", f"--username={self.user}"]

    def sql(self, sql: str) -> bytes:
        return self.exec(
            [
                "psql",
                *self.connection(),
                "--dbname=postgres",
                "-XAt",
                "--set=ON_ERROR_STOP=1",
                "--command",
                sql,
            ]
        )

    def validate(self, archive: BinaryIO) -> None:
        archive.seek(0)
        if archive.read(5) != b"PGDMP":
            raise LocalDatabaseError("not a PostgreSQL custom archive")
        archive.seek(0)
        self.exec(["pg_restore", "--list"], stdin=archive, stdout=subprocess.DEVNULL)
        # Listing alone does not detect truncated table-data blocks.
        archive.seek(0)
        self.exec(["pg_restore", "--file=/dev/null"], stdin=archive, stdout=subprocess.DEVNULL)
        archive.seek(0)


def open_private_directory(path: Path, *, create: bool = True) -> tuple[Path, int]:
    """Walk from / without following links; caller owns the returned descriptor.

    Root and our uid are trusted. Writable ancestors require sticky protection:
    every child is also trusted-owned, so another uid cannot rename it there.
    """
    path = path.expanduser().absolute()
    if ".." in path.parts:
        raise LocalDatabaseError("parent directory traversal refused")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    current = Path("/")
    try:
        for component in (*path.parts[1:], None):
            info = os.fstat(fd)
            if info.st_uid not in {0, os.getuid()} or (
                info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX
            ):
                raise LocalDatabaseError("replaceable backup directory ancestor refused")
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise LocalDatabaseError("backup directory must be outside Git worktrees")
            if current == ROOT:
                raise LocalDatabaseError("backup directory must be outside Git worktrees")
            if component is None:
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise LocalDatabaseError("backup directory must be owned by you with mode 0700")
                return path, fd
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                child = os.open(component, flags, dir_fd=fd)
            except OSError as error:
                raise LocalDatabaseError(
                    "backup directory changed or is not a real directory"
                ) from error
            os.close(fd)
            fd = child
            current /= component
    except BaseException:
        os.close(fd)
        raise
    raise AssertionError("unreachable")


def private_directory(path: Path) -> Path:
    path, fd = open_private_directory(path)
    os.close(fd)
    return path


def backup(db: LocalPostgres, directory: Path) -> dict[str, str | int]:
    directory, directory_fd = open_private_directory(directory)
    name = f"bardi-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}.dump"
    final = directory / name
    partial = name + ".partial"
    published = False
    created = False
    try:
        fd = os.open(
            partial,
            os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        created = True
        # Unbuffered: subprocess stdin must see the same offset as Python validation.
        with os.fdopen(fd, "w+b", buffering=0) as stream:
            os.fchmod(stream.fileno(), 0o600)
            db.exec(
                [
                    "pg_dump",
                    *db.connection(),
                    f"--dbname={db.source}",
                    "--format=custom",
                    "--lock-wait-timeout=10000",
                ],
                stdout=stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
            db.validate(stream)
            size = os.fstat(stream.fileno()).st_size
        os.link(
            partial,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )  # Atomic no-clobber publication in the pinned directory.
        published = True
        os.unlink(partial, dir_fd=directory_fd)
        created = False
        os.fsync(directory_fd)
        # Do not report a name now pointing at an unrelated replacement directory.
        _, check_fd = open_private_directory(directory, create=False)
        try:
            if not os.path.samestat(os.fstat(directory_fd), os.fstat(check_fd)):
                raise LocalDatabaseError("backup directory changed during backup")
        finally:
            os.close(check_fd)
        return {
            "status": "backup_complete",
            "path": str(final),
            "source_database": db.source,
            "bytes": size,
        }
    except BaseException:
        if published:
            os.unlink(name, dir_fd=directory_fd)
        raise
    finally:
        try:
            if created:
                os.unlink(partial, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)


def restore(db: LocalPostgres, path: Path, target: str) -> dict[str, str]:
    identifier(target)
    if not re.fullmatch(r"bardi_restore_[a-z0-9_]+", target) or target == db.source:
        raise LocalDatabaseError("target must be a fresh bardi_restore_SUFFIX, never the source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb", buffering=0) as archive:
        if not stat.S_ISREG(os.fstat(archive.fileno()).st_mode):
            raise LocalDatabaseError("archive must be a regular file")
        db.validate(archive)
        if db.sql(f"SELECT 1 FROM pg_database WHERE datname = '{target}'").strip():
            raise LocalDatabaseError("target already exists; choose a fresh database")
        try:
            db.sql(f'CREATE DATABASE "{target}" TEMPLATE template0')
        except BaseException as error:
            raise LocalDatabaseError(
                "target creation failed/unverified; any existing target is retained"
            ) from error
        try:
            db.exec(
                [
                    "pg_restore",
                    *db.connection(),
                    f"--dbname={target}",
                    "--single-transaction",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                ],
                stdin=archive,
                stdout=subprocess.DEVNULL,
            )
        except BaseException as error:
            raise LocalDatabaseError(
                "restore failed/unverified; new target retained for manual inspection"
            ) from error
    return {"status": "restored_unverified", "database": target}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backup").add_argument(
        "--directory", type=Path, default=Path.home() / ".local/state/bardi/backups"
    )
    restoring = sub.add_parser("restore")
    restoring.add_argument("archive", type=Path)
    restoring.add_argument("--database", required=True)
    args = parser.parse_args(argv)
    try:
        db = LocalPostgres()
        result = (
            backup(db, args.directory)
            if args.command == "backup"
            else restore(db, args.archive, args.database)
        )
        print(json.dumps(result))
        return 0
    except LocalDatabaseError as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
    except OSError, ValueError, KeyError, IndexError, KeyboardInterrupt:
        print(
            '{"status":"failed","error":"local operation failed or interrupted"}', file=sys.stderr
        )
    return 1
