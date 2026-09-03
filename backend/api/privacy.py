"""Fail-closed logging safeguards for anonymous planning requests."""

from __future__ import annotations

import logging
from collections.abc import Mapping

PLANNING_ROUTE = "/v1/planning"
PLANNING_OBSERVABILITY_FIELDS = frozenset({"method", "route", "status_code", "error_code"})
PLANNING_ERROR_CODES = frozenset(
    {
        "internal_error",
        "knowledge_snapshot_invalid",
        "knowledge_unavailable",
        "request_error",
    }
)

# Attributes created by logging.LogRecord itself. Everything else is application or
# framework data and is removed from planning records unless explicitly allowed above.
_STANDARD_LOG_RECORD_ATTRIBUTES = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


def planning_observability_metadata(
    *, method: object, status_code: object, error_code: object
) -> dict[str, str | int]:
    """Build the complete, coarse planning event metadata allow-list.

    Deliberately, this API has no parameter for a request, body, Fact, DTO, trace, or
    exception. Values are normalized too, so even misuse cannot turn an allow-listed
    field into a channel for arbitrary sensitive text.
    """

    candidate_method = method.upper() if type(method) is str else "POST"
    safe_method = candidate_method if candidate_method == "POST" else "POST"
    safe_status = status_code if type(status_code) is int and 100 <= status_code <= 599 else 500
    safe_code = (
        error_code
        if type(error_code) is str and error_code in PLANNING_ERROR_CODES
        else "internal_error"
    )
    return {
        "method": safe_method,
        "route": PLANNING_ROUTE,
        "status_code": safe_status,
        "error_code": safe_code,
    }


def _planning_request_details(record: logging.LogRecord) -> tuple[bool, str]:
    request = getattr(record, "request", None)
    request_path = getattr(request, "path", "") or getattr(request, "path_info", "")
    method = getattr(request, "method", "POST")

    fixed_route = getattr(record, "route", "")
    explicit_path = getattr(record, "path", "") or getattr(record, "request_path", "")
    candidates: list[object] = [request_path, fixed_route, explicit_path]
    if isinstance(record.args, Mapping):
        candidates.extend(record.args.values())
    elif isinstance(record.args, tuple):
        candidates.extend(record.args)

    is_planning = any(
        isinstance(candidate, str) and PLANNING_ROUTE in candidate for candidate in candidates
    )
    return is_planning, method if isinstance(method, str) else "POST"


class PlanningPrivacyFilter(logging.Filter):
    """Reduce planning records to the explicit coarse observability allow-list."""

    def filter(self, record: logging.LogRecord) -> bool:
        is_planning, request_method = _planning_request_details(record)
        if not is_planning:
            return True

        metadata = planning_observability_metadata(
            method=getattr(record, "method", request_method),
            status_code=getattr(record, "status_code", 500),
            error_code=getattr(record, "error_code", "request_error"),
        )

        # Rewrite before deleting extras. The fixed format cannot invoke repr/str on an
        # application object and contains exactly the allow-listed scalar values.
        record.msg = "%s %s %s %s"
        record.args = (
            metadata["method"],
            metadata["route"],
            metadata["status_code"],
            metadata["error_code"],
        )
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None

        for attribute in tuple(record.__dict__):
            if (
                attribute not in _STANDARD_LOG_RECORD_ATTRIBUTES
                and attribute not in PLANNING_OBSERVABILITY_FIELDS
            ):
                delattr(record, attribute)
        # ``request`` is conventionally an extra, but be explicit about the important
        # invariant even if logging internals add it to their standard fields one day.
        if hasattr(record, "request"):
            delattr(record, "request")
        for key, value in metadata.items():
            setattr(record, key, value)
        return True
