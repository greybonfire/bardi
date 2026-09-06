"""Small privacy-safe abuse guard for the initial private pilot."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

_PUBLIC_API_PREFIX = "/v1/"
_DEFAULT_LIMIT = 60
_DEFAULT_WINDOW_SECONDS = 60

_lock = Lock()
_buckets: dict[tuple[str, str, int], int] = {}
_last_prune_window: int | None = None


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    limited: bool
    retry_after_seconds: int


def _positive_int(value: object, *, default: int) -> int:
    return value if type(value) is int and value > 0 else default


def _scope(path: object) -> str:
    if not isinstance(path, str):
        return "public"
    normalized = path.rstrip("/")
    if normalized == "/v1/planning":
        return "planning"
    if normalized == "/v1/services":
        return "services"
    return "public"


def _client_identifier(request: HttpRequest) -> str:
    """Return an ephemeral HMAC identifier without retaining the raw client address."""

    header_name = getattr(settings, "PUBLIC_API_CLIENT_IP_HEADER", "")
    raw_value: object = None
    if isinstance(header_name, str) and header_name:
        raw_value = request.META.get(header_name)
    if not isinstance(raw_value, str) or not raw_value.strip():
        raw_value = request.META.get("REMOTE_ADDR", "unknown")

    raw_client = raw_value if isinstance(raw_value, str) else "unknown"
    # X-Real-IP is the production contract, but accepting the first token also keeps a
    # deliberately configured X-Forwarded-For header bounded and deterministic.
    normalized_client = raw_client.split(",", 1)[0].strip()[:128] or "unknown"
    secret = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(
        secret,
        normalized_client.encode("utf-8", errors="replace"),
        hashlib.sha256,
    ).hexdigest()


def evaluate_rate_limit(request: HttpRequest, *, now: float | None = None) -> RateLimitDecision:
    """Evaluate one public request against a fixed window without touching its body."""

    if getattr(settings, "PUBLIC_API_RATE_LIMIT_ENABLED", False) is not True:
        return RateLimitDecision(limited=False, retry_after_seconds=0)

    limit = _positive_int(
        getattr(settings, "PUBLIC_API_RATE_LIMIT_REQUESTS", _DEFAULT_LIMIT),
        default=_DEFAULT_LIMIT,
    )
    window_seconds = _positive_int(
        getattr(settings, "PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS", _DEFAULT_WINDOW_SECONDS),
        default=_DEFAULT_WINDOW_SECONDS,
    )
    current = time.monotonic() if now is None else now
    window_id = int(current // window_seconds)
    retry_after = max(1, math.ceil(window_seconds - (current % window_seconds)))
    key = (_client_identifier(request), _scope(request.path), window_id)

    global _last_prune_window
    with _lock:
        if _last_prune_window != window_id:
            stale_before = window_id - 1
            for existing_key in tuple(_buckets):
                if existing_key[2] < stale_before:
                    del _buckets[existing_key]
            _last_prune_window = window_id

        count = _buckets.get(key, 0) + 1
        _buckets[key] = count

    return RateLimitDecision(limited=count > limit, retry_after_seconds=retry_after)


def reset_rate_limit_state() -> None:
    """Clear process-local counters. Intended for deterministic tests and worker startup."""

    global _last_prune_window
    with _lock:
        _buckets.clear()
        _last_prune_window = None


class PublicApiRateLimitMiddleware:
    """Bound public API bursts without persisting requests, Facts, or client addresses."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith(_PUBLIC_API_PREFIX):
            decision = evaluate_rate_limit(request)
            if decision.limited:
                response = JsonResponse(
                    {
                        "type": "invalid",
                        "diagnostics": [{"code": "rate_limited", "path": []}],
                    },
                    status=429,
                )
                response["Retry-After"] = str(decision.retry_after_seconds)
                response["Cache-Control"] = "no-store"
                return response
        return self.get_response(request)
