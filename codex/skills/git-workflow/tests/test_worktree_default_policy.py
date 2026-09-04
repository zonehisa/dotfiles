#!/usr/bin/env python3

"""Keep the R1-R4 Issue Worktree-default route synchronized across policy documents."""

from __future__ import annotations

import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CODEX_ROOT = SKILL_ROOT.parents[1]
REPO_ROOT = CODEX_ROOT.parent
GLOBAL_AGENTS = CODEX_ROOT / "AGENTS.md"
README = REPO_ROOT / "README.md"
POLICY = REPO_ROOT / "policies" / "development-workflow.md"
GIT_WORKFLOW = SKILL_ROOT / "SKILL.md"
ISSUE_START = SKILL_ROOT / "references" / "issue-start.md"
DELIVERY = SKILL_ROOT / "references" / "delivery.md"
WORKTREE = CODEX_ROOT / "skills" / "parallel-worktree" / "SKILL.md"
LIFECYCLE = CODEX_ROOT / "skills" / "parallel-worktree" / "references" / "lifecycle.md"
PARALLEL_OPENAI_YAML = CODEX_ROOT / "skills" / "parallel-worktree" / "agents" / "openai.yaml"

POLICY_DOCUMENTS = (GLOBAL_AGENTS, README, POLICY, GIT_WORKFLOW, ISSUE_START, DELIVERY, WORKTREE, LIFECYCLE)


class WorktreeDefaultPolicyTest(unittest.TestCase):
    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_r1_r4_documents_require_origin_based_issue_worktree(self) -> None:
        for path in POLICY_DOCUMENTS:
            content = self.read(path)
            with self.subTest(path=path):
                self.assertRegex(content, r"R1.?R4")
                self.assertRegex(content, r"Worktree")
                self.assertRegex(content, r"origin/(?:<default-branch>|main)")

    def test_only_r0_may_stay_in_clean_checkout(self) -> None:
        for path in POLICY_DOCUMENTS:
            content = self.read(path)
            with self.subTest(path=path):
                self.assertRegex(content, r"R0")
                self.assertIn("checkout", content)

    def test_stale_conditional_only_route_is_absent(self) -> None:
        for path in POLICY_DOCUMENTS:
            content = self.read(path)
            with self.subTest(path=path):
                self.assertNotIn("Use a Worktree only", content)
                self.assertNotIn("conditional Worktree decision", content)
                self.assertNotIn("conditional rather than mandatory", content)

    def test_parallel_worktree_is_implicitly_available_for_new_issue_start(self) -> None:
        content = self.read(PARALLEL_OPENAI_YAML)
        self.assertIn("allow_implicit_invocation: true", content)
        self.assertNotIn("allow_implicit_invocation: false", content)


if __name__ == "__main__":
    unittest.main()
