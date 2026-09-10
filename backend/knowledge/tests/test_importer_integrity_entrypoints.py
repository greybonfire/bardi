from __future__ import annotations

from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TransactionTestCase

from knowledge.importers import national_id_renewal as national_id_module
from knowledge.importers import passport_renewal as passport_module
from knowledge.importers import temporary_family_exemption as family_module
from knowledge.importers.national_id_renewal import import_national_id_renewal
from knowledge.importers.national_id_renewal_integrity import (
    verify_national_id_renewal_import,
)
from knowledge.importers.passport_renewal import import_passport_renewal
from knowledge.importers.passport_renewal_integrity import verify_passport_renewal_import
from knowledge.importers.temporary_family_exemption import import_temporary_family_exemption
from knowledge.importers.temporary_family_exemption_integrity import (
    verify_temporary_family_exemption_import,
)


class ImporterIntegrityEntrypointTests(TransactionTestCase):
    def _author(self, username: str):  # type: ignore[no-untyped-def]
        return get_user_model().objects.create_user(username=username, is_staff=True)

    def _knowledge_counts(self) -> dict[str, int]:
        return {
            model._meta.label: model._default_manager.count()
            for model in apps.get_app_config("knowledge").get_models()
        }

    def _failing_verifier(self, message: str):  # type: ignore[no-untyped-def]
        def fail(*args: object, **kwargs: object) -> None:
            del args, kwargs
            self.assertTrue(connection.in_atomic_block)
            raise ValidationError(message)

        return fail

    def test_passport_public_entrypoint_verifies_new_repeat_and_rolls_back_failure(self) -> None:
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)
        author = self._author("passport-entrypoint-author")
        before = self._knowledge_counts()

        with patch(
            "knowledge.importers.passport_renewal_integrity.verify_passport_renewal_import",
            side_effect=self._failing_verifier("injected passport verification failure"),
        ):
            with self.assertRaisesMessage(
                ValidationError,
                "injected passport verification failure",
            ):
                import_passport_renewal(author=author)

        self.assertEqual(self._knowledge_counts(), before)
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)

        with patch(
            "knowledge.importers.passport_renewal_integrity.verify_passport_renewal_import",
            wraps=verify_passport_renewal_import,
        ) as verifier:
            first = import_passport_renewal(author=author)
            second = import_passport_renewal(author=author)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(verifier.call_count, 2)
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)

    def test_national_id_public_entrypoint_verifies_new_repeat_and_rolls_back_failure(self) -> None:
        self.assertIs(national_id_module.import_national_id_renewal, import_national_id_renewal)
        author = self._author("national-id-entrypoint-author")
        before = self._knowledge_counts()

        with patch(
            "knowledge.importers.national_id_renewal_integrity.verify_national_id_renewal_import",
            side_effect=self._failing_verifier("injected National ID verification failure"),
        ):
            with self.assertRaisesMessage(
                ValidationError,
                "injected National ID verification failure",
            ):
                import_national_id_renewal(author=author)

        self.assertEqual(self._knowledge_counts(), before)
        self.assertIs(national_id_module.import_national_id_renewal, import_national_id_renewal)

        with patch(
            "knowledge.importers.national_id_renewal_integrity.verify_national_id_renewal_import",
            wraps=verify_national_id_renewal_import,
        ) as verifier:
            first = import_national_id_renewal(author=author)
            second = import_national_id_renewal(author=author)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(verifier.call_count, 2)
        self.assertIs(national_id_module.import_national_id_renewal, import_national_id_renewal)

    def test_family_public_entrypoint_verifies_new_repeat_and_rolls_back_failure(self) -> None:
        self.assertIs(
            family_module.import_temporary_family_exemption,
            import_temporary_family_exemption,
        )
        author = self._author("family-entrypoint-author")
        before = self._knowledge_counts()

        with patch(
            (
                "knowledge.importers.temporary_family_exemption_integrity."
                "verify_temporary_family_exemption_import"
            ),
            side_effect=self._failing_verifier("injected family verification failure"),
        ):
            with self.assertRaisesMessage(
                ValidationError,
                "injected family verification failure",
            ):
                import_temporary_family_exemption(author=author)

        self.assertEqual(self._knowledge_counts(), before)
        self.assertIs(
            family_module.import_temporary_family_exemption,
            import_temporary_family_exemption,
        )

        with patch(
            (
                "knowledge.importers.temporary_family_exemption_integrity."
                "verify_temporary_family_exemption_import"
            ),
            wraps=verify_temporary_family_exemption_import,
        ) as verifier:
            first = import_temporary_family_exemption(author=author)
            second = import_temporary_family_exemption(author=author)

        self.assertEqual(
            tuple(version.pk for version in first),
            tuple(version.pk for version in second),
        )
        self.assertEqual(verifier.call_count, 2)
        self.assertIs(
            family_module.import_temporary_family_exemption,
            import_temporary_family_exemption,
        )
