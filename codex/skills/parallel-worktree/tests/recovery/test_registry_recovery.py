#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HELPER = Path(__file__).resolve().parents[2] / "scripts" / "pw-helper"


class RecoveryTest(unittest.TestCase):
    def test_invalid_management_adapter_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin = root / "origin.git"
            repo = root / "repo"
            subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            for key, value in (("user.name", "PW Test"), ("user.email", "pw@example.test")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
            (repo / "file.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "push", "-u", "origin", "main"], check=True, capture_output=True)
            subprocess.run(["git", "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
            env = os.environ | {"CODEX_HOME": str(root / "codex")}
            prepared = subprocess.run(
                [str(HELPER), "prepare-start", "--repo", str(repo), "--issue", "9", "--risk", "R1", "--planned-branch", "fix/9-test"],
                text=True, capture_output=True, check=True, env=env,
            )
            record = json.loads(prepared.stdout)
            registry = root / "codex" / "parallel-worktree" / record["repository_id"] / "issue-9.json"
            data = json.loads(registry.read_text())
            data["adapter_kind"] = "codex_desktop_managed"
            registry.write_text(json.dumps(data))
            result = subprocess.run([str(HELPER), "show", "--repo", str(repo), "--issue", "9"], text=True, capture_output=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid management_mode/adapter_kind pairing", result.stderr)

    def test_valid_codex_managed_pair_remains_disabled_without_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin = root / "origin.git"
            repo = root / "repo"
            subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            for key, value in (("user.name", "PW Test"), ("user.email", "pw@example.test")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
            (repo / "file.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "push", "-u", "origin", "main"], check=True, capture_output=True)
            subprocess.run(["git", "--git-dir", str(origin), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
            env = os.environ | {"CODEX_HOME": str(root / "codex")}
            prepared = subprocess.run(
                [str(HELPER), "prepare-start", "--repo", str(repo), "--issue", "10", "--risk", "R1", "--planned-branch", "fix/10-test"],
                text=True, capture_output=True, check=True, env=env,
            )
            record = json.loads(prepared.stdout)
            registry = root / "codex" / "parallel-worktree" / record["repository_id"] / "issue-10.json"
            data = json.loads(registry.read_text())
            data["management_mode"] = "codex_managed"
            data["adapter_kind"] = "codex_desktop_managed"
            data["archive_delete_contract"] = "unverified"
            registry.write_text(json.dumps(data))
            result = subprocess.run([str(HELPER), "show", "--repo", str(repo), "--issue", "10"], text=True, capture_output=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("disabled until its adapter contract is verified", result.stderr)


if __name__ == "__main__":
    unittest.main()
