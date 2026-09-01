"""Deterministic settings for PostgreSQL-backed Django tests."""

# ruff: noqa: F403,F405
from .base import *

SECRET_KEY = "django-test-only-deterministic-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
DATABASES = {"default": postgres_database()}
