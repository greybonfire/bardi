import importlib
import os
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase


def _production_settings() -> Any:
    """Load production settings with explicit test values, independent of the local .env."""
    values = {
        "DJANGO_SECRET_KEY": "test-production-secret-key-with-more-than-fifty-characters-12345",
        "DJANGO_ALLOWED_HOSTS": "testserver.example",
        "CSRF_TRUSTED_ORIGINS": "https://testserver.example",
        "POSTGRES_DB": "bardi_test",
        "POSTGRES_USER": "bardi_test",
        "POSTGRES_PASSWORD": "test-password",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
    }
    with patch.dict(os.environ, values):
        module = importlib.import_module("bardi.settings.production")
        return importlib.reload(module)


class SettingsTests(SimpleTestCase):
    def test_database_is_postgresql_only(self) -> None:
        engine = settings.DATABASES["default"]["ENGINE"]

        self.assertEqual(engine, "django.db.backends.postgresql")
        self.assertNotIn("sqlite", engine.lower())
        self.assertFalse(
            any("sqlite" in str(database).lower() for database in settings.DATABASES.values())
        )

    def test_built_in_admin_auth_and_session_components_are_installed(self) -> None:
        required_apps = {
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        }
        self.assertTrue(required_apps.issubset(settings.INSTALLED_APPS))

        required_middleware = {
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
        }
        self.assertTrue(required_middleware.issubset(settings.MIDDLEWARE))

    def test_standard_password_validators_are_present(self) -> None:
        validator_names = {validator["NAME"] for validator in settings.AUTH_PASSWORD_VALIDATORS}

        self.assertIn(
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
            validator_names,
        )
        self.assertIn(
            "django.contrib.auth.password_validation.MinimumLengthValidator",
            validator_names,
        )

    def test_test_settings_are_deterministic_and_safe(self) -> None:
        self.assertFalse(settings.DEBUG)
        self.assertTrue(settings.SECRET_KEY)
        self.assertTrue({"testserver", "localhost", "127.0.0.1"}.issubset(settings.ALLOWED_HOSTS))

    def test_production_security_settings_are_enabled(self) -> None:
        production = _production_settings()

        self.assertFalse(production.DEBUG)
        self.assertTrue(production.SECURE_SSL_REDIRECT)
        self.assertTrue(production.SESSION_COOKIE_SECURE)
        self.assertTrue(production.CSRF_COOKIE_SECURE)
        self.assertGreater(production.SECURE_HSTS_SECONDS, 0)
        self.assertTrue(production.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(production.SECURE_HSTS_PRELOAD)
