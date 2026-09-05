from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parents[2]


def database_from_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use postgres:// or postgresql://")
    options = parse_qs(parsed.query)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or 5432,
        "OPTIONS": {key: values[-1] for key, values in options.items()},
    }


def postgres_database(*, defaults: Mapping[str, str] | None = None) -> dict[str, object]:
    url = os.getenv("DATABASE_URL")
    if url:
        return database_from_url(url)
    values = dict(defaults or {})
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", values.get("NAME", "bardi")),
        "USER": os.getenv("POSTGRES_USER", values.get("USER", "bardi")),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", values.get("PASSWORD", "bardi")),
        "HOST": os.getenv("POSTGRES_HOST", values.get("HOST", "localhost")),
        "PORT": int(os.getenv("POSTGRES_PORT", values.get("PORT", "5432"))),
    }


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-only-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host]
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
    "knowledge.apps.KnowledgeConfig",
    "api.apps.ApiConfig",
]

# Mandatory feature-specific publication readiness gates extend the non-replaceable
# structural core defined by knowledge.publication.
PROCEDURE_VERSION_PUBLICATION_GATES = (
    "knowledge.fees.FeePublicationGate",
    "knowledge.eligibility_bases.EligibilityBasisPublicationGate",
    "knowledge.procedure_dependencies.ProcedureDependencyPublicationGate",
    "knowledge.service_point_routing.ServicePointRoutingPublicationGate",
    "knowledge.evidence_workflow.EvidenceWorkflowPublicationGate",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bardi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "bardi.wsgi.application"
ASGI_APPLICATION = "bardi.asgi.application"

DATABASES = {"default": postgres_database()}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "safe": {
            "format": "{levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "safe",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}
