from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_preflight.py"
SPEC = importlib.util.spec_from_file_location("review_preflight_test_module", SCRIPT)
assert SPEC and SPEC.loader
review_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_preflight)


class ReviewPreflightTest(unittest.TestCase):
    def packet(self) -> dict[str, object]:
        declaration = "Supported use: local source changes reviewed against the frozen acceptance criteria."
        changed_paths = [
            {
                "after": {"blob": "a" * 40, "mode": "100644", "type": "blob"},
                "before": {"blob": "b" * 40, "mode": "100644", "type": "blob"},
                "path": "codex/skills/git-workflow/references/delivery.md",
            },
            {
                "after": {"blob": "c" * 40, "mode": "100644", "type": "blob"},
                "before": {"blob": "d" * 40, "mode": "100644", "type": "blob"},
                "path": "codex/skills/git-workflow/scripts/review_preflight.py",
            },
        ]
        fingerprint = review_preflight.changed_path_records_fingerprint(changed_paths)
        return {
            "schema_version": 2,
            "repository": "acme/example",
            "issue_number": 42,
            "branch": "codex/issue-42",
            "base_ref": "origin/main",
            "base_sha": "1" * 40,
            "objective": "Require review records before completion review.",
            "acceptance_criteria": [
                "Reject incomplete review packets.",
                "Reuse an unchanged valid review without repeating evidence checks.",
            ],
            "risk": "R3",
            "risk_reason": "Changes the review delivery gate.",
            "target_paths": ["codex/skills/git-workflow/references/delivery.md",
                             "codex/skills/git-workflow/scripts/review_preflight.py"],
            "threat_model_supported_use_declaration": declaration,
            "threat_model_supported_use_declaration_hash": hashlib.sha256(
                declaration.encode("utf-8")
            ).hexdigest(),
            "patch_base_tree": "2" * 40,
            "fingerprint_scope": "changed-paths-blob-mode",
            "changed_path_fingerprint": fingerprint,
            "changed_paths": changed_paths,
            "test_evidence": [{
                "name": "review preflight unit tests",
                "command": "python3 -m unittest test_review_preflight.py",
                "result": "passed",
                "source_fingerprint": fingerprint,
            }],
            "reviewer": {
                "agent_id": "reviewer-task-1",
                "role": "reviewer_luna",
                "model": "GPT-5.6 Luna",
                "effort": "max",
                "fresh_context": True,
                "read_only": True,
                "fork_turns": "none",
            },
            "round": 1,
        }

    def prior_report(self, validated: dict[str, object], findings: dict[str, int] | None = None) -> dict[str, object]:
        return {
            "review_valid": True,
            "completed": True,
            "review_lifecycle_key": validated["review_lifecycle_key"],
            "review_context_key": validated["review_context_key"],
            "review_round_key": validated["review_round_key"],
            "changed_path_fingerprint": validated["changed_path_fingerprint"],
            "threat_model_supported_use_declaration_hash": validated[
                "threat_model_supported_use_declaration_hash"
            ],
            "reviewer_agent_id": validated["reviewer_agent_id"],
            "reviewer_role": "reviewer_luna",
            "reviewer_model": "GPT-5.6 Luna",
            "reviewer_effort": "max",
            "reviewer_read_only": True,
            "reviewer_fresh_context": True,
            "fork_turns": "none",
            "round": validated["round"],
            "findings": findings or {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
        }

    def test_complete_packet_passes_and_keys_are_stable(self) -> None:
        packet = self.packet()
        first = review_preflight.validate_packet(packet)
        second = review_preflight.validate_packet(packet)
        self.assertTrue(first["valid"])
        self.assertTrue(first["review_required"])
        self.assertEqual(first["review_context_key"], second["review_context_key"])
        self.assertEqual(first["review_round_key"], second["review_round_key"])

    def test_schema_v1_packet_is_rejected(self) -> None:
        packet = self.packet()
        packet["schema_version"] = 1
        with self.assertRaisesRegex(review_preflight.PreflightError, "schema_version is unsupported"):
            review_preflight.validate_packet(packet)

    def test_missing_immutable_declaration_hash_is_rejected(self) -> None:
        packet = self.packet()
        packet.pop("threat_model_supported_use_declaration_hash")
        with self.assertRaisesRegex(review_preflight.PreflightError, "declaration_hash is required"):
            review_preflight.validate_packet(packet)

    def test_changed_declaration_with_old_hash_is_rejected(self) -> None:
        packet = self.packet()
        packet["threat_model_supported_use_declaration"] = "A later declaration must not replace the frozen one."
        with self.assertRaisesRegex(review_preflight.PreflightError, "does not match"):
            review_preflight.validate_packet(packet)

    def test_missing_or_stale_test_evidence_is_rejected(self) -> None:
        packet = self.packet()
        packet["test_evidence"] = []
        with self.assertRaisesRegex(review_preflight.PreflightError, "test_evidence"):
            review_preflight.validate_packet(packet)

        packet = self.packet()
        packet["test_evidence"][0]["source_fingerprint"] = "c" * 64
        with self.assertRaisesRegex(review_preflight.PreflightError, "different source fingerprint"):
            review_preflight.validate_packet(packet)

    def test_unchanged_packet_reuses_review_and_keeps_blockers(self) -> None:
        packet = self.packet()
        validated = review_preflight.validate_packet(packet)
        previous = self.prior_report(validated, {"P0": 0, "P1": 1, "P2": 0, "P3": 0})
        decision = review_preflight.compare_with_previous(validated, previous)
        self.assertEqual(decision["decision"], "reuse_existing_review")
        self.assertTrue(decision["skip_redundant_review"])
        self.assertTrue(decision["delivery_blocked"])
        self.assertEqual(decision["findings"]["P1"], 1)

    def test_changed_fingerprint_requires_next_round_with_same_reviewer(self) -> None:
        packet = self.packet()
        previous_preflight = review_preflight.validate_packet(packet)
        previous = self.prior_report(previous_preflight)
        packet["round"] = 2
        packet["changed_paths"][0]["after"]["blob"] = "e" * 40
        packet["changed_path_fingerprint"] = review_preflight.changed_path_records_fingerprint(
            packet["changed_paths"]
        )
        packet["test_evidence"][0]["source_fingerprint"] = packet["changed_path_fingerprint"]
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "next_round_required")
        self.assertTrue(decision["ready_to_submit"])
        self.assertFalse(decision["skip_redundant_review"])

    def test_changed_acceptance_criteria_requires_new_reviewer_lifecycle(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["acceptance_criteria"].append("The changed context gets a new review lifecycle.")
        packet["reviewer"]["agent_id"] = "reviewer-task-2"
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "new_lifecycle_required")
        self.assertTrue(decision["fresh_reviewer_required"])
        self.assertTrue(decision["ready_to_submit"])

    def test_changed_objective_requires_new_reviewer_lifecycle(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["objective"] = "A changed objective is a new review context."
        packet["reviewer"]["agent_id"] = "reviewer-task-2"
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "new_lifecycle_required")
        self.assertTrue(decision["fresh_reviewer_required"])
        self.assertTrue(decision["ready_to_submit"])

    def test_changed_target_path_set_requires_new_reviewer_lifecycle(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["target_paths"].append("codex/skills/git-workflow/tests/new_test.py")
        packet["reviewer"]["agent_id"] = "reviewer-task-2"
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "new_lifecycle_required")
        self.assertTrue(decision["fresh_reviewer_required"])
        self.assertTrue(decision["ready_to_submit"])

    def test_base_ref_and_sha_move_with_same_tree_reuses_review(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["base_ref"] = "origin/stable"
        packet["base_sha"] = "3" * 40
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "reuse_existing_review")
        self.assertTrue(decision["skip_redundant_review"])
        self.assertFalse(decision["delivery_blocked"])

    def test_changed_patch_base_tree_requires_new_reviewer_lifecycle(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["patch_base_tree"] = "3" * 40
        packet["reviewer"]["agent_id"] = "reviewer-task-2"
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "new_lifecycle_required")
        self.assertTrue(decision["fresh_reviewer_required"])
        self.assertTrue(decision["ready_to_submit"])

    def test_changed_path_outside_target_scope_is_rejected(self) -> None:
        packet = self.packet()
        packet["changed_paths"][0]["path"] = "unlisted/secret.py"
        packet["changed_paths"].sort(key=lambda record: record["path"])
        packet["changed_path_fingerprint"] = review_preflight.changed_path_records_fingerprint(
            packet["changed_paths"]
        )
        with self.assertRaisesRegex(review_preflight.PreflightError,
                                    "target_paths must include every changed path"):
            review_preflight.validate_packet(packet)

    def test_omitted_changed_path_does_not_match_original_fingerprint(self) -> None:
        packet = self.packet()
        packet["changed_paths"] = packet["changed_paths"][:1]
        with self.assertRaisesRegex(review_preflight.PreflightError,
                                    "changed_path_fingerprint does not match changed_paths records"):
            review_preflight.validate_packet(packet)

    def test_new_declaration_hash_starts_a_new_lifecycle(self) -> None:
        packet = self.packet()
        previous = self.prior_report(review_preflight.validate_packet(packet))
        packet["threat_model_supported_use_declaration"] = "A newly frozen declaration for a new review lifecycle."
        packet["threat_model_supported_use_declaration_hash"] = hashlib.sha256(
            packet["threat_model_supported_use_declaration"].encode("utf-8")
        ).hexdigest()
        packet["reviewer"]["agent_id"] = "reviewer-task-2"
        current = review_preflight.validate_packet(packet)
        decision = review_preflight.compare_with_previous(current, previous)
        self.assertEqual(decision["decision"], "new_lifecycle_required")
        self.assertTrue(decision["ready_to_submit"])

    def test_round_three_requires_explicit_user_approval_record(self) -> None:
        packet = self.packet()
        packet["round"] = 3
        with self.assertRaisesRegex(review_preflight.PreflightError,
                                    "context-bound direct user approval record"):
            review_preflight.validate_packet(packet)
        bound = review_preflight.validate_packet(self.packet())
        packet["round3_approval_record"] = {
            "approved": True,
            "approval_source": "direct_user",
            "approval_reference": "fixture:approval-reference",
            "review_lifecycle_key": bound["review_lifecycle_key"],
            "review_context_key": bound["review_context_key"],
            "review_round_key": bound["review_round_key"],
            "changed_path_fingerprint": bound["changed_path_fingerprint"],
            "threat_model_supported_use_declaration_hash": bound[
                "threat_model_supported_use_declaration_hash"
            ],
            "round": 3,
        }
        self.assertTrue(review_preflight.validate_packet(packet)["valid"])

    def test_round_three_rejects_stale_or_unbound_approval_record(self) -> None:
        packet = self.packet()
        bound = review_preflight.validate_packet(packet)
        packet["round"] = 3
        packet["round3_approval_record"] = {
            "approved": True,
            "approval_source": "direct_user",
            "approval_reference": "fixture:approval-reference",
            "review_lifecycle_key": bound["review_lifecycle_key"],
            "review_context_key": bound["review_context_key"],
            "review_round_key": bound["review_round_key"],
            "changed_path_fingerprint": bound["changed_path_fingerprint"],
            "threat_model_supported_use_declaration_hash": bound[
                "threat_model_supported_use_declaration_hash"
            ],
            "round": 3,
        }
        packet["round3_approval_record"]["review_context_key"] = "0" * 64
        with self.assertRaisesRegex(review_preflight.PreflightError,
                                    "not bound to current review_context_key"):
            review_preflight.validate_packet(packet)

    def test_invalid_previous_report_cannot_authorize_reuse(self) -> None:
        current = review_preflight.validate_packet(self.packet())
        with self.assertRaisesRegex(review_preflight.PreflightError, "incomplete or invalid"):
            review_preflight.compare_with_previous(current, {"review_valid": False})

    def test_cli_accepts_complete_packet(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-preflight-cli-") as directory:
            packet_path = Path(directory) / "packet.json"
            packet_path.write_text(json.dumps(self.packet()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--packet", str(packet_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_cli_rejects_incomplete_packet_before_submission(self) -> None:
        packet = self.packet()
        packet.pop("threat_model_supported_use_declaration_hash")
        with tempfile.TemporaryDirectory(prefix="review-preflight-cli-") as directory:
            packet_path = Path(directory) / "packet.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--packet", str(packet_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("declaration_hash is required", result.stderr)

    def test_cli_compare_skips_duplicate_review_for_exact_prior_result(self) -> None:
        packet = self.packet()
        validated = review_preflight.validate_packet(packet)
        previous = self.prior_report(validated)
        with tempfile.TemporaryDirectory(prefix="review-preflight-compare-") as directory:
            packet_path = Path(directory) / "packet.json"
            report_path = Path(directory) / "review-result.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            report_path.write_text(json.dumps(previous), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "compare", "--packet", str(packet_path),
                 "--previous-report", str(report_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "reuse_existing_review")


if __name__ == "__main__":
    unittest.main()
