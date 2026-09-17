from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "issue_preflight.py"
SPEC = importlib.util.spec_from_file_location("issue_preflight_test_module", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class IssuePreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="issue-preflight-test-")
        self.root = Path(self.temp.name)
        self.origin = self.root / "origin.git"
        self.repo = self.root / "work"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fixture_path = self.root / "fixture.json"
        self._git("init", "--bare", str(self.origin), cwd=self.root)
        self._git("clone", "-q", str(self.origin), str(self.repo), cwd=self.root)
        self._git("switch", "-c", "main")
        self._git("config", "user.name", "Issue Preflight Test")
        self._git("config", "user.email", "issue-preflight@example.invalid")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-qm", "initial")
        self._git("push", "-qu", "origin", "main")
        remote = "https://user:secret@github.com/acme/demo.git"
        self._git("remote", "set-url", "origin", remote)
        self._git("config", f"url.{self.origin}.insteadOf", remote)
        self.gh_env = os.environ.copy()
        self.gh_env["PATH"] = f"{self.bin}:{self.gh_env.get('PATH', '')}"
        self.gh_env["PREFLIGHT_FIXTURE"] = str(self.fixture_path)
        self._write_gh_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, *args: str, cwd: Path | None = None, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo,
            check=False,
            capture_output=True,
            text=True,
            env=self.gh_env if hasattr(self, "gh_env") else None,
        )
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def _write_gh_fixture(self, *, issue_body: str = "", pr_list: list[dict[str, object]] | None = None) -> None:
        issue = {
            "number": 106,
            "title": "Implement feature",
            "body": issue_body,
            "state": "OPEN",
            "url": "https://github.com/acme/demo/issues/106",
            "updatedAt": "2026-09-16T00:00:00Z",
            "closedAt": None,
            "labels": [],
        }
        fixture = {
            "repo": {"nameWithOwner": "acme/demo", "defaultBranchRef": {"name": "main"}},
            "issue": issue,
            "timeline": [],
            "pr_list": pr_list or [],
            "pr_views": {},
        }
        self.fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
        (self.bin / "gh").write_text(
            textwrap.dedent(
                """
                #!/usr/bin/env python3
                import json, os, sys
                from pathlib import Path
                data = json.loads(Path(os.environ["PREFLIGHT_FIXTURE"]).read_text())
                args = sys.argv[1:]
                if args[:2] == ["repo", "view"]:
                    value = data["repo"]
                elif args[:2] == ["issue", "view"]:
                    value = data["issue"]
                elif args[:1] == ["api"]:
                    value = data["timeline"]
                elif args[:2] == ["pr", "list"]:
                    value = data["pr_list"]
                elif args[:2] == ["pr", "view"]:
                    number = next((item for item in args if item.isdigit()), "0")
                    value = data.get("pr_views", {}).get(number)
                    if value is None:
                        print("missing PR", file=sys.stderr)
                        raise SystemExit(1)
                else:
                    print("unexpected gh call", file=sys.stderr)
                    raise SystemExit(1)
                print(json.dumps(value))
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (self.bin / "gh").chmod(0o755)

    def collect(self, criteria: list[dict[str, object]], *, issue_body: str = "", target: str = "main") -> dict[str, object]:
        self._write_gh_fixture(issue_body=issue_body)
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            return preflight.collect_evidence(self.repo, 106, criteria=criteria, target=target, fetch=True)

    def bind_assessment(self, evidence: dict[str, object], criteria: list[dict[str, object]], status: str, rationale: str, residual: str) -> list[dict[str, object]]:
        target_sha = str((evidence["current_target"])["sha"])
        issue_hash = str((evidence["issue_relevant"])["sha256"])
        result = json.loads(json.dumps(criteria))
        for item in result:
            item["assessment"] = {
                "status": status,
                "rationale": rationale,
                "residual_scope": residual,
                "assessed_target_sha": target_sha,
                "assessed_issue_relevant_sha256": issue_hash,
            }
        return result

    def test_source_stub_with_matching_keyword_stays_unknown_without_assessment(self) -> None:
        (self.repo / "app.py").write_text("def save_eta():\n    pass\n", encoding="utf-8")
        self._git("add", "app.py")
        self._git("commit", "-qm", "stub")
        self._git("push", "-q", "origin", "main")
        criteria = [{"id": "eta", "requirement": "save_eta persists the value", "source": [{"path": "app.py"}], "search": [{"path": "app.py", "literal": "save_eta"}]}]
        first = self.collect(criteria)
        self.assertEqual(first["decision"], "unknown")
        self.assertEqual(first["requirements"][0]["status"], "unknown")

    def test_present_without_linked_pr_can_satisfy_with_bound_assessment(self) -> None:
        (self.repo / "feature.py").write_text("def feature():\n    return True\n", encoding="utf-8")
        (self.repo / "test_feature.py").write_text("def test_feature(): pass\n", encoding="utf-8")
        self._git("add", "feature.py", "test_feature.py")
        self._git("commit", "-qm", "feature")
        self._git("push", "-q", "origin", "main")
        criteria = [{"id": "feature", "requirement": "feature exists", "source": [{"path": "feature.py"}], "tests": [{"path": "test_feature.py"}]}]
        first = self.collect(criteria)
        assessed = self.bind_assessment(first, criteria, "satisfied", "Latest source and regression test satisfy the requirement.", "No residual scope.")
        second = self.collect(assessed)
        self.assertEqual(second["decision"], "satisfied")
        self.assertTrue(second["no_edit_or_pr"])
        self.assertEqual(second["related_prs"]["items"], [])
        self.assertEqual(second["repository"]["remote"], "https://github.com/acme/demo")

    def test_related_context_uses_all_states_and_skips_issue_or_same_title_noise(self) -> None:
        self._write_gh_fixture(
            issue_body="Related to #201\nDepends on #42",
            pr_list=[
                {"number": 201, "title": "Implement feature", "body": "", "state": "MERGED", "url": "https://github.com/acme/demo/pull/201"},
                {"number": 202, "title": "Implement feature", "body": "Unrelated work", "state": "CLOSED", "url": "https://github.com/acme/demo/pull/202"},
            ],
        )
        timeline = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        timeline["timeline"] = [{"event": "cross-referenced", "source": {"issue": {"number": 203, "pull_request": {"url": "https://github.com/acme/demo/pull/203"}}}}]
        timeline["pr_views"] = {"203": {"number": 203, "title": "Typed link", "body": "", "state": "OPEN", "url": "https://github.com/acme/demo/pull/203"}}
        self.fixture_path.write_text(json.dumps(timeline), encoding="utf-8")
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            evidence = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        related = evidence["related_prs"]
        self.assertEqual(related["status"], "ok")
        self.assertEqual([item["number"] for item in related["items"]], [201, 203])
        self.assertEqual(related["body_reference_numbers"], [201])
        self.assertNotIn(202, [item["number"] for item in related["items"]])

    def test_related_context_includes_all_state_pr_for_current_non_target_branch(self) -> None:
        self._git("switch", "-c", "codex/issue-106")
        self._write_gh_fixture(
            pr_list=[
                {"number": 204, "title": "Branch linked", "body": "", "state": "OPEN", "url": "https://github.com/acme/demo/pull/204", "headRefName": "codex/issue-106"},
            ],
        )
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            evidence = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        related = evidence["related_prs"]
        self.assertEqual(related["status"], "ok")
        self.assertEqual([item["number"] for item in related["items"]], [204])
        self.assertEqual(related["current_branch"], "codex/issue-106")
        self.assertEqual(related["current_branch_reference_numbers"], [204])


    def test_partial_gap_is_needs_work_only_with_missing_assessment(self) -> None:
        (self.repo / "feature.py").write_text("present\n", encoding="utf-8")
        self._git("add", "feature.py")
        self._git("commit", "-qm", "partial")
        self._git("push", "-q", "origin", "main")
        criteria = [
            {"id": "present", "requirement": "existing part", "source": [{"path": "feature.py"}]},
            {"id": "gap", "requirement": "missing part", "source": [{"path": "missing.py", "exists": False}]},
        ]
        first = self.collect(criteria)
        assessed = self.bind_assessment(first, criteria, "missing", "The second requirement is absent in the latest target.", "Add the missing implementation and test.")
        target_sha = str(first["current_target"]["sha"])
        issue_hash = str(first["issue_relevant"]["sha256"])
        assessed[0]["assessment"] = {
            "status": "satisfied",
            "rationale": "The existing part is present in the latest target.",
            "residual_scope": "None for this requirement.",
            "assessed_target_sha": target_sha,
            "assessed_issue_relevant_sha256": issue_hash,
        }
        second = self.collect(assessed)
        self.assertEqual(second["decision"], "needs_work")
        self.assertEqual([item["status"] for item in second["requirements"]], ["satisfied", "missing"])

    def test_issue_and_target_changes_invalidate_evidence(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        first = self.collect(criteria)
        assessed = self.bind_assessment(first, criteria, "missing", "The requested behavior is not present.", "Implement behavior.")
        packet = self.collect(assessed)
        (self.repo / "target-moved.txt").write_text("target moved\n", encoding="utf-8")
        self._git("add", "target-moved.txt")
        self._git("commit", "-qm", "move target")
        self._git("push", "-q", "origin", "main")
        self._write_gh_fixture(issue_body="Issue changed after evidence")
        self.assertEqual(packet["decision"], "needs_work")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            result = preflight.validate_evidence(self.repo, packet, refresh=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("current target SHA changed" in error for error in result["errors"]))
        self.assertTrue(any("Issue relevant content changed" in error for error in result["errors"]))

    def test_fetch_failure_is_unknown(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        with mock.patch.object(preflight, "fetch_origin", return_value=(False, "fatal: unable to access 'https://user:secret@example.com/repo.git' and 'https://TOKEN@example.com/repo.git': network unavailable")):
            with mock.patch.dict(os.environ, self.gh_env, clear=True):
                evidence = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        self.assertEqual(evidence["decision"], "unknown")
        self.assertEqual(evidence["collection"]["fetch"]["status"], "unknown")
        self.assertNotIn("secret", json.dumps(evidence))
        self.assertNotIn("TOKEN", json.dumps(evidence))
        self.assertIn("<redacted>", evidence["collection"]["fetch"]["error"])

    def test_github_failure_and_bounded_related_list_are_unknown(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        with mock.patch.object(preflight, "run_gh", side_effect=preflight.PreflightError("gh unavailable")):
            with mock.patch.dict(os.environ, self.gh_env, clear=True):
                failed = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        self.assertEqual(failed["decision"], "unknown")
        self.assertEqual(failed["collection"]["issue"]["status"], "unknown")

        noisy = [{"number": index, "title": "noise", "body": "", "state": "CLOSED"} for index in range(1, 1001)]
        self._write_gh_fixture(pr_list=noisy)
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            truncated = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        self.assertEqual(truncated["related_prs"]["status"], "unknown")
        self.assertTrue(any("bounded" in error for error in truncated["related_prs"]["errors"]))

    def test_related_lookup_failure_blocks_a_bound_missing_assessment(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        self._write_gh_fixture(issue_body="Related to #201", pr_list=[])
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            first = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        assessed = self.bind_assessment(first, criteria, "missing", "The requested behavior is absent.", "Implement the behavior.")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            evidence = preflight.collect_evidence(self.repo, 106, criteria=assessed, target="main", fetch=True)
        self.assertEqual(evidence["requirements"][0]["status"], "missing")
        self.assertEqual(evidence["related_prs"]["status"], "unknown")
        self.assertEqual(evidence["collection"]["related_prs"]["status"], "unknown")
        self.assertEqual(evidence["decision"], "unknown")

    def test_repository_binding_mismatch_is_unknown_and_credentials_do_not_leak(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        fixture["repo"]["nameWithOwner"] = "other/repository"
        self.fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            evidence = preflight.collect_evidence(self.repo, 106, criteria=criteria, target="main", fetch=True)
        self.assertEqual(evidence["decision"], "unknown")
        self.assertNotIn("secret", json.dumps(evidence))

    def test_creation_base_sha_survives_moving_historical_ref_and_missing_sha_is_invalid(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        self._git("branch", "history")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            packet = preflight.collect_evidence(
                self.repo, 106, criteria=criteria, target="main", creation_base="history", fetch=True,
            )
        original_base_sha = packet["creation_base"]["sha"]
        self._git("switch", "history")
        (self.repo / "history-only.txt").write_text("moved historical ref\n", encoding="utf-8")
        self._git("add", "history-only.txt")
        self._git("commit", "-qm", "move historical ref")
        self._git("switch", "main")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            refreshed = preflight.validate_evidence(self.repo, packet, refresh=True)
        self.assertTrue(refreshed["valid"])
        self.assertEqual(refreshed["current"]["creation_base"]["ref"], "refs/heads/history")
        self.assertEqual(refreshed["current"]["creation_base"]["sha"], original_base_sha)

        missing = json.loads(json.dumps(packet))
        missing["creation_base"]["sha"] = "0" * 40
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            invalid = preflight.validate_evidence(self.repo, missing, refresh=True)
        self.assertFalse(invalid["valid"])
        self.assertIn("creation base SHA is unavailable", invalid["errors"])

    def test_evidence_from_another_origin_is_rejected_even_for_same_tree_and_issue(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        packet = self.collect(criteria)
        # Keep the target tree, commit, and Issue fixture unchanged while
        # changing only the checkout's origin identity.
        self._git("remote", "set-url", "origin", "https://github.com/other/repository.git")
        with mock.patch.dict(os.environ, self.gh_env, clear=True):
            result = preflight.validate_evidence(self.repo, packet, refresh=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("repository" in error for error in result["errors"]))

    def test_target_name_resolves_to_live_origin_remote(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        evidence = self.collect(criteria, target="main")
        self.assertEqual(evidence["current_target"]["ref"], "refs/remotes/origin/main")
        with self.assertRaises(preflight.PreflightError):
            preflight.collect_evidence(self.repo, 106, criteria=criteria, target=evidence["current_target"]["sha"], fetch=False)

    def test_pre_pr_conflict_stale_head_and_missing_evidence_are_denied(self) -> None:
        initial = self._git("rev-parse", "HEAD")
        (self.repo / "conflict.txt").write_text("target\n", encoding="utf-8")
        self._git("add", "conflict.txt")
        self._git("commit", "-qm", "target conflict")
        target = self._git("rev-parse", "HEAD")
        self._git("switch", "-c", "conflicting-head", initial)
        (self.repo / "conflict.txt").write_text("head\n", encoding="utf-8")
        self._git("add", "conflict.txt")
        self._git("commit", "-qm", "head conflict")
        head = self._git("rev-parse", "HEAD")
        conflict = preflight.validate_pr(self.repo, base_ref=target, head_sha=head, expected_head_sha="0" * 40)
        self.assertEqual(conflict["status"], "deny")
        self.assertIn("submitted head SHA is stale", conflict["reasons"])
        self.assertIn("virtual merge has conflicts", conflict["reasons"])

        result = subprocess.run(
            ["python3", str(SCRIPT), "pre-pr", "--repo", str(self.repo), "--base", target, "--head", head, "--expected-head", head],
            text=True, capture_output=True, check=False, env=self.gh_env,
        )
        self.assertEqual(result.returncode, 2)
        output = json.loads(result.stdout)
        self.assertFalse(output["ready"])
        self.assertEqual(output["status"], "unknown")
        self.assertTrue(any("evidence" in reason for reason in output["reasons"]))

    def test_pre_pr_denies_when_worktree_status_cannot_be_verified(self) -> None:
        base = self._git("rev-parse", "HEAD")
        self._git("switch", "-c", "status-check-head")
        (self.repo / "status-check.txt").write_text("change\n", encoding="utf-8")
        self._git("add", "status-check.txt")
        self._git("commit", "-qm", "status check head")
        head = self._git("rev-parse", "HEAD")
        real_run = preflight._run

        def fail_status(command, **kwargs):
            if "status" in command:
                return subprocess.CompletedProcess(command, 7, b"", b"status unavailable")
            return real_run(command, **kwargs)

        with mock.patch.object(preflight, "_run", side_effect=fail_status):
            result = preflight.validate_pr(self.repo, base_ref=base, head_sha=head, expected_head_sha=head)
        self.assertEqual(result["status"], "deny")
        self.assertIn("worktree status could not be verified", result["reasons"])

    def test_pre_pr_rejects_base_ref_that_does_not_match_evidence_target(self) -> None:
        criteria = [{"id": "readme", "requirement": "fixture readme", "source": [{"path": "README.md"}]}]
        first = self.collect(criteria)
        assessed = self.bind_assessment(first, criteria, "missing", "The requested behavior is absent.", "Implement the behavior.")
        packet = self.collect(assessed)
        packet_path = self.root / "preflight.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        target = str(packet["current_target"]["sha"])

        self._git("switch", "-c", "other-base", target)
        (self.repo / "other-base.txt").write_text("other base\n", encoding="utf-8")
        self._git("add", "other-base.txt")
        self._git("commit", "-qm", "other base")
        other_base = self._git("rev-parse", "HEAD")
        self._git("switch", "-c", "submitted", target)
        (self.repo / "submitted.txt").write_text("submitted change\n", encoding="utf-8")
        self._git("add", "submitted.txt")
        self._git("commit", "-qm", "submitted change")
        head = self._git("rev-parse", "HEAD")
        result = subprocess.run(
            [
                "python3", str(SCRIPT), "pre-pr", "--repo", str(self.repo),
                "--base", "other-base", "--head", head, "--expected-head", head,
                "--evidence-file", str(packet_path),
            ],
            text=True, capture_output=True, check=False, env=self.gh_env,
        )
        self.assertEqual(result.returncode, 2)
        output = json.loads(result.stdout)
        self.assertFalse(output["ready"])
        self.assertTrue(any("base" in reason for reason in output["reasons"]))

    def test_squash_duplicate_is_denied_by_effective_merge_delta(self) -> None:
        base = self._git("rev-parse", "HEAD")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self._git("add", "feature.txt")
        self._git("commit", "-qm", "feature branch")
        head = self._git("rev-parse", "HEAD")
        self._git("switch", "-c", "main-copy", base)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self._git("add", "feature.txt")
        self._git("commit", "-qm", "squash on target")
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        self._git("add", "later.txt")
        self._git("commit", "-qm", "unrelated target change")
        target = self._git("rev-parse", "HEAD")
        result = preflight.validate_pr(self.repo, base_ref=target, head_sha=head, expected_head_sha=head)
        self.assertEqual(result["status"], "deny")
        self.assertEqual(result["changed_paths"], [])
        self.assertTrue(any("effective merge delta is empty" in reason for reason in result["reasons"]))

    def test_reverted_feature_can_be_reintroduced(self) -> None:
        base = self._git("rev-parse", "HEAD")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self._git("add", "feature.txt")
        self._git("commit", "-qm", "feature")
        self._git("rm", "-q", "feature.txt")
        self._git("commit", "-qm", "revert feature")
        target = self._git("rev-parse", "HEAD")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self._git("add", "feature.txt")
        self._git("commit", "-qm", "reintroduce feature")
        head = self._git("rev-parse", "HEAD")
        result = preflight.validate_pr(self.repo, base_ref=target, head_sha=head, expected_head_sha=head)
        self.assertEqual(result["status"], "allow")
        # A clean minimal delta remains allowable when the submitted head is an
        # independent commit against the reverted target.
        self._git("switch", "-c", "readd", target)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self._git("add", "feature.txt")
        self._git("commit", "-qm", "readd from target")
        readd = self._git("rev-parse", "HEAD")
        allowed = preflight.validate_pr(self.repo, base_ref=target, head_sha=readd, expected_head_sha=readd)
        self.assertEqual(allowed["status"], "allow")
        self.assertEqual(allowed["changed_paths"], ["feature.txt"])


if __name__ == "__main__":
    unittest.main()
