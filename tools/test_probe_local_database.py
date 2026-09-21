"""Database-free regressions for the disposable probe's TCP readiness gate."""

import contextlib
import io
import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from tools import probe_local_database as probe


class TCPReadinessTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "POSTGRES_DB": "disposable",
            "POSTGRES_USER": "probe",
            "POSTGRES_PASSWORD": "secret-not-for-output",
            "POSTGRES_PORT": "49123",
        }

    @patch.object(probe.time, "sleep")
    @patch("psycopg.connect")
    def test_initialization_refusal_then_authenticated_tcp_ready(self, connect, sleep):
        connection = MagicMock()
        connect.side_effect = [psycopg.OperationalError("secret"), connection]
        probe.wait_for_tcp(self.env)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(
            connect.call_args.kwargs,
            {
                "dbname": "disposable",
                "user": "probe",
                "password": "secret-not-for-output",
                "host": "127.0.0.1",
                "port": "49123",
                "connect_timeout": 2,
                "options": "-c default_transaction_read_only=on",
            },
        )
        connection.close.assert_called_once_with()
        sleep.assert_called_once_with(0.1)

    @patch.object(probe.time, "sleep")
    @patch.object(probe.time, "monotonic", side_effect=[0, 0, 31])
    @patch("psycopg.connect", side_effect=psycopg.OperationalError("secret"))
    def test_deadline_is_bounded_and_error_is_sanitized(self, connect, clock, sleep):
        with self.assertRaises(TimeoutError) as caught:
            probe.wait_for_tcp(self.env)
        self.assertNotIn("secret", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(connect.call_count, 1)

    @patch("psycopg.connect", side_effect=ValueError("invalid configuration"))
    def test_non_connection_errors_are_not_retried(self, connect):
        with self.assertRaises(ValueError):
            probe.wait_for_tcp(self.env)
        connect.assert_called_once()


class FailureDiagnosticsTests(unittest.TestCase):
    def test_subprocess_secrets_and_source_lines_are_not_printed(self):
        output = io.StringIO()
        try:
            raise subprocess.CalledProcessError(
                1, ["secret-command"], output=b"secret-rows", stderr=b"secret-password"
            )
        except subprocess.CalledProcessError as error:
            with contextlib.redirect_stderr(output):
                probe.report_failure(error)
        self.assertNotIn("secret", output.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["exception"], "CalledProcessError")
        self.assertEqual(result["status"], "probe_failed")
        self.assertEqual(result["frames"][0]["file"], "test_probe_local_database.py")
        self.assertIsInstance(result["frames"][0]["line"], int)


if __name__ == "__main__":
    unittest.main()
