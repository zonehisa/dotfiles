from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(__file__).resolve().parents[2]
HELPER = SKILL / "scripts" / "pw-helper"
PREFLIGHT_SCRIPT = SKILL.parent / "git-workflow" / "scripts" / "issue_preflight.py"
SPEC = importlib.util.spec_from_file_location("issue_preflight_gate_module", PREFLIGHT_SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def run_helper(*args: str, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(HELPER), *args], text=True, capture_output=True, env=env, check=check)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class PreflightHelperGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="preflight-helper-gate-")
        root = Path(self.temp.name)
        self.root = root
        self.codex_home = root / "codex"
        self.origin = root / "origin.git"
        self.repo = root / "repo"
        self.fixture = root / "gh.json"
        self.bin = root / "bin"
        self.bin.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.origin)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        git(self.repo, "config", "user.name", "Preflight Gate")
        git(self.repo, "config", "user.email", "preflight-gate@example.invalid")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "initial")
        git(self.repo, "push", "-qu", "origin", "main")
        subprocess.run(["git", "--git-dir", str(self.origin), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
        git(self.repo, "fetch", "origin")
        remote = "https://user:secret@github.com/example/preflight.git"
        git(self.repo, "remote", "set-url", "origin", remote)
        git(self.repo, "config", f"url.{self.origin}.insteadOf", remote)
        self.fixture.write_text(json.dumps({
            "repo": {"nameWithOwner": "example/preflight", "defaultBranchRef": {"name": "main"}},
            "issue": {"number": 106, "title": "Feature", "body": "", "state": "OPEN", "url": "https://github.com/example/preflight/issues/106", "updatedAt": "2026-09-16T00:00:00Z", "closedAt": None, "labels": []},
            "timeline": [], "pr_list": [], "pr_views": {},
        }), encoding="utf-8")
        (self.bin / "gh").write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "d=json.loads(Path(os.environ['PREFLIGHT_FIXTURE']).read_text())\n"
            "a=sys.argv[1:]\n"
            "if a[:2]==['repo','view']: v=d['repo']\n"
            "elif a[:2]==['issue','view']: v=d['issue']\n"
            "elif a[:1]==['api']: v=d['timeline']\n"
            "elif a[:2]==['pr','list']: v=d['pr_list']\n"
            "elif a[:2]==['pr','view']: v=d['pr_views'].get(next((x for x in a if x.isdigit()),'0'))\n"
            "else: raise SystemExit(2)\n"
            "print(json.dumps(v))\n",
            encoding="utf-8",
        )
        (self.bin / "gh").chmod(0o700)
        self.env = {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "PREFLIGHT_FIXTURE": str(self.fixture),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def json(self, *args: str, check: bool = True) -> dict:
        result = run_helper(*args, env=self.env, check=check)
        return json.loads(result.stdout if result.stdout else result.stderr)

    def setup_lifecycle(self, issue: int = 106) -> tuple[dict, Path]:
        record = self.json("prepare-start", "--repo", str(self.repo), "--issue", str(issue), "--risk", "R3", "--planned-branch", f"fix/{issue}-preflight")
        operation = record["operation_id"]
        self.json("worktree-add", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation)
        self.json("verify-child", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation)
        self.json("record-owner", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation, "--owner-task-id", "gate-owner")
        self.json("record-permission", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation, "--evidence-sha256", "a" * 64)
        created = self.json("branch-create", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation, "--caller-task-id", "gate-owner")
        child = Path(created["worktree_path"])
        self.json("transition", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation, "--to-state", "planning")
        self.json("transition", "--repo", str(self.repo), "--issue", str(issue), "--operation", operation, "--to-state", "approved")
        return self.json("show", "--repo", str(self.repo), "--issue", str(issue)), child

    def attach_packet(self, record: dict, *, status: str) -> dict:
        fixture = json.loads(self.fixture.read_text(encoding="utf-8"))
        fixture["issue"]["number"] = int(record["issue"])
        self.fixture.write_text(json.dumps(fixture), encoding="utf-8")
        criteria = [{"id": "gap", "requirement": "new behavior", "source": [{"path": "missing.py", "exists": False}]}]
        with mock.patch.dict(os.environ, self.env, clear=True):
            first = preflight.collect_evidence(self.repo, int(record["issue"]), criteria=criteria, target=record["base_remote_ref"], creation_base=record["base_sha_at_start"], fetch=True)
            assessed = json.loads(json.dumps(criteria))
            assessed[0]["assessment"] = {
                "status": status,
                "rationale": "The latest target was inspected against the Issue requirement.",
                "residual_scope": "Implement and test the missing behavior." if status == "missing" else "No residual scope.",
                "assessed_target_sha": first["current_target"]["sha"],
                "assessed_issue_relevant_sha256": first["issue_relevant"]["sha256"],
            }
            evidence = preflight.collect_evidence(self.repo, int(record["issue"]), criteria=assessed, target=record["base_remote_ref"], creation_base=record["base_sha_at_start"], fetch=True)
        registry = self.codex_home / "parallel-worktree" / record["repository_id"]
        evidence_dir = registry / "evidence"
        evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        evidence_file = evidence_dir / f"packet-{status}.json"
        evidence_file.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        evidence_file.chmod(0o600)
        attached = self.json("record-preflight", "--repo", str(self.repo), "--issue", str(record["issue"]), "--operation", record["operation_id"], "--caller-task-id", "gate-owner", "--evidence-file", str(evidence_file))
        self.assertEqual(attached["preflight"]["decision"], evidence["decision"])
        return attached

    def test_real_helper_gate_allows_confirmed_gap_and_blocks_satisfied_or_stale(self) -> None:
        (self.repo / "README.md").write_text("primary unstaged\n", encoding="utf-8")
        (self.repo / "staged-primary.txt").write_text("staged\n", encoding="utf-8")
        git(self.repo, "add", "staged-primary.txt")
        (self.repo / "primary-dirty.txt").write_text("preserve\n", encoding="utf-8")
        before_status = git(self.repo, "status", "--porcelain=v1", "--untracked-files=all")
        record, _ = self.setup_lifecycle()
        self.attach_packet(record, status="missing")
        implementing = self.json("transition", "--repo", str(self.repo), "--issue", "106", "--operation", record["operation_id"], "--to-state", "implementing")
        self.assertEqual(implementing["state"], "implementing")
        self.assertEqual(git(self.repo, "status", "--porcelain=v1", "--untracked-files=all"), before_status)

        # A fresh lifecycle with a satisfied assessment is a hard stop.
        satisfied, _ = self.setup_lifecycle(issue=107)
        self.attach_packet(satisfied, status="satisfied")
        blocked = run_helper("transition", "--repo", str(self.repo), "--issue", "107", "--operation", satisfied["operation_id"], "--to-state", "implementing", env=self.env, check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("already satisfied", blocked.stderr)

    def test_resume_or_write_rechecks_remote_target_without_overwriting_primary(self) -> None:
        record, _ = self.setup_lifecycle(issue=108)
        self.attach_packet(record, status="missing")
        external = self.root / "external"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(external)], check=True)
        git(external, "config", "user.name", "External")
        git(external, "config", "user.email", "external@example.invalid")
        (external / "remote-change.txt").write_text("remote\n", encoding="utf-8")
        git(external, "add", "remote-change.txt")
        git(external, "commit", "-qm", "move origin")
        git(external, "push", "-q", "origin", "main")
        dirty = self.repo / "primary-untracked.txt"
        dirty.write_text("keep\n", encoding="utf-8")
        blocked = run_helper("transition", "--repo", str(self.repo), "--issue", "108", "--operation", record["operation_id"], "--to-state", "implementing", env=self.env, check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("current target SHA changed", blocked.stderr)
        self.assertTrue(dirty.exists())

    def test_write_gate_requires_registry_creation_base_sha(self) -> None:
        record, _ = self.setup_lifecycle(issue=109)
        self.attach_packet(record, status="missing")
        registry_path = self.codex_home / "parallel-worktree" / record["repository_id"] / "issue-109.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["base_sha_at_start"] = "0" * 40
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        blocked = run_helper(
            "transition", "--repo", str(self.repo), "--issue", "109",
            "--operation", record["operation_id"], "--to-state", "implementing",
            env=self.env, check=False,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("registry creation base SHA", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
