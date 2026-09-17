from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


BUILDER = Path(__file__).resolve().parent / "fixtures" / "build_issue_preflight_inputs.py"


class IssuePreflightFixtureBuilderTest(unittest.TestCase):
    def test_builder_emits_raw_inputs_and_separate_grader_criteria(self) -> None:
        with tempfile.TemporaryDirectory(prefix="issue-preflight-fixture-") as directory:
            output = Path(directory) / "generated"
            result = subprocess.run(
                ["python3", str(BUILDER), "--output-dir", str(output)],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            manifest = json.loads((output / "inputs.json").read_text(encoding="utf-8"))
            grader = json.loads((output / "expected" / "grader-criteria.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual({case["id"] for case in manifest["cases"]}, {"case-stale-squash", "case-partial-reverted"})
            self.assertEqual({case["id"] for case in grader["cases"]}, {"case-stale-squash", "case-partial-reverted"})
            for case in manifest["cases"]:
                root = Path(case["root"])
                self.assertTrue((root / "request.txt").is_file())
                self.assertTrue((root / "fixture.json").is_file())
                self.assertTrue((root / "before.json").is_file())
                self.assertFalse("grader" in json.loads((root / "fixture.json").read_text(encoding="utf-8")))
                env = {**os.environ, "PATH": f"{case['tool_path']}:{os.environ['PATH']}"}
                subprocess.run(["git", "-C", str(root / "primary"), "status", "--short"], check=True, env=env, capture_output=True)
                self.assertTrue((root / "tool-trace.jsonl").is_file())
            self.assertIn("case-stale-squash", result.stdout)


if __name__ == "__main__":
    unittest.main()
