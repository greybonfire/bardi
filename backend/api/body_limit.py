"""Bound planning bodies before Django Ninja accesses request.body."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

from django.core.exceptions import RequestDataTooBig
from django.http import HttpRequest, HttpResponse, JsonResponse

from .privacy import PLANNING_ROUTE

MAX_PLANNING_BODY_BYTES = 512 * 1024


def _cache_bounded_body(request: HttpRequest) -> None:
    try:
        declared_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except TypeError, ValueError:
        # Framing is the server's responsibility; still bound the exposed stream.
        declared_length = 0
    if declared_length > MAX_PLANNING_BODY_BYTES:
        raise RequestDataTooBig

    if hasattr(request, "_body"):
        if len(request._body) > MAX_PLANNING_BODY_BYTES:
            raise RequestDataTooBig
        return

    body = bytearray()
    try:
        # Loop for streams that return short reads. Never read beyond limit + 1.
        while len(body) <= MAX_PLANNING_BODY_BYTES:
            chunk = request.read(MAX_PLANNING_BODY_BYTES + 1 - len(body))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > MAX_PLANNING_BODY_BYTES:
            raise RequestDataTooBig
    finally:
        request._stream.close()

    # Mirror Django's body cache so Ninja and subsequent consumers can reread it
    # without triggering RawPostDataException after the bounded stream read.
    request._body = bytes(body)
    request._stream = BytesIO(request._body)


class PlanningBodyLimitMiddleware:
    """Keep the planning-only budget outside Ninja's eager body access/parser wrapper."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and request.path == PLANNING_ROUTE:
            code = None
            try:
                if getattr(request, "_read_started", False) and not hasattr(request, "_body"):
                    # A consumed, uncached stream cannot be safely size-checked.
                    code = "invalid_body"
                else:
                    _cache_bounded_body(request)
            except RequestDataTooBig:
                code = "body_too_large"
            except OSError:
                # Do not let stream failures reach Django's debug error renderer.
                code = "invalid_body"
            if code is not None:
                response = JsonResponse(
                    {"type": "invalid", "diagnostics": [{"code": code, "path": ["body"]}]},
                    status=413 if code == "body_too_large" else 400,
                )
                response["Cache-Control"] = "no-store"
                return response
        return self.get_response(request)
