from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from knowledge.importers.national_id_renewal import import_national_id_renewal


class Command(BaseCommand):
    help = "Import or verify the researched ordinary domestic National ID-renewal draft."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--author", required=True)

    def handle(self, *args: object, **options: object) -> None:
        username = str(options["author"])
        user_model = get_user_model()
        try:
            author = user_model._default_manager.get(username=username, is_staff=True)
        except user_model.DoesNotExist as exc:
            raise CommandError("--author must name an existing staff user.") from exc
        version = import_national_id_renewal(author=author)
        self.stdout.write(f"{version.semantic_id} {version.state}")
