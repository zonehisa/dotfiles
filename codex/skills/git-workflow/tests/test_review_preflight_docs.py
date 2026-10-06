from __future__ import annotations

import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ISSUE_START = " ".join((SKILL_ROOT / "references" / "issue-start.md").read_text(encoding="utf-8").split())
DELIVERY = " ".join((SKILL_ROOT / "references" / "delivery.md").read_text(encoding="utf-8").split())


class ReviewPreflightDocsTest(unittest.TestCase):
    def test_issue_request_contract_freezes_scope_and_success_before_work(self) -> None:
        for marker in ("Freeze the request contract", "Writable paths:",
                       "Acceptance criteria (observable):", "Budget (tokens / tool calls / retries",
                       "Before any work begins", "including Coordinator-only implementation",
                       "Output (changed paths / checks and results / unresolved items):"):
            with self.subTest(marker=marker):
                self.assertIn(marker, ISSUE_START)

    def test_review_gate_preserves_existing_review_and_delivery_safety(self) -> None:
        for marker in ("fresh-context `reviewer_luna`", "read-only access", "R0", "R4",
                       "review_fingerprint.py", "threat_model_supported_use_declaration_hash",
                       "Round 3 request packet", "helper cannot authenticate approval",
                       "bound to the current lifecycle/context/round and changed-path fingerprint",
                       "full `changed_paths` records emitted by `review_fingerprint.py`",
                       "does not query Git", "base ref and base SHA in the packet for audit",
                       "A ref or commit move may reuse the prior result only when the patch-base tree",
                       "a changed patch-base tree, objective, acceptance criterion, risk, target path",
                       "A base ref or commit move with the same patch-base tree",
                       "Construct `review_context_key` from objective, acceptance criteria, risk",
                       "Never backfill a missing historical hash", "P0-P2 findings block commit and PR",
                       "explicit authorization", "do not start a duplicate review or rerun"):
            with self.subTest(marker=marker):
                self.assertIn(marker, DELIVERY)
        self.assertNotIn("base/lifecycle", DELIVERY)


if __name__ == "__main__":
    unittest.main()
