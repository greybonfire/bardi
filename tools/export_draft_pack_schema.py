"""Generate the draft-pack schema without Django setup or a database connection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from knowledge.draft_packs.schema import DraftPack  # noqa: E402

OUTPUT = ROOT / "docs/draft-packs/draft-pack-v1.schema.json"


def schema_text() -> str:
    schema = DraftPack.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = schema_text()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != text:
            print(f"Schema drift: run uv run python {Path(__file__).relative_to(ROOT)}")
            return 1
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
