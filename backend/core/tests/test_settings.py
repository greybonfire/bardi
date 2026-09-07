import importlib
import os
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

_PRODUCTION_ENV = {
    "DJANGO_SECRET_KEY": "test-production-secret-key-with-more-than-fifty-characters-12345",
    "DJANGO_ALLOWED_HOSTS": "testserver.example",
    "CSRF_TRUSTED_ORIGINS": "https://testserver.example",
    "POSTGRES_DB": "bardi_test",
    "POSTGRES_USER": "bardi_test",
    "POSTGRES_PASSWORD": "test-password",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
}


def _development_settings() -> Any:
    with patch.dict(os.environ, {"DJANGO_DEBUG": "true"}):
        module = importlib.import_module("bardi.settings.development")
        return importlib.reload(module)


def _production_settings() -> Any:
    """Load production settings with explicit test values, independent of the local .env."""
    with patch.dict(os.environ, _PRODUCTION_ENV, clear=True):
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
            "core.observability.RequestObservabilityMiddleware",
            "api.rate_limit.PublicApiRateLimitMiddleware",
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
        self.assertFalse(settings.PUBLIC_API_RATE_LIMIT_ENABLED)
        self.assertFalse(settings.OPERATIONAL_OBSERVABILITY_ENABLED)

    def test_development_and_production_share_fail_closed_planning_logging(self) -> None:
        relevant = {"django", "django.request", "django.server", "django.security", "bardi.api"}
        for configured in (_development_settings(), _production_settings()):
            with self.subTest(settings_module=configured.__name__):
                logging_config = configured.LOGGING
                self.assertEqual(
                    logging_config["filters"]["planning_privacy"]["()"],
                    "api.privacy.PlanningPrivacyFilter",
                )
                self.assertEqual(
                    logging_config["handlers"]["console"]["filters"], ["planning_privacy"]
                )
                self.assertEqual(logging_config["root"]["handlers"], ["console"])
                for logger_name in relevant:
                    logger = logging_config["loggers"][logger_name]
                    self.assertEqual(logger["handlers"], ["console"])
                    self.assertEqual(logger["filters"], ["planning_privacy"])
                    self.assertFalse(logger["propagate"])

                self.assertEqual(
                    logging_config["filters"]["operational_privacy"]["()"],
                    "core.observability.OperationalPrivacyFilter",
                )
                self.assertEqual(
                    logging_config["handlers"]["operational_console"]["formatter"],
                    "operational_json",
                )
                self.assertEqual(
                    logging_config["loggers"]["bardi.ops"]["handlers"],
                    ["operational_console"],
                )
                self.assertFalse(logging_config["loggers"]["bardi.ops"]["propagate"])

        self.assertTrue(_development_settings().DEBUG)
        self.assertFalse(_production_settings().DEBUG)

    def test_production_required_configuration_fails_closed(self) -> None:
        module = importlib.import_module("bardi.settings.production")
        required = (
            "DJANGO_SECRET_KEY",
            "DJANGO_ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
        )
        try:
            for missing in required:
                with self.subTest(missing=missing):
                    values = dict(_PRODUCTION_ENV)
                    del values[missing]
                    with (
                        patch.dict(os.environ, values, clear=True),
                        self.assertRaises(ImproperlyConfigured),
                    ):
                        importlib.reload(module)
        finally:
            _production_settings()

    def test_production_rejects_weak_host_and_transport_configuration(self) -> None:
        module = importlib.import_module("bardi.settings.production")
        invalid_overrides = (
            {"DJANGO_SECRET_KEY": "too-short"},
            {"DJANGO_ALLOWED_HOSTS": "*"},
            {"CSRF_TRUSTED_ORIGINS": "http://testserver.example"},
            {"DJANGO_SECURE_HSTS_SECONDS": "0"},
            {"PUBLIC_API_RATE_LIMIT_REQUESTS": "0"},
        )
        try:
            for overrides in invalid_overrides:
                with self.subTest(overrides=overrides):
                    values = {**_PRODUCTION_ENV, **overrides}
                    with (
                        patch.dict(os.environ, values, clear=True),
                        self.assertRaises(ImproperlyConfigured),
                    ):
                        importlib.reload(module)
        finally:
            _production_settings()

    def test_production_security_and_private_pilot_controls_are_enabled(self) -> None:
        production = _production_settings()

        self.assertFalse(production.DEBUG)
        self.assertNotIn("*", production.ALLOWED_HOSTS)
        self.assertTrue(
            all(origin.startswith("https://") for origin in production.CSRF_TRUSTED_ORIGINS)
        )

        self.assertTrue(production.SECURE_SSL_REDIRECT)
        self.assertEqual(
            production.SECURE_PROXY_SSL_HEADER,
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )
        self.assertGreaterEqual(production.SECURE_HSTS_SECONDS, 300)
        self.assertFalse(production.SECURE_HSTS_PRELOAD)
        self.assertTrue(production.SESSION_COOKIE_SECURE)
        self.assertTrue(production.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(production.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(production.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertLessEqual(production.SESSION_COOKIE_AGE, 43_200)
        self.assertTrue(production.CSRF_COOKIE_SECURE)
        self.assertTrue(production.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(production.SECURE_REFERRER_POLICY, "same-origin")
        self.assertEqual(production.SECURE_CROSS_ORIGIN_OPENER_POLICY, "same-origin")
        self.assertEqual(production.X_FRAME_OPTIONS, "DENY")

        self.assertTrue(production.PUBLIC_API_RATE_LIMIT_ENABLED)
        self.assertGreater(production.PUBLIC_API_RATE_LIMIT_REQUESTS, 0)
        self.assertGreater(production.PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS, 0)
        self.assertEqual(production.PUBLIC_API_CLIENT_IP_HEADER, "HTTP_X_REAL_IP")
        self.assertTrue(production.OPERATIONAL_OBSERVABILITY_ENABLED)
