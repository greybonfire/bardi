"""Small JSON-only command adapter. File writes never replace existing paths."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError

from .errors import Diagnostic, DraftPackError
from .schema import MAX_BYTES


class JsonCommand(BaseCommand):
    # Avoid migration/system-check prose on machine stdout. Deployment checks remain
    # separate; the module enforces all permissions and database invariants.
    requires_system_checks: list[str] = []

    def actor(self, username: str) -> Any:
        user = (
            get_user_model()
            ._default_manager.filter(**{get_user_model().USERNAME_FIELD: username})
            .first()
        )
        if user is None:
            raise DraftPackError(
                (
                    Diagnostic(
                        "permission_denied",
                        ("actor",),
                        "An existing permitted staff actor is required.",
                    ),
                )
            )
        return user

    def execute_json(self, operation: Any, output: str | None = None) -> None:
        try:
            result = operation()
            text = json.dumps(result, ensure_ascii=False, sort_keys=True, cls=DjangoJSONEncoder)
            if output is not None:
                self._write(output, text + "\n")
                text = json.dumps({"status": "written", "output": output})
            self.stdout.write(text)
        except DraftPackError as exc:
            self.stdout.write(json.dumps({"status": "error", **exc.as_dict()}, ensure_ascii=False))
            raise CommandError("Draft pack rejected.") from None
        except DatabaseError:
            self.stdout.write(
                json.dumps(
                    {
                        "status": "error",
                        "diagnostics": [
                            {
                                "code": "database_error",
                                "path": [],
                                "message": "Database operation failed; check configuration.",
                            }
                        ],
                    }
                )
            )
            raise CommandError("Draft pack database operation failed.") from None
        except OSError:
            self.stdout.write(
                json.dumps(
                    {
                        "status": "error",
                        "diagnostics": [
                            {
                                "code": "file_error",
                                "path": [],
                                "message": "Could not read or safely create the requested file.",
                            }
                        ],
                    }
                )
            )
            raise CommandError("Draft pack file operation failed.") from None

    @staticmethod
    def read_pack(filename: str) -> bytes:
        with Path(filename).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise DraftPackError((Diagnostic("size_limit", (), "Draft pack exceeds 8 MiB."),))
        return raw

    @staticmethod
    def _write(filename: str, text: str) -> None:
        path = Path(filename)
        # Hard-link publication is atomic and fails on existing files or symlinks.
        fd, temporary = tempfile.mkstemp(prefix=".draft-pack-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            os.unlink(temporary)
