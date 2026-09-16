"""Stable, JSON-safe diagnostics shared by draft-pack entry points."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: tuple[str | int, ...]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "path": list(self.path), "message": self.message}


class DraftPackError(Exception):
    def __init__(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("Draft pack rejected.")

    def as_dict(self) -> dict[str, Any]:
        return {"diagnostics": [item.as_dict() for item in self.diagnostics]}
