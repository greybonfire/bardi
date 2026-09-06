"""Allow-listed structured operational events for the private pilot."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

OPERATIONAL_OBSERVABILITY_FIELDS = frozenset(
    {
        "event",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "database_status",
        "request_id",
    }
)
_OPERATIONAL_EVENTS = frozenset({"request_completed", "readiness_check"})
_OPERATIONAL_METHODS = frozenset({"GET", "POST", "HEAD", "OPTIONS"})
_OPERATIONAL_ROUTES = frozenset(
    {
        "/v1/planning",
        "/v1/services",
        "/health/live",
        "/health/ready",
        "/admin/*",
        "other",
    }
)
_DATABASE_STATUSES = frozenset({"ok", "unavailable", "not_checked"})
_STANDARD_LOG_RECORD_ATTRIBUTES = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


def normalize_operational_route(path: object) -> str:
    """Map request paths to a small fixed vocabulary with no user-controlled segments."""

    if not isinstance(path, str):
        return "other"
    normalized = path.rstrip("/") or "/"
    if normalized == "/v1/planning":
        return "/v1/planning"
    if normalized == "/v1/services":
        return "/v1/services"
    if normalized == "/health/live":
        return "/health/live"
    if normalized == "/health/ready":
        return "/health/ready"
    if normalized == "/admin" or normalized.startswith("/admin/"):
        return "/admin/*"
    return "other"


def _safe_request_id(value: object) -> str:
    if not isinstance(value, str) or len(value) != 32:
        return "0" * 32
    lowered = value.lower()
    if any(character not in "0123456789abcdef" for character in lowered):
        return "0" * 32
    return lowered


def operational_observability_metadata(
    *,
    event: object,
    method: object,
    route: object,
    status_code: object,
    duration_ms: object = 0,
    database_status: object = "not_checked",
    request_id: object = "",
) -> dict[str, str | int]:
    """Construct the complete scalar allow-list for one operational event."""

    safe_event = event if isinstance(event, str) and event in _OPERATIONAL_EVENTS else "request_completed"
    candidate_method = method.upper() if isinstance(method, str) else "GET"
    safe_method = candidate_method if candidate_method in _OPERATIONAL_METHODS else "GET"
    safe_route = route if isinstance(route, str) and route in _OPERATIONAL_ROUTES else "other"
    safe_status = status_code if type(status_code) is int and 100 <= status_code <= 599 else 500
    safe_duration = duration_ms if type(duration_ms) is int and 0 <= duration_ms <= 3_600_000 else 0
    safe_database_status = (
        database_status
        if isinstance(database_status, str) and database_status in _DATABASE_STATUSES
        else "not_checked"
    )
    return {
        "event": safe_event,
        "method": safe_method,
        "route": safe_route,
        "status_code": safe_status,
        "duration_ms": safe_duration,
        "database_status": safe_database_status,
        "request_id": _safe_request_id(request_id),
    }


class OperationalPrivacyFilter(logging.Filter):
    """Strip operational records to the explicit structured allow-list."""

    def filter(self, record: logging.LogRecord) -> bool:
        metadata = operational_observability_metadata(
            event=getattr(record, "event", "request_completed"),
            method=getattr(record, "method", "GET"),
            route=getattr(record, "route", "other"),
            status_code=getattr(record, "status_code", 500),
            duration_ms=getattr(record, "duration_ms", 0),
            database_status=getattr(record, "database_status", "not_checked"),
            request_id=getattr(record, "request_id", ""),
        )

        record.msg = metadata["event"]
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        for attribute in tuple(record.__dict__):
            if (
                attribute not in _STANDARD_LOG_RECORD_ATTRIBUTES
                and attribute not in OPERATIONAL_OBSERVABILITY_FIELDS
            ):
                delattr(record, attribute)
        for key, value in metadata.items():
            setattr(record, key, value)
        return True


class StructuredOperationalFormatter(logging.Formatter):
    """Emit only the vetted operational schema as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        metadata = operational_observability_metadata(
            event=getattr(record, "event", "request_completed"),
            method=getattr(record, "method", "GET"),
            route=getattr(record, "route", "other"),
            status_code=getattr(record, "status_code", 500),
            duration_ms=getattr(record, "duration_ms", 0),
            database_status=getattr(record, "database_status", "not_checked"),
            request_id=getattr(record, "request_id", ""),
        )
        payload: dict[str, str | int] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            **metadata,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


logger = logging.getLogger("bardi.ops")


class RequestObservabilityMiddleware:
    """Record coarse request completion metadata without reading bodies or query strings."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = perf_counter()
        request_id = uuid4().hex
        setattr(request, "_bardi_request_id", request_id)
        response = self.get_response(request)
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        route = normalize_operational_route(request.path)
        if route != "other":
            logger.info(
                "request_completed",
                extra=operational_observability_metadata(
                    event="request_completed",
                    method=request.method,
                    route=route,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                ),
            )
        response["X-Request-ID"] = request_id
        return response
