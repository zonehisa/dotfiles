#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


SKILL = Path(__file__).resolve().parents[2]
HELPER = SKILL / "scripts" / "pw-helper"


def run(*args: str, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(HELPER), *args], text=True, capture_output=True, env=merged, check=check)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True).stdout.strip()


class HelperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.codex_home = root / "codex"
        self.origin = root / "origin.git"
        self.repo = root / "repo"
        subprocess.run(["git", "init", "--bare", str(self.origin)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        git(self.repo, "config", "user.name", "PW Test")
        git(self.repo, "config", "user.email", "pw@example.test")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        (self.repo / "README.md").write_text("base\n")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "push", "-u", "origin", "main")
        subprocess.run(["git", "--git-dir", str(self.origin), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
        git(self.repo, "fetch", "origin")
        self.env = {"CODEX_HOME": str(self.codex_home)}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def helper_json(self, *args: str) -> dict:
        return json.loads(run(*args, env=self.env).stdout)

    def test_repository_id_is_stable(self) -> None:
        first = self.helper_json("repository-id", "--repo", str(self.repo))
        second = self.helper_json("repository-id", "--repo", str(self.repo))
        self.assertEqual(first["repository_id"], second["repository_id"])
        self.assertRegex(first["repository_id"], r"^[0-9a-f]{20}$")

    def test_rejects_invalid_issue(self) -> None:
        result = run(
            "prepare-start", "--repo", str(self.repo), "--issue", "#1",
            "--risk", "R1", "--planned-branch", "fix/1-example",
            env=self.env, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("positive decimal", result.stderr)

    def test_prepare_reserves_distinct_ports_and_rejects_existing_branch(self) -> None:
        first = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "127",
            "--risk", "R1", "--planned-branch", "fix/127-example",
        )
        second = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "128",
            "--risk", "R1", "--planned-branch", "fix/128-example",
        )
        self.assertNotEqual(first["resource_namespace"]["port"], second["resource_namespace"]["port"])
        self.assertGreaterEqual(first["resource_namespace"]["port"], 20_000)
        git(self.repo, "branch", "fix/129-existing")
        rejected = run(
            "prepare-start", "--repo", str(self.repo), "--issue", "129",
            "--risk", "R1", "--planned-branch", "fix/129-existing",
            env=self.env, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("branch already exists", rejected.stderr)

    def test_resource_names_are_distinct_across_repositories(self) -> None:
        root = Path(self.temp.name)
        origin2 = root / "origin-2.git"
        repo2 = root / "repo-2"
        subprocess.run(["git", "init", "--bare", str(origin2)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(repo2)], check=True, capture_output=True)
        git(repo2, "config", "user.name", "PW Test")
        git(repo2, "config", "user.email", "pw@example.test")
        git(repo2, "remote", "add", "origin", str(origin2))
        (repo2 / "README.md").write_text("second\n")
        git(repo2, "add", "README.md")
        git(repo2, "commit", "-m", "initial")
        git(repo2, "push", "-u", "origin", "main")
        subprocess.run(["git", "--git-dir", str(origin2), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
        git(repo2, "fetch", "origin")
        first = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "140",
            "--risk", "R1", "--planned-branch", "fix/140-first",
        )
        second = self.helper_json(
            "prepare-start", "--repo", str(repo2), "--issue", "140",
            "--risk", "R1", "--planned-branch", "fix/140-second",
        )
        self.assertNotEqual(first["repository_id"], second["repository_id"])
        for key in ("compose_project", "database", "cache", "port"):
            self.assertNotEqual(first["resource_namespace"][key], second["resource_namespace"][key])

    def test_global_resource_lock_is_not_held_during_fetch(self) -> None:
        root = Path(self.temp.name)
        origin2 = root / "fast-origin.git"
        repo2 = root / "fast-repo"
        subprocess.run(["git", "init", "--bare", str(origin2)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(repo2)], check=True, capture_output=True)
        git(repo2, "config", "user.name", "PW Test")
        git(repo2, "config", "user.email", "pw@example.test")
        git(repo2, "remote", "add", "origin", str(origin2))
        (repo2 / "README.md").write_text("fast\n")
        git(repo2, "add", "README.md")
        git(repo2, "commit", "-m", "initial")
        git(repo2, "push", "-u", "origin", "main")
        subprocess.run(["git", "--git-dir", str(origin2), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)

        fake_bin = root / "slow-git-bin"
        fake_bin.mkdir()
        wrapper = fake_bin / "git"
        wrapper.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys, time\n"
            "if 'fetch' in sys.argv and os.environ['PW_SLOW_REPO'] in sys.argv:\n"
            " time.sleep(5)\n"
            "os.execv(os.environ['PW_REAL_GIT'], [os.environ['PW_REAL_GIT'], *sys.argv[1:]])\n"
        )
        wrapper.chmod(0o700)
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        env = os.environ | self.env | {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "PW_REAL_GIT": str(real_git),
            "PW_SLOW_REPO": str(self.repo),
        }
        slow = subprocess.Popen(
            [str(HELPER), "prepare-start", "--repo", str(self.repo), "--issue", "141", "--risk", "R1", "--planned-branch", "fix/141-slow"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        time.sleep(0.5)
        started = time.monotonic()
        fast = subprocess.run(
            [str(HELPER), "prepare-start", "--repo", str(repo2), "--issue", "142", "--risk", "R1", "--planned-branch", "fix/142-fast"],
            text=True, capture_output=True, env=env, check=True,
        )
        elapsed = time.monotonic() - started
        slow_stdout, slow_stderr = slow.communicate(timeout=10)
        self.assertEqual(slow.returncode, 0, slow_stderr or slow_stdout)
        self.assertLess(elapsed, 2.5, fast.stdout)

    def test_skill_managed_lifecycle_preserves_primary_checkout(self) -> None:
        (self.repo / "README.md").write_text("dirty primary\n")
        (self.repo / "untracked.txt").write_text("keep me\n")
        before = self.helper_json("fingerprint", "--repo", str(self.repo))["digest"]
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "123",
            "--risk", "R2", "--planned-branch", "fix/123-example",
        )
        operation = record["operation_id"]
        self.assertEqual(record["management_mode"], "skill_managed")
        self.assertEqual(record["adapter_kind"], "git_worktree_app_server")
        self.assertEqual(record["archive_delete_contract"], "unsupported")
        self.helper_json("worktree-add", "--repo", str(self.repo), "--issue", "123", "--operation", operation)
        self.helper_json("verify-child", "--repo", str(self.repo), "--issue", "123", "--operation", operation)
        self.helper_json("record-owner", "--repo", str(self.repo), "--issue", "123", "--operation", operation, "--owner-task-id", "owner-123")
        self.helper_json("record-permission", "--repo", str(self.repo), "--issue", "123", "--operation", operation, "--evidence-sha256", "a" * 64)
        created = self.helper_json("branch-create", "--repo", str(self.repo), "--issue", "123", "--operation", operation, "--caller-task-id", "owner-123")
        self.assertEqual(created["state"], "created")
        self.assertEqual(created["actual_branch"], "fix/123-example")
        self.assertEqual(created["primary_digest_before"], created["primary_digest_after"])
        registry_dir = self.codex_home / "parallel-worktree" / record["repository_id"]
        evidence_dir = registry_dir / "evidence"
        evidence_dir.mkdir(mode=0o700)
        status_evidence = evidence_dir / "status.json"
        status_evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [{"id": "owner-123", "status": "active"}],
        }))
        status_evidence.chmod(0o600)
        status = self.helper_json(
            "status", "--repo", str(self.repo), "--issue", "123",
            "--task-evidence-file", str(status_evidence),
        )
        self.assertEqual(status["recorded_state"], "created")
        self.assertEqual(status["suggested_state"], "created")
        self.assertTrue(status["checks"]["worktree_registered"])
        status_evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [
                {"id": "owner-123", "status": "idle"},
                {"id": "unregistered-task", "status": "active"},
            ],
        }))
        status_evidence.chmod(0o600)
        drifted = self.helper_json(
            "status", "--repo", str(self.repo), "--issue", "123",
            "--task-evidence-file", str(status_evidence),
        )
        self.assertEqual(drifted["suggested_state"], "drifted")
        self.assertEqual(drifted["checks"]["task_inventory"]["extra"], ["unregistered-task"])
        status_evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [],
        }))
        status_evidence.chmod(0o600)
        orphaned = self.helper_json(
            "status", "--repo", str(self.repo), "--issue", "123",
            "--task-evidence-file", str(status_evidence),
        )
        self.assertEqual(orphaned["suggested_state"], "orphaned")
        self.assertEqual(before, self.helper_json("fingerprint", "--repo", str(self.repo))["digest"])
        self.assertEqual((self.repo / "README.md").read_text(), "dirty primary\n")
        self.assertEqual((self.repo / "untracked.txt").read_text(), "keep me\n")

    def test_verify_child_detects_untracked_drift(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "124",
            "--risk", "R1", "--planned-branch", "fix/124-example",
        )
        operation = record["operation_id"]
        added = self.helper_json("worktree-add", "--repo", str(self.repo), "--issue", "124", "--operation", operation)
        child = Path(added["worktree_path"])
        (child / "unexpected.txt").write_text("drift\n")
        result = run(
            "verify-child", "--repo", str(self.repo), "--issue", "124",
            "--operation", operation, env=self.env, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        shown = self.helper_json("show", "--repo", str(self.repo), "--issue", "124")
        self.assertEqual(shown["state"], "drifted")
        self.assertEqual(shown["resume_state"], "provisioning")

    def test_owner_observer_scope_and_lease_are_guarded_by_operation(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "125",
            "--risk", "R3", "--planned-branch", "fix/125-example",
        )
        operation = record["operation_id"]
        owner = self.helper_json(
            "record-owner", "--repo", str(self.repo), "--issue", "125",
            "--operation", operation, "--owner-task-id", "task-owner-125",
        )
        self.assertEqual(owner["owner_task_id"], "task-owner-125")
        permission = self.helper_json(
            "record-permission", "--repo", str(self.repo), "--issue", "125",
            "--operation", operation, "--evidence-sha256", "b" * 64,
        )
        self.assertEqual(permission["permission_state"], "verified")
        observer = self.helper_json(
            "observer-add", "--repo", str(self.repo), "--issue", "125",
            "--operation", operation, "--task-id", "task-review-125", "--status", "notLoaded",
        )
        self.assertEqual(observer["observer_tasks"][0]["access"], "read_only")
        scoped = self.helper_json(
            "set-scope", "--repo", str(self.repo), "--issue", "125",
            "--operation", operation, "--allow", "app", "--allow", "tests", "--forbid", ".env",
        )
        self.assertEqual(scoped["scope"]["allowed"], ["app", "tests"])
        renewed = self.helper_json(
            "renew-lease", "--repo", str(self.repo), "--issue", "125",
            "--operation", operation, "--lease-seconds", "1800",
        )
        self.assertIsNotNone(renewed["lease_expires_at"])

        wrong = run(
            "record-owner", "--repo", str(self.repo), "--issue", "125",
            "--operation", "wrong-operation", "--owner-task-id", "other",
            env=self.env, check=False,
        )
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("Operation ID", wrong.stderr)

    def test_state_machine_rejects_cleanup_jump_and_allows_error_resume(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "126",
            "--risk", "R2", "--planned-branch", "fix/126-example",
        )
        operation = record["operation_id"]
        jump = run(
            "transition", "--repo", str(self.repo), "--issue", "126",
            "--operation", operation, "--to-state", "cleanup_pending",
            env=self.env, check=False,
        )
        self.assertNotEqual(jump.returncode, 0)
        self.assertIn("dedicated cleanup commands", jump.stderr)
        blocked = self.helper_json(
            "transition", "--repo", str(self.repo), "--issue", "126",
            "--operation", operation, "--to-state", "blocked", "--error", "approval required",
        )
        self.assertEqual(blocked["resume_state"], "provisioning")
        resumed = self.helper_json(
            "transition", "--repo", str(self.repo), "--issue", "126",
            "--operation", operation, "--to-state", "provisioning",
        )
        self.assertIsNone(resumed["resume_state"])

    def test_expired_lease_rejects_mutation(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "130",
            "--risk", "R1", "--planned-branch", "fix/130-example",
        )
        registry = self.codex_home / "parallel-worktree" / record["repository_id"] / "issue-130.json"
        data = json.loads(registry.read_text())
        data["lease_expires_at"] = "2000-01-01T00:00:00Z"
        registry.write_text(json.dumps(data))
        rejected = run(
            "worktree-add", "--repo", str(self.repo), "--issue", "130",
            "--operation", record["operation_id"], env=self.env, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("lease has expired", rejected.stderr)
        resumed = self.helper_json(
            "resume-operation", "--repo", str(self.repo), "--issue", "130",
            "--previous-operation", record["operation_id"], "--expected-state", "provisioning",
        )
        self.assertNotEqual(resumed["operation_id"], record["operation_id"])
        self.helper_json(
            "worktree-add", "--repo", str(self.repo), "--issue", "130",
            "--operation", resumed["operation_id"],
        )

    def test_prepare_rejects_nonstandard_lease(self) -> None:
        rejected = run(
            "prepare-start", "--repo", str(self.repo), "--issue", "132",
            "--risk", "R1", "--planned-branch", "fix/132-example",
            "--lease-seconds", "86400", env=self.env, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("fixed at 1800", rejected.stderr)

    def test_concurrent_start_has_one_registry_writer(self) -> None:
        command = [
            str(HELPER), "prepare-start", "--repo", str(self.repo), "--issue", "134",
            "--risk", "R1", "--planned-branch", "fix/134-example",
        ]
        env = os.environ | self.env
        first = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        second = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        first_result = first.communicate()
        second_result = second.communicate()
        returncodes = sorted([first.returncode, second.returncode])
        self.assertEqual(returncodes, [0, 1])
        combined_error = first_result[1] + second_result[1]
        self.assertIn("Registry already exists", combined_error)

    def test_fetch_failure_creates_no_registry_branch_or_worktree(self) -> None:
        before = self.helper_json("fingerprint", "--repo", str(self.repo))["digest"]
        offline = Path(self.temp.name) / "origin-offline.git"
        self.origin.rename(offline)
        rejected = run(
            "prepare-start", "--repo", str(self.repo), "--issue", "135",
            "--risk", "R1", "--planned-branch", "fix/135-example",
            env=self.env, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        meta = self.helper_json("repository-id", "--repo", str(self.repo))
        registry = self.codex_home / "parallel-worktree" / meta["repository_id"] / "issue-135.json"
        self.assertFalse(registry.exists())
        self.assertNotIn("fix/135-example", git(self.repo, "branch", "--list"))
        worktrees = git(self.repo, "worktree", "list", "--porcelain")
        self.assertEqual(worktrees.count("worktree "), 1)
        self.assertEqual(before, self.helper_json("fingerprint", "--repo", str(self.repo))["digest"])

    def test_scope_rejects_dot_and_pre_staged_outside_file(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "131",
            "--risk", "R2", "--planned-branch", "fix/131-example",
        )
        operation = record["operation_id"]
        dot = run(
            "set-scope", "--repo", str(self.repo), "--issue", "131", "--operation", operation,
            "--allow", ".", env=self.env, check=False,
        )
        self.assertNotEqual(dot.returncode, 0)
        self.helper_json("worktree-add", "--repo", str(self.repo), "--issue", "131", "--operation", operation)
        self.helper_json("verify-child", "--repo", str(self.repo), "--issue", "131", "--operation", operation)
        self.helper_json("record-owner", "--repo", str(self.repo), "--issue", "131", "--operation", operation, "--owner-task-id", "owner-131")
        self.helper_json("record-permission", "--repo", str(self.repo), "--issue", "131", "--operation", operation, "--evidence-sha256", "c" * 64)
        created = self.helper_json("branch-create", "--repo", str(self.repo), "--issue", "131", "--operation", operation, "--caller-task-id", "owner-131")
        self.helper_json("set-scope", "--repo", str(self.repo), "--issue", "131", "--operation", operation, "--allow", "allowed")
        child = Path(created["worktree_path"])
        (child / "outside.txt").write_text("outside\n")
        git(child, "add", "outside.txt")
        registry_dir = self.codex_home / "parallel-worktree" / record["repository_id"]
        messages = registry_dir / "messages"
        messages.mkdir()
        message = messages / "commit.txt"
        message.write_text("test: scoped commit\n")
        rejected = run(
            "commit", "--repo", str(self.repo), "--issue", "131", "--operation", operation,
            "--caller-task-id", "owner-131", "--message-file", str(message), env=self.env, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("outside approved scope", rejected.stderr)

    def test_cleanup_requires_verified_evidence_and_two_phase_authorization(self) -> None:
        record = self.helper_json(
            "prepare-start", "--repo", str(self.repo), "--issue", "133",
            "--risk", "R2", "--planned-branch", "fix/133-example",
        )
        operation = record["operation_id"]
        self.helper_json("worktree-add", "--repo", str(self.repo), "--issue", "133", "--operation", operation)
        self.helper_json("verify-child", "--repo", str(self.repo), "--issue", "133", "--operation", operation)
        self.helper_json(
            "record-owner", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
            "--owner-task-id", "owner-133",
        )
        self.helper_json(
            "record-permission", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
            "--evidence-sha256", "d" * 64,
        )
        created = self.helper_json(
            "branch-create", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
            "--caller-task-id", "owner-133",
        )
        self.helper_json(
            "push", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
            "--caller-task-id", "owner-133",
        )
        for state in ("planning", "approved", "implementing", "pr_open", "merged"):
            self.helper_json(
                "transition", "--repo", str(self.repo), "--issue", "133",
                "--operation", operation, "--to-state", state,
            )
        bypass = run(
            "transition", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--to-state", "cleanup_ready", env=self.env, check=False,
        )
        self.assertNotEqual(bypass.returncode, 0)
        self.assertIn("dedicated cleanup commands", bypass.stderr)

        registry_dir = self.codex_home / "parallel-worktree" / record["repository_id"]
        fake_bin = Path(self.temp.name) / "bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "if sys.argv[1:3] == ['repo', 'view']:\n"
            " print(json.dumps({'nameWithOwner':'example/repo'}))\n"
            "elif sys.argv[1:3] == ['pr', 'view']:\n"
            " print(json.dumps({'number':133,'url':'https://example.test/pr/133','state':'MERGED',"
            "'baseRefName':'main','headRefName':'fix/133-example','headRefOid':os.environ['PW_TEST_HEAD']}))\n"
            "else:\n"
            " raise SystemExit(2)\n"
        )
        fake_gh.chmod(0o700)
        self.env["PATH"] = f"{fake_bin}{os.pathsep}{os.environ['PATH']}"
        self.env["PW_TEST_HEAD"] = git(Path(created["worktree_path"]), "rev-parse", "HEAD")

        self.helper_json(
            "verify-pr", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--number", "133",
        )
        evidence_dir = registry_dir / "evidence"
        evidence_dir.mkdir(mode=0o700)
        evidence = evidence_dir / "tasks.json"
        evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [{"id": "owner-133", "status": "idle"}],
        }))
        evidence.chmod(0o600)
        candidate_record = self.helper_json(
            "cleanup-prepare", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--task-evidence-file", str(evidence),
        )
        candidate = candidate_record["cleanup_candidate"]["id"]

        unauthorized = run(
            "worktree-remove", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, env=self.env, check=False,
        )
        self.assertNotEqual(unauthorized.returncode, 0)

        approval_dir = registry_dir / "approvals"
        approval_dir.mkdir(mode=0o700)
        approval = approval_dir / "cleanup.json"
        approval.write_text(json.dumps({"candidate_id": candidate, "user_approved": True}))
        approval.chmod(0o600)
        evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [{"id": "owner-133", "status": "idle"}],
        }))
        evidence.chmod(0o600)
        self.helper_json(
            "cleanup-authorize", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--candidate", candidate,
            "--approval-file", str(approval), "--task-evidence-file", str(evidence),
        )
        registry = registry_dir / "issue-133.json"
        expired = json.loads(registry.read_text())
        expired["lease_expires_at"] = "2000-01-01T00:00:00Z"
        registry.write_text(json.dumps(expired))
        resumed_cleanup = self.helper_json(
            "resume-operation", "--repo", str(self.repo), "--issue", "133",
            "--previous-operation", operation, "--expected-state", "cleanup_pending",
        )
        operation = resumed_cleanup["operation_id"]
        self.assertEqual(resumed_cleanup["state"], "merged")

        evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [{"id": "owner-133", "status": "idle"}],
        }))
        evidence.chmod(0o600)
        candidate_record = self.helper_json(
            "cleanup-prepare", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--task-evidence-file", str(evidence),
        )
        candidate = candidate_record["cleanup_candidate"]["id"]
        approval.write_text(json.dumps({"candidate_id": candidate, "user_approved": True}))
        approval.chmod(0o600)
        evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [{"id": "owner-133", "status": "idle"}],
        }))
        evidence.chmod(0o600)
        self.helper_json(
            "cleanup-authorize", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--candidate", candidate,
            "--approval-file", str(approval), "--task-evidence-file", str(evidence),
        )
        failed_cleanup = self.helper_json(
            "transition", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--to-state", "cleanup_failed", "--error", "simulated",
        )
        self.assertEqual(failed_cleanup["resume_state"], "cleanup_pending")
        recovered_cleanup = self.helper_json(
            "transition", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--to-state", "cleanup_pending",
        )
        self.assertEqual(recovered_cleanup["state"], "cleanup_pending")
        removed = self.helper_json(
            "worktree-remove", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
        )
        self.assertEqual(removed["removed"], created["worktree_path"])
        expired = json.loads(registry.read_text())
        expired["lease_expires_at"] = "2000-01-01T00:00:00Z"
        registry.write_text(json.dumps(expired))
        resumed_removed = self.helper_json(
            "resume-operation", "--repo", str(self.repo), "--issue", "133",
            "--previous-operation", operation, "--expected-state", "cleanup_pending",
        )
        operation = resumed_removed["operation_id"]
        self.assertEqual(resumed_removed["state"], "cleanup_pending")
        deleted = self.helper_json(
            "branch-delete", "--repo", str(self.repo), "--issue", "133", "--operation", operation,
        )
        self.assertTrue(deleted["deleted"])
        evidence.write_text(json.dumps({
            "cwd": created["worktree_path"],
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "test-adapter",
            "tasks": [],
        }))
        evidence.chmod(0o600)
        finalized = self.helper_json(
            "cleanup-finalize", "--repo", str(self.repo), "--issue", "133",
            "--operation", operation, "--task-evidence-file", str(evidence),
        )
        self.assertEqual(finalized["state"], "archived")


if __name__ == "__main__":
    unittest.main()
