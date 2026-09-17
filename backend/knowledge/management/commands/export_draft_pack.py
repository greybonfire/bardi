from typing import Any

from django.core.management.base import CommandParser

from knowledge.draft_packs import export_draft_pack
from knowledge.draft_packs.cli import JsonCommand


class Command(JsonCommand):
    help = "Export a coherent, editable draft-pack snapshot."

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        # The documented --version selects knowledge, not Django's version banner.
        kwargs["conflict_handler"] = "resolve"
        return super().create_parser(prog_name, subcommand, **kwargs)

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--version", required=True)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--output")

    def handle(self, *args: Any, **options: Any) -> None:
        self.execute_json(
            lambda: export_draft_pack(options["version"], actor=self.actor(options["actor"])),
            options["output"],
        )
