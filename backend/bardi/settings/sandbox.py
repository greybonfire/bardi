"""Generated local sandbox configuration, with every production publication gate."""

import re

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import postgres_database, required_env

if required_env("BARDI_SANDBOX") != "1":
    raise ImproperlyConfigured("sandbox_marker_required")
SANDBOX_ID = required_env("BARDI_SANDBOX_ID")
if not re.fullmatch(r"[a-f0-9]{32}", SANDBOX_ID):
    raise ImproperlyConfigured("invalid_sandbox_identity")
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
PROCEDURE_VERSION_REVIEW_MODE = required_env("PROCEDURE_VERSION_REVIEW_MODE")
if PROCEDURE_VERSION_REVIEW_MODE not in {"solo", "independent"}:
    raise ImproperlyConfigured("invalid_sandbox_review_mode")
DATABASES = {"default": postgres_database()}
if (
    DATABASES["default"]["HOST"] != "postgres"
    or DATABASES["default"]["PORT"] != "5432"
    or DATABASES["default"]["USER"] != "sandbox"
    or not re.fullmatch(r"bardi_restore_[a-f0-9]{32}", DATABASES["default"]["NAME"])
):
    raise ImproperlyConfigured("invalid_sandbox_database")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "backend"]
CSRF_TRUSTED_ORIGINS = []
SESSION_COOKIE_NAME = f"bardi_sandbox_{SANDBOX_ID}_session"
CSRF_COOKIE_NAME = f"bardi_sandbox_{SANDBOX_ID}_csrf"
ROOT_URLCONF = "bardi.sandbox_urls"
