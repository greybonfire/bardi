"""Framework-independent validation diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

type DiagnosticPathSegment = str | int
type DiagnosticPath = tuple[DiagnosticPathSegment, ...]


@dataclass(frozen=True, slots=True)
class ValidationDiagnostic:
    """A stable machine-readable validation failure."""

    code: str
    path: DiagnosticPath
