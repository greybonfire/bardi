from typing import Any

from django.core.management.base import CommandParser

from knowledge.draft_packs import export_draft_context
from knowledge.draft_packs.cli import JsonCommand


class Command(JsonCommand):
    help = "Export non-importable read-only authoring context."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--service")
        parser.add_argument("--actor", required=True)
        parser.add_argument("--output")

    def handle(self, *args: Any, **options: Any) -> None:
        self.execute_json(
            lambda: export_draft_context(options["service"], actor=self.actor(options["actor"])),
            options["output"],
        )
