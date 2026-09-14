// @vitest-environment node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

it("exports deterministically without database access and detects missing/stale snapshots", () => {
  // Exercise the real tool with a temporary OUTPUT, never modify the working
  // snapshot while other workers or CI type generation may be reading it.
  const result = spawnSync("uv", ["run", "python", "-c", `
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("web_export", "tools/export_web_api.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
with tempfile.TemporaryDirectory() as directory:
    exporter.OUTPUT = Path(directory) / "api-schema.json"
    with patch("django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
               side_effect=AssertionError("schema export must not access a database")):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            sys.argv = ["export_web_api.py", "--check"]
            assert exporter.main() == 1, "missing snapshot must fail"
            sys.argv = ["export_web_api.py"]
            assert exporter.main() == 0
            generated = exporter.OUTPUT.read_text(encoding="utf-8")
            assert generated == exporter.render_schema(), "export must be deterministic"
            assert os.environ["DJANGO_SETTINGS_MODULE"] == "bardi.settings.development"
            sys.argv = ["export_web_api.py", "--check"]
            assert exporter.main() == 0
            exporter.OUTPUT.write_text("{}\\n", encoding="utf-8")
            assert exporter.main() == 1, "stale snapshot must fail"
`], {
    cwd: fileURLToPath(new URL("../../../", import.meta.url)),
    env: {
      ...process.env,
      DJANGO_SETTINGS_MODULE: "bardi.settings.production",
      POSTGRES_HOST: "invalid.example",
      POSTGRES_PORT: "1",
    },
    encoding: "utf-8",
    timeout: 20_000,
  });
  expect(result.error).toBeUndefined();
  expect(result.stderr).toBe("");
  expect(result.status).toBe(0);
}, 25_000);
