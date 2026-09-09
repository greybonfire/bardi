"""Detached, lightweight reads for public Service navigation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Service


@dataclass(frozen=True, slots=True)
class ServiceNavigationEntry:
    """The only persisted fields needed to render Service navigation."""

    semantic_id: str
    text_ar: str
    text_en: str


def load_active_service_navigation() -> tuple[ServiceNavigationEntry, ...]:
    """Load active Services without materializing any planning knowledge."""

    rows = (
        Service.objects.filter(is_active=True)
        .order_by("semantic_id")
        .values_list("semantic_id", "text_ar", "text_en")
    )
    entries = tuple(ServiceNavigationEntry(*row) for row in rows)
    return tuple(sorted(entries, key=lambda entry: entry.semantic_id))
