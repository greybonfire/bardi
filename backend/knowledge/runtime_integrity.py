"""Runtime integrity hooks installed after the complete knowledge model graph loads."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import EvidenceLink


def install_evidence_identity_validation() -> None:
    """Preserve EvidenceLink semantic-id validation after dynamic owner installers replace clean."""

    current_clean = EvidenceLink.clean
    if getattr(current_clean, "_validates_semantic_identity", False):
        return

    def clean(link: EvidenceLink) -> None:
        current_clean(link)
        if link.semantic_id and not link.semantic_id.strip():
            raise ValidationError({"semantic_id": "Evidence identity cannot be whitespace."})

    clean._validates_semantic_identity = True  # type: ignore[attr-defined]
    EvidenceLink.clean = clean  # type: ignore[assignment]


def install_passport_renewal_integrity_verification() -> None:
    """Make every passport-renewal importer call verify the complete imported semantic state."""

    from .importers import passport_renewal
    from .importers.passport_renewal_integrity import verify_passport_renewal_import

    current = passport_renewal.import_passport_renewal
    if getattr(current, "_verifies_import_integrity", False):
        return

    @wraps(current)
    @transaction.atomic
    def verified_import(*args: Any, **kwargs: Any) -> Any:
        version = current(*args, **kwargs)
        verify_passport_renewal_import(version)
        return version

    verified_import._verifies_import_integrity = True  # type: ignore[attr-defined]
    passport_renewal.import_passport_renewal = cast(Callable[..., Any], verified_import)


__all__ = (
    "install_evidence_identity_validation",
    "install_passport_renewal_integrity_verification",
)
