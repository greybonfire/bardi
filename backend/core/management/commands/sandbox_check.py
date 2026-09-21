"""Read-only schema-history and system validation; never applies migrations."""

from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    requires_system_checks: list[str] = []

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            if settings.SETTINGS_MODULE != "bardi.settings.sandbox":
                raise ValueError("not_sandbox")
            with connection.cursor() as cursor:
                cursor.execute("SHOW default_transaction_read_only")
                if cursor.fetchone() != ("on",):
                    raise ValueError("not_read_only")
            call_command("check", verbosity=0)
            executor = MigrationExecutor(connection)
            loader = executor.loader
            loader.check_consistent_history(connection)
            if set(loader.applied_migrations) - set(loader.disk_migrations):
                raise ValueError("unknown_migrations")
            if executor.migration_plan(loader.graph.leaf_nodes()):
                raise ValueError("pending_migrations")
        except Exception:
            raise CommandError("sandbox_compatibility_failed", returncode=1) from None
        self.stdout.write("sandbox_compatible")
