"""Django Ninja routes for the stateless public planning contract."""

from __future__ import annotations

import logging

from django.db import DatabaseError
from django.http import HttpRequest
from knowledge.domain import KnowledgeSnapshotLoadError
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError
from ninja.parser import Parser
from planning import InconclusiveResult, InvalidResult, PlanningInput, PublicDiagnostic

from .application import execute_planning, list_active_services, project_result
from .privacy import planning_observability_metadata
from .schemas import (
    InconclusiveResponse,
    InvalidResponse,
    NavigationResponse,
    PlanningRequest,
    PlanningResponse,
)


class PrivacySafeParser(Parser):
    def parse_body(self, request: HttpRequest) -> dict[str, object]:
        try:
            parsed = super().parse_body(request)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HttpError(400, "invalid_body") from exc
        if not isinstance(parsed, dict):
            raise HttpError(400, "invalid_body")
        return parsed


logger = logging.getLogger("bardi.api")


api = NinjaAPI(
    title="Bardi public API",
    version="1.0.0",
    urls_namespace="bardi-v1",
    parser=PrivacySafeParser(),
    description=(
        "Stateless planning API. Pinned Fact derivation and redacted contradiction handling "
        "run before Procedure selection, version resolution, applicability, trust evaluation, "
        "and evidence-backed Checklist assembly."
    ),
)


@api.exception_handler(HttpError)
def body_error(request: HttpRequest, exc: HttpError):  # type: ignore[no-untyped-def]
    return api.create_response(
        request,
        {"type": "invalid", "diagnostics": [{"code": "invalid_body", "path": ["body"]}]},
        status=exc.status_code,
    )


@api.exception_handler(ValidationError)
def validation_error(request: HttpRequest, exc: ValidationError):  # type: ignore[no-untyped-def]
    diagnostics = []
    for error in exc.errors:
        error_type = str(error.get("type", "invalid_request"))
        code = (
            error_type if error_type in {"invalid_json", "object_required"} else "invalid_request"
        )
        diagnostics.append({"code": code, "path": list(error.get("loc", ()))})
    return api.create_response(request, {"type": "invalid", "diagnostics": diagnostics}, status=422)


@api.exception_handler(Exception)
def unexpected_api_error(request: HttpRequest, _exc: Exception):  # type: ignore[no-untyped-def]
    path = request.path.rstrip("/")
    if path == "/v1/planning":
        metadata = planning_observability_metadata(
            method=request.method,
            status_code=500,
            error_code="internal_error",
        )
    else:
        metadata = {
            "method": "GET" if request.method == "GET" else "POST",
            "route": "/v1/services" if path == "/v1/services" else "/v1/public",
            "status_code": 500,
            "error_code": "internal_error",
        }
    # Never log the exception object or request. The response contract is deliberately
    # stable even under DEBUG so traceback locals cannot expose anonymous Facts.
    logger.error("public api request failed", extra=metadata)
    return api.create_response(
        request,
        {"type": "invalid", "diagnostics": [{"code": "internal_error", "path": []}]},
        status=500,
    )


@api.get(
    "/services",
    response={
        200: NavigationResponse,
        429: InvalidResponse,
        500: InvalidResponse,
        503: InconclusiveResponse,
    },
)
def services(request: HttpRequest):  # type: ignore[no-untyped-def]
    try:
        return 200, list_active_services()
    except KnowledgeSnapshotLoadError:
        return 500, project_result(
            InvalidResult((PublicDiagnostic("knowledge_snapshot_invalid", ()),)), "en"
        )
    except DatabaseError:
        return 503, project_result(InconclusiveResult("knowledge_unavailable"), "en")


@api.post(
    "/planning",
    response={
        200: PlanningResponse,
        400: InvalidResponse,
        422: InvalidResponse,
        429: InvalidResponse,
        500: InvalidResponse,
        503: InconclusiveResponse,
    },
)
def planning(request: HttpRequest, payload: PlanningRequest):  # type: ignore[no-untyped-def]
    try:
        planning_input = PlanningInput(
            payload.service_id,
            dict(payload.facts),
            payload.locale,
            payload.evaluation_context.evaluation_date,
        )
        return 200, execute_planning(planning_input)
    except KnowledgeSnapshotLoadError:
        return 500, project_result(
            InvalidResult((PublicDiagnostic("knowledge_snapshot_invalid", ()),)), payload.locale
        )
    except DatabaseError:
        return 503, project_result(InconclusiveResult("knowledge_unavailable"), payload.locale)
