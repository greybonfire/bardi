"""Fresh disposable PostgreSQL database setup, selected only by test settings."""

from typing import Any

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models.signals import post_migrate
from django.test.runner import DiscoverRunner


class FreshDatabaseRunner(DiscoverRunner):
    """Keep rollback-heavy tests from racing background maintenance, not real writers."""

    def setup_databases(self, **kwargs: Any) -> Any:
        if self.keepdb:
            raise ImproperlyConfigured(
                "FreshDatabaseRunner requires fresh databases; omit --keepdb."
            )
        expected = {
            alias: (
                connections[alias].settings_dict["NAME"],
                # Django's creation API honors TEST.NAME; omitted from django-stubs.
                connections[alias].creation._get_test_db_name(),  # type: ignore[attr-defined]
            )
            for alias in connections
        }
        for original, test_name in expected.values():
            if not test_name or test_name == original:
                raise ImproperlyConfigured("Test database must differ from the original database.")

        def configure(sender: object, using: str, **signal_kwargs: Any) -> None:
            if using not in expected:
                raise ImproperlyConfigured("Unexpected test database alias.")
            original, test_name = expected[using]
            connection = connections[using]
            if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != test_name:
                raise ImproperlyConfigured("Expected a disposable PostgreSQL test database.")
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                current = cursor.fetchone()[0]
                if current != test_name or current == original:
                    raise ImproperlyConfigured(
                        "Connected database is not the expected test database."
                    )
                tables = connection.introspection.table_names(cursor)
                for table in tables:
                    if table.startswith("knowledge_"):
                        cursor.execute(
                            f"ALTER TABLE {connection.ops.quote_name(table)} "
                            "SET (autovacuum_enabled = false, toast.autovacuum_enabled = false)"
                        )

        # create_test_db emits this after migrations and before Django clones the DB.
        # Never leave it installed for flush or migration tests later in the run.
        sender = apps.get_app_config("knowledge")
        post_migrate.connect(configure, sender=sender, weak=False)
        try:
            return super().setup_databases(**kwargs)
        finally:
            post_migrate.disconnect(configure, sender=sender)
