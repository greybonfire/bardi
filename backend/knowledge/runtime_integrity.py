"""Runtime integrity hooks for production importer verification."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from django.db import transaction


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


def install_national_id_renewal_integrity_verification() -> None:
    """Make every National ID-renewal importer call verify the imported semantic state."""

    from .importers import national_id_renewal
    from .importers.national_id_renewal_integrity import verify_national_id_renewal_import

    current = national_id_renewal.import_national_id_renewal
    if getattr(current, "_verifies_import_integrity", False):
        return

    @wraps(current)
    @transaction.atomic
    def verified_import(*args: Any, **kwargs: Any) -> Any:
        version = current(*args, **kwargs)
        verify_national_id_renewal_import(version)
        return version

    verified_import._verifies_import_integrity = True  # type: ignore[attr-defined]
    national_id_renewal.import_national_id_renewal = cast(Callable[..., Any], verified_import)


def install_temporary_family_exemption_integrity_verification() -> None:
    """Make every temporary family-exemption import verify its complete semantic state."""

    from .importers import temporary_family_exemption
    from .importers.temporary_family_exemption_integrity import (
        verify_temporary_family_exemption_import,
    )

    current = temporary_family_exemption.import_temporary_family_exemption
    if getattr(current, "_verifies_import_integrity", False):
        return

    @wraps(current)
    @transaction.atomic
    def verified_import(*args: Any, **kwargs: Any) -> Any:
        versions = current(*args, **kwargs)
        verify_temporary_family_exemption_import(versions)
        return versions

    verified_import._verifies_import_integrity = True  # type: ignore[attr-defined]
    temporary_family_exemption.import_temporary_family_exemption = cast(
        Callable[..., Any], verified_import
    )


__all__ = (
    "install_national_id_renewal_integrity_verification",
    "install_passport_renewal_integrity_verification",
    "install_temporary_family_exemption_integrity_verification",
)
