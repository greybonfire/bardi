"""Shared settings for the Bardi Django project."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from django.core.exceptions import ImproperlyConfigured


def env_bool(name: str, *, default: bool = False) -> bool:
    """Read a boolean environment variable with an explicit accepted vocabulary."""
    value = os.environ.get(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be one of 1, 0, true, false, yes, no, on, or off")


def env_list(name: str, *, default: Sequence[str] = ()) -> list[str]:
    """Read a comma-separated environment variable as a list of non-empty values."""
    value = os.environ.get(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def required_env(name: str) -> str:
    """Read a required, non-blank environment variable."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ImproperlyConfigured(f"{name} must be set")
    return value


def required_env_list(name: str) -> list[str]:
    """Read a required comma-separated environment variable."""
    values = env_list(name)
    if not values:
        raise ImproperlyConfigured(f"{name} must contain at least one value")
    return values


def postgres_database(*, defaults: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a PostgreSQL connection dictionary, optionally with local defaults."""
    values: dict[str, str] = {}
    for name in (
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    ):
        value = os.environ.get(name)
        if value is None and defaults is not None:
            value = defaults.get(name)
        if value is None or not value.strip():
            raise ImproperlyConfigured(f"{name} must be set for PostgreSQL")
        values[name] = value

    try:
        port = int(values["POSTGRES_PORT"])
    except ValueError as exc:
        raise ImproperlyConfigured("POSTGRES_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ImproperlyConfigured("POSTGRES_PORT must be between 1 and 65535")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": values["POSTGRES_DB"],
        "USER": values["POSTGRES_USER"],
        "PASSWORD": values["POSTGRES_PASSWORD"],
        "HOST": values["POSTGRES_HOST"],
        "PORT": values["POSTGRES_PORT"],
    }


# These values let interactive development start after copying .env.example. The
# production and test overlays deliberately replace this database configuration.
DEVELOPMENT_DATABASE_DEFAULTS = {
    "POSTGRES_DB": "bardi",
    "POSTGRES_USER": "bardi",
    "POSTGRES_PASSWORD": "bardi-development-only",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
}

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-development-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

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
WSGI_APPLICATION = "bardi.wsgi.application"
ASGI_APPLICATION = "bardi.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": postgres_database(defaults=DEVELOPMENT_DATABASE_DEFAULTS)}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "planning_privacy": {"()": "api.privacy.PlanningPrivacyFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["planning_privacy"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "filters": ["planning_privacy"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "filters": ["planning_privacy"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "filters": ["planning_privacy"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "filters": ["planning_privacy"],
            "level": "WARNING",
            "propagate": False,
        },
        "bardi.api": {
            "handlers": ["console"],
            "filters": ["planning_privacy"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
