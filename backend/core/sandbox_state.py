"""Small descriptor-anchored private sandbox manifest; no recovery journal."""

import fcntl
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any

from core.local_database import LocalDatabaseError, open_private_directory


class State:
    def __init__(self, path: Path, *, create: bool = False) -> None:
        self.path, self.fd = open_private_directory(path, create=create)
        self.lock = -1
        try:
            self.lock = self.open("lock", os.O_RDWR | (os.O_CREAT if create else 0))
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.lock >= 0:
            os.close(self.lock)
        os.close(self.fd)

    def open(self, name: str, flags: int) -> int:
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self.fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
        ):
            os.close(fd)
            raise LocalDatabaseError("unsafe_private_file")
        return fd

    def verify_path(self) -> None:
        lock_info = os.stat("lock", dir_fd=self.fd, follow_symlinks=False)
        if not os.path.samestat(lock_info, os.fstat(self.lock)) or lock_info.st_nlink != 1:
            raise LocalDatabaseError("state_lock_changed")
        _, fd = open_private_directory(self.path, create=False)
        try:
            if not os.path.samestat(os.fstat(fd), os.fstat(self.fd)):
                raise LocalDatabaseError("state_directory_changed")
        finally:
            os.close(fd)

    def read(self) -> dict[str, Any] | None:
        try:
            fd = self.open("manifest.json", os.O_RDONLY)
        except FileNotFoundError:
            return None
        with os.fdopen(fd) as stream:
            result: dict[str, Any] = json.load(stream)
        return result

    def replace(self, name: str, content: str) -> None:
        self.verify_path()
        try:
            fd = self.open(name, os.O_RDONLY)
        except FileNotFoundError:
            pass
        else:
            os.close(fd)
        temporary = f".{uuid.uuid4().hex}.tmp"
        fd = self.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self.verify_path()
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def commit(self, manifest: dict[str, Any]) -> None:
        self.replace("manifest.json", json.dumps(manifest))
