#!/usr/bin/env python3
"""Export the Django Ninja public API schema for the web client.

The schema is generated from the backend request/response declarations rather than
maintained as a second hand-written contract.  This command only imports Django and
builds Ninja's in-memory OpenAPI document; it does not make database queries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUTPUT = ROOT / "frontend" / "api-schema.json"


def render_schema() -> str:
    sys.path.insert(0, str(BACKEND))
    # Export is deliberately independent of production secrets and database state,
    # even when the caller has exported a different settings module.
    os.environ["DJANGO_SETTINGS_MODULE"] = "bardi.settings.development"

    import django

    django.setup()

    from api.api import api

    return json.dumps(api.get_openapi_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the checked-in schema is not current",
    )
    args = parser.parse_args()

    rendered = render_schema()
    if args.check:
        try:
            current = OUTPUT.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"missing generated schema: {OUTPUT}", file=sys.stderr)
            return 1
        if current != rendered:
            print(f"generated schema is out of date: {OUTPUT}", file=sys.stderr)
            return 1
        return 0

    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
