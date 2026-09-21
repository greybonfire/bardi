"""Sandbox gates, isolated Admin and strict read-only migration checks (no database)."""

import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management.base import CommandError

from core.local_database import ROOT
from core.management.commands import sandbox_check


class CompatibilityTests(unittest.TestCase):
    def test_only_read_only_complete_known_consistent_history_passes(self) -> None:
        for failure in (
            None,
            "settings",
            "writable",
            "pending",
            "unknown",
            "inconsistent",
            "system",
        ):
            with self.subTest(failure=failure):
                settings = SimpleNamespace(SETTINGS_MODULE="bardi.settings.sandbox")
                connection = MagicMock()
                connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "on",
                )
                executor = MagicMock()
                executor.loader.applied_migrations = {("core", "0001")}
                executor.loader.disk_migrations = {("core", "0001")}
                executor.migration_plan.return_value = []
                if failure == "settings":
                    settings.SETTINGS_MODULE = "bardi.settings.test"
                if failure == "writable":
                    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                        "off",
                    )
                if failure == "pending":
                    executor.migration_plan.return_value = [("pending", False)]
                if failure == "unknown":
                    executor.loader.applied_migrations.add(("private", "unknown"))
                if failure == "inconsistent":
                    executor.loader.check_consistent_history.side_effect = ValueError("private")
                with (
                    patch.object(sandbox_check, "settings", settings),
                    patch.object(sandbox_check, "connection", connection),
                    patch.object(sandbox_check, "MigrationExecutor", return_value=executor),
                    patch.object(sandbox_check, "call_command") as check,
                ):
                    if failure == "system":
                        check.side_effect = ValueError("private")
                    command = sandbox_check.Command(stdout=MagicMock())
                    if failure:
                        with self.assertRaisesRegex(CommandError, "^sandbox_compatibility_failed$"):
                            command.handle()
                    else:
                        command.handle()
                        check.assert_called_once_with("check", verbosity=0)
                    executor.migrate.assert_not_called()
                    for call in (
                        connection.cursor.return_value.__enter__.return_value.execute.call_args_list
                    ):
                        self.assertEqual(call.args, ("SHOW default_transaction_read_only",))


class SandboxSettingsTests(unittest.TestCase):
    def environment(self) -> dict[str, str]:
        return {
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(ROOT / "backend"),
            "DJANGO_SETTINGS_MODULE": "bardi.settings.sandbox",
            "BARDI_SANDBOX": "1",
            "BARDI_SANDBOX_ID": "a" * 32,
            "DJANGO_SECRET_KEY": "test-only-not-a-real-secret",
            "POSTGRES_DB": "bardi_restore_" + "b" * 32,
            "POSTGRES_USER": "sandbox",
            "POSTGRES_PASSWORD": "test-only",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5432",
            "PROCEDURE_VERSION_REVIEW_MODE": "solo",
        }

    def test_full_base_gates_and_isolated_admin_cookies(self) -> None:
        script = """
import django
django.setup()
from django.conf import settings
from django.contrib import admin
from bardi.settings import base
assert settings.PROCEDURE_VERSION_PUBLICATION_GATES == base.PROCEDURE_VERSION_PUBLICATION_GATES
assert settings.SELECTION_QUESTIONS_REQUIRED is True
assert settings.PLANNING_SCENARIOS_REQUIRED is True
assert settings.PROCEDURE_VERSION_REVIEW_MODE == 'solo'
assert settings.SESSION_COOKIE_NAME == 'bardi_sandbox_' + 'a' * 32 + '_session'
assert settings.CSRF_COOKIE_NAME == 'bardi_sandbox_' + 'a' * 32 + '_csrf'
assert not settings.DATABASES['default'].get('OPTIONS')
header = admin.site.site_header
from bardi.sandbox_urls import sandbox_admin
assert sandbox_admin.site_header == 'LOCAL QUESTIONNAIRE SANDBOX'
assert admin.site.site_header == header
assert sandbox_admin is not admin.site
assert set(sandbox_admin._registry) == set(admin.site._registry)
assert all(a.admin_site is sandbox_admin for a in sandbox_admin._registry.values())
from django.core.management import call_command, get_commands
assert get_commands()['sandbox_check'] == 'core'
call_command('check', verbosity=0)
"""
        result = subprocess.run(
            [sys.executable, "-c", script], env=self.environment(), capture_output=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_generated_settings_required_and_no_authoring_database(self) -> None:
        for key, value in (
            ("BARDI_SANDBOX", "0"),
            ("BARDI_SANDBOX_ID", "bad"),
            ("POSTGRES_HOST", "localhost"),
            ("POSTGRES_DB", "bardi"),
            ("PROCEDURE_VERSION_REVIEW_MODE", "off"),
            ("DJANGO_SECRET_KEY", ""),
        ):
            env = self.environment()
            env[key] = value
            result = subprocess.run(
                [sys.executable, "-c", "import bardi.settings.sandbox"],
                env=env,
                capture_output=True,
                timeout=60,
            )
            self.assertNotEqual(result.returncode, 0, key)
