from typing import Any

from django.core.management.base import CommandParser

from knowledge.draft_packs import import_draft_pack
from knowledge.draft_packs.cli import JsonCommand


class Command(JsonCommand):
    help = "Import a complete draft snapshot without publication or verification."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("file")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--new", action="store_true")
        mode.add_argument("--target-version")
        parser.add_argument("--actor", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-deletions", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        self.execute_json(
            lambda: import_draft_pack(
                self.read_pack(options["file"]),
                actor=self.actor(options["actor"]),
                target_version=options["target_version"],
                dry_run=options["dry_run"],
                allow_deletions=options["allow_deletions"],
            )
        )
