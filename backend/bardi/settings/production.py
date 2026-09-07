"""Fail-closed production settings for the private pilot."""

from django.core.exceptions import ImproperlyConfigured

# ruff: noqa: F403,F405
from .base import *

SECRET_KEY = required_env("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be at least 50 characters and must not use Django's insecure prefix"
    )

DEBUG = False
ALLOWED_HOSTS = required_env_list("DJANGO_ALLOWED_HOSTS")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not contain a wildcard in production")

CSRF_TRUSTED_ORIGINS = required_env_list("CSRF_TRUSTED_ORIGINS")
if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must contain HTTPS origins only")

DATABASES = {"default": postgres_database()}

# Deployment contract: a trusted reverse proxy terminates TLS, overwrites
# X-Forwarded-Proto/X-Real-IP, and is the only network path to the application.
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    default=3600,
    minimum=300,
    maximum=31_536_000,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
if SECURE_HSTS_PRELOAD and (SECURE_HSTS_SECONDS < 31_536_000 or not SECURE_HSTS_INCLUDE_SUBDOMAINS):
    raise ImproperlyConfigured(
        "HSTS preload requires at least one year and SECURE_HSTS_INCLUDE_SUBDOMAINS=true"
    )

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int(
    "DJANGO_ADMIN_SESSION_AGE_SECONDS",
    default=3600,
    minimum=300,
    maximum=43_200,
)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

OPERATIONAL_OBSERVABILITY_ENABLED = True

# Initial private-pilot abuse guard. Counters are process-local and keyed by an HMAC of
# the client address supplied by the trusted ingress; neither addresses nor request Facts
# are persisted or logged. Multi-worker deployments must add an ingress-level global cap.
PUBLIC_API_RATE_LIMIT_ENABLED = True
PUBLIC_API_RATE_LIMIT_REQUESTS = env_int(
    "PUBLIC_API_RATE_LIMIT_REQUESTS",
    default=60,
    minimum=1,
    maximum=10_000,
)
PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = env_int(
    "PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS",
    default=60,
    minimum=1,
    maximum=3600,
)
PUBLIC_API_CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
