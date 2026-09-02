"""Logging safeguards for anonymous planning requests."""

from __future__ import annotations

import logging


class PlanningPrivacyFilter(logging.Filter):
    """Replace planning-route records so bodies, inputs and exception locals cannot escape."""

    def filter(self, record: logging.LogRecord) -> bool:
        request = getattr(record, "request", None)
        path = getattr(request, "path", "")
        if not path and isinstance(record.args, tuple):
            if any(isinstance(item, str) and "/v1/planning" in item for item in record.args):
                path = "/v1/planning"
        if not str(path).startswith("/v1/planning"):
            return True
        method = getattr(request, "method", "POST")
        status = getattr(record, "status_code", 500)
        code = getattr(record, "error_code", "request_error")
        record.msg = "%s %s %s %s"
        record.args = (method, "/v1/planning", status, code)
        record.exc_info = None
        record.exc_text = None
        for attribute in ("body", "data", "facts", "input", "parsed"):
            if hasattr(record, attribute):
                setattr(record, attribute, None)
        return True
