"""Run from the checkout with uv run python tools/local_sandbox.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from core.local_sandbox import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
