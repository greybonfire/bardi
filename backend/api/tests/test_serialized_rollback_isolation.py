from __future__ import annotations

import unittest

from django.test import SimpleTestCase

from api.tests import test_contradiction_diagnostics, test_cross_family_production_parity


class SerializedRollbackIsolationLifecycleTests(SimpleTestCase):
    databases = {"default"}
    serialized_rollback = True

    def test_mixed_transaction_and_serialized_rollback_lifecycle(self) -> None:
        suite = unittest.TestSuite(
            (
                test_contradiction_diagnostics.ContradictionDiagnosticContractTests(
                    "test_omitted_dominated_fact_is_not_reported_for_true_contradiction"
                ),
                test_cross_family_production_parity.CrossFamilyProductionParityAcceptanceTests(
                    "test_identical_requests_are_byte_semantically_deterministic"
                ),
                test_cross_family_production_parity.CrossFamilyProductionParityAcceptanceTests(
                    "test_identical_requests_are_byte_semantically_deterministic"
                ),
                test_contradiction_diagnostics.ContradictionDiagnosticContractTests(
                    "test_omitted_dominated_fact_is_not_reported_for_true_contradiction"
                ),
                test_cross_family_production_parity.CrossFamilyProductionParityAcceptanceTests(
                    "test_identical_requests_are_byte_semantically_deterministic"
                ),
            )
        )
        result = unittest.TestResult()
        suite.run(result)

        details = "\n\n".join(
            f"{test}:\n{traceback}" for test, traceback in (*result.errors, *result.failures)
        )
        self.assertEqual(result.testsRun, 5, details)
        self.assertFalse(result.errors, details)
        self.assertFalse(result.failures, details)
        self.assertFalse(result.skipped, details)
