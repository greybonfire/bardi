"""Development settings with safe, local-only defaults."""

import os

# The insecure defaults in this module are intentionally limited to local development.
# Set every value explicitly before using any deployed environment.
# ruff: noqa: F403,F405
from .base import *

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-development-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=("localhost", "127.0.0.1"))
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=("https://localhost", "https://127.0.0.1"),
)
DATABASES = {"default": postgres_database(defaults=DEVELOPMENT_DATABASE_DEFAULTS)}
