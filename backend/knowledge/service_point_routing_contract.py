"""Runtime model contract for time-bounded Service Point material."""

from __future__ import annotations

from django.db import models

from .service_point_routing import ServicePointVersion


def install_service_point_temporal_contract() -> None:
    """Make the material start boundary required in model validation and migration state."""

    field = ServicePointVersion._meta.get_field("effective_from")
    if not isinstance(field, models.DateField):
        raise TypeError("ServicePointVersion.effective_from must remain a DateField.")
    field.null = False
    field.blank = False


install_service_point_temporal_contract()

__all__ = ("install_service_point_temporal_contract",)
