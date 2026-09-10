from __future__ import annotations

from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

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
from knowledge.models import ProcedureVersion


class ImporterIntegrityEntrypointTests(TestCase):
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
            raise ValidationError(message)

        return fail

    def test_passport_public_entrypoint_verifies_new_repeat_and_rolls_back_failure(self) -> None:
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)
        author = self._author("passport-entrypoint-author")
        before = self._knowledge_counts()

        with patch(
            "knowledge.importers.passport_renewal_integrity.verify_passport_renewal_import",
            side_effect=self._failing_verifier("injected passport verification failure"),
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected passport verification failure",
            ):
                import_passport_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)

        self.assertEqual(self._knowledge_counts(), before)
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)

        with patch(
            "knowledge.importers.passport_renewal_integrity.verify_passport_renewal_import",
            wraps=verify_passport_renewal_import,
        ) as verifier:
            first = import_passport_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)
            self.assertEqual(verifier.call_args_list[0].args, (first,))
            second = import_passport_renewal(author=author)
            self.assertEqual(verifier.call_count, 2)
            self.assertEqual(verifier.call_args_list[1].args, (second,))

        self.assertEqual(first.pk, second.pk)
        self.assertIs(passport_module.import_passport_renewal, import_passport_renewal)

    def test_national_id_public_entrypoint_verifies_new_repeat_and_rolls_back_failure(self) -> None:
        self.assertIs(national_id_module.import_national_id_renewal, import_national_id_renewal)
        author = self._author("national-id-entrypoint-author")
        before = self._knowledge_counts()

        with patch(
            "knowledge.importers.national_id_renewal_integrity.verify_national_id_renewal_import",
            side_effect=self._failing_verifier("injected National ID verification failure"),
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected National ID verification failure",
            ):
                import_national_id_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)

        self.assertEqual(self._knowledge_counts(), before)
        self.assertIs(national_id_module.import_national_id_renewal, import_national_id_renewal)

        with patch(
            "knowledge.importers.national_id_renewal_integrity.verify_national_id_renewal_import",
            wraps=verify_national_id_renewal_import,
        ) as verifier:
            first = import_national_id_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)
            self.assertEqual(verifier.call_args_list[0].args, (first,))
            second = import_national_id_renewal(author=author)
            self.assertEqual(verifier.call_count, 2)
            self.assertEqual(verifier.call_args_list[1].args, (second,))

        self.assertEqual(first.pk, second.pk)
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
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected family verification failure",
            ):
                import_temporary_family_exemption(author=author)
            self.assertEqual(verifier.call_count, 1)

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
            self.assertEqual(verifier.call_count, 1)
            self.assertEqual(verifier.call_args_list[0].args, (first,))
            second = import_temporary_family_exemption(author=author)
            self.assertEqual(verifier.call_count, 2)
            self.assertEqual(verifier.call_args_list[1].args, (second,))

        self.assertEqual(
            tuple(version.pk for version in first),
            tuple(version.pk for version in second),
        )
        self.assertIs(
            family_module.import_temporary_family_exemption,
            import_temporary_family_exemption,
        )


    def test_passport_existing_row_verifier_failure_rolls_back_mutation(self) -> None:
        author = self._author("passport-existing-rollback-author")
        version = import_passport_renewal(author=author)
        original_text = version.text_en

        def fail_after_mutation(target: ProcedureVersion) -> None:
            ProcedureVersion.objects.filter(pk=target.pk).update(
                text_en="passport verifier mutation must roll back"
            )
            raise ValidationError("injected passport existing verification failure")

        with patch(
            "knowledge.importers.passport_renewal_integrity.verify_passport_renewal_import",
            side_effect=fail_after_mutation,
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected passport existing verification failure",
            ):
                import_passport_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)

        version.refresh_from_db()
        self.assertEqual(version.text_en, original_text)

    def test_national_id_existing_row_verifier_failure_rolls_back_mutation(self) -> None:
        author = self._author("national-id-existing-rollback-author")
        version = import_national_id_renewal(author=author)
        original_text = version.text_en

        def fail_after_mutation(target: ProcedureVersion) -> None:
            ProcedureVersion.objects.filter(pk=target.pk).update(
                text_en="National ID verifier mutation must roll back"
            )
            raise ValidationError("injected National ID existing verification failure")

        with patch(
            "knowledge.importers.national_id_renewal_integrity.verify_national_id_renewal_import",
            side_effect=fail_after_mutation,
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected National ID existing verification failure",
            ):
                import_national_id_renewal(author=author)
            self.assertEqual(verifier.call_count, 1)

        version.refresh_from_db()
        self.assertEqual(version.text_en, original_text)

    def test_family_existing_rows_verifier_failure_rolls_back_mutations(self) -> None:
        author = self._author("family-existing-rollback-author")
        versions = import_temporary_family_exemption(author=author)
        original_text = {version.pk: version.text_en for version in versions}

        def fail_after_mutation(
            targets: tuple[ProcedureVersion, ProcedureVersion],
        ) -> None:
            for target in targets:
                ProcedureVersion.objects.filter(pk=target.pk).update(
                    text_en=f"{target.semantic_id} verifier mutation must roll back"
                )
            raise ValidationError("injected family existing verification failure")

        with patch(
            (
                "knowledge.importers.temporary_family_exemption_integrity."
                "verify_temporary_family_exemption_import"
            ),
            side_effect=fail_after_mutation,
        ) as verifier:
            with self.assertRaisesMessage(
                ValidationError,
                "injected family existing verification failure",
            ):
                import_temporary_family_exemption(author=author)
            self.assertEqual(verifier.call_count, 1)

        for version in versions:
            version.refresh_from_db()
            self.assertEqual(version.text_en, original_text[version.pk])
