"""Minimal liveness and PostgreSQL readiness signals."""

from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .observability import operational_observability_metadata

logger = logging.getLogger("bardi.ops")


def _no_store(response: JsonResponse) -> JsonResponse:
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def liveness(_request: HttpRequest) -> JsonResponse:
    """Prove that Django can serve a request without depending on PostgreSQL."""

    return _no_store(JsonResponse({"status": "ok"}))


@require_GET
def readiness(request: HttpRequest) -> JsonResponse:
    """Fail closed unless the application can execute a minimal PostgreSQL query."""

    database_status = "ok"
    status_code = 200
    payload: dict[str, object] = {"status": "ready", "checks": {"database": "ok"}}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise RuntimeError("unexpected readiness probe result")
    except Exception:
        database_status = "unavailable"
        status_code = 503
        payload = {"status": "not_ready", "checks": {"database": "unavailable"}}

    logger.info(
        "readiness_check",
        extra=operational_observability_metadata(
            event="readiness_check",
            method=request.method,
            route="/health/ready",
            status_code=status_code,
            database_status=database_status,
            request_id=getattr(request, "_bardi_request_id", ""),
        ),
    )
    return _no_store(JsonResponse(payload, status=status_code))
