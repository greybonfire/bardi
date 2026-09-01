"""Fail-closed production settings."""

# ruff: noqa: F403,F405
from .base import *

SECRET_KEY = required_env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = required_env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = required_env_list("CSRF_TRUSTED_ORIGINS")
DATABASES = {"default": postgres_database()}

# Keep transport/proxy topology neutral until deployment hardening selects the actual
# ingress/proxy contract. Secure cookies and browser-side protections are safe defaults;
# HTTPS redirects, HSTS, preload, and proxy SSL headers are deliberately deferred to #54.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
