"""Safety boundaries and real catalog coverage for disposable database setup."""

from unittest.mock import MagicMock, patch

from bardi.settings import base, development, test
from bardi.testing import FreshDatabaseRunner
from django.apps import AppConfig, apps
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models.signals import post_migrate
from django.test import SimpleTestCase, TestCase
from django.test.runner import DiscoverRunner


class FreshDatabaseRunnerTests(SimpleTestCase):
    def test_only_test_settings_select_runner(self) -> None:
        self.assertEqual(test.TEST_RUNNER, "bardi.testing.FreshDatabaseRunner")
        for module in (base, development):
            self.assertFalse(hasattr(module, "TEST_RUNNER"))

    def test_keepdb_rejected_before_setup(self) -> None:
        with patch.object(DiscoverRunner, "setup_databases") as setup:
            with self.assertRaisesMessage(ImproperlyConfigured, "--keepdb"):
                FreshDatabaseRunner(keepdb=True).setup_databases()
            setup.assert_not_called()

    def test_scoped_signal_guards_and_cleanup(self) -> None:
        for failure in (None, "alias", "configured", "connected", "original", "setup"):
            with self.subTest(failure=failure):
                db = MagicMock()
                db.settings_dict = {"NAME": "application"}
                db.vendor = "postgresql"
                db.creation._get_test_db_name.return_value = (
                    "application" if failure == "original" else "test_disposable"
                )
                cursor = db.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = ("test_disposable",)
                db.introspection.table_names.return_value = ['knowledge_odd"name', "auth_user"]
                db.ops.quote_name.side_effect = lambda name: '"' + name.replace('"', '""') + '"'
                sender = apps.get_app_config("knowledge")
                before = list(post_migrate.receivers)

                def setup(
                    failure: str | None = failure,
                    db: MagicMock = db,
                    cursor: MagicMock = cursor,
                    sender: AppConfig = sender,
                    **kwargs: object,
                ) -> list[object]:
                    if failure == "setup":
                        raise RuntimeError("setup failed")
                    db.settings_dict["NAME"] = (
                        "application" if failure == "configured" else "test_disposable"
                    )
                    if failure == "connected":
                        cursor.fetchone.return_value = ("application",)
                    post_migrate.send(sender=apps.get_app_config("auth"), using="default")
                    cursor.execute.assert_not_called()
                    post_migrate.send(
                        sender=sender, using="other" if failure == "alias" else "default"
                    )
                    return []

                # Isolate Django's other receivers, which require migration arguments.
                with (
                    patch("bardi.testing.connections", {"default": db}),
                    patch.object(post_migrate, "receivers", []),
                    patch.object(DiscoverRunner, "setup_databases", side_effect=setup) as parent,
                ):
                    if failure:
                        with self.assertRaises(
                            RuntimeError if failure == "setup" else ImproperlyConfigured
                        ):
                            FreshDatabaseRunner().setup_databases()
                    else:
                        FreshDatabaseRunner().setup_databases()
                        cursor.execute.assert_any_call(
                            'ALTER TABLE "knowledge_odd""name" SET '
                            "(autovacuum_enabled = false, toast.autovacuum_enabled = false)"
                        )
                    self.assertEqual(post_migrate.receivers, [])
                    if failure == "original":
                        parent.assert_not_called()
                    if failure:
                        self.assertFalse(
                            any(
                                str(call.args[0]).startswith("ALTER")
                                for call in cursor.execute.call_args_list
                            )
                        )
                self.assertEqual(post_migrate.receivers, before)


class FreshDatabaseCatalogTests(TestCase):
    def test_knowledge_tables_and_toast_disable_autovacuum(self) -> None:
        # Also runs inside worker clones when invoked with --parallel.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.relname, c.reloptions, t.reloptions, c.reltoastrelid "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "LEFT JOIN pg_class t ON t.oid = c.reltoastrelid "
                "WHERE n.nspname = current_schema() AND c.relkind = 'r'"
            )
            rows = cursor.fetchall()
        knowledge = [row for row in rows if row[0].startswith("knowledge_")]
        self.assertTrue(knowledge)
        self.assertTrue(any(row[3] for row in knowledge))
        for name, options, toast_options, toast_oid in knowledge:
            with self.subTest(table=name):
                self.assertIn("autovacuum_enabled=false", options or [])
                if toast_oid:
                    self.assertIn("autovacuum_enabled=false", toast_options or [])
        for name, options, _, _ in rows:
            if not name.startswith("knowledge_"):
                self.assertNotIn("autovacuum_enabled=false", options or [], name)
