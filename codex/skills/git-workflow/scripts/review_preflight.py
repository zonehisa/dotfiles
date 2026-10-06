#!/usr/bin/env python3
"""Check a frozen completion-review packet and safe reuse of a prior review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = 2
FINGERPRINT_SCOPE = "changed-paths-blob-mode"
SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
GIT_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
GIT_MODES = {"100644", "100755", "120000", "160000"}
GIT_OBJECT_TYPES = {"blob", "commit"}
REVIEW_RANKS = {"R1", "R2", "R3", "R4"}
REVIEWER_ROLE = "reviewer_luna"
REVIEWER_MODEL = "GPT-5.6 Luna"


class PreflightError(ValueError):
    """A required review record is missing, malformed, or stale."""


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError(f"{field} is required")
    return value


def require_digest(value: Any, field: str, pattern: re.Pattern[str]) -> str:
    result = require_text(value, field)
    if not pattern.fullmatch(result):
        raise PreflightError(f"{field} must be a full hexadecimal digest")
    return result.lower()


def require_paths(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PreflightError(f"{field} must be a non-empty array")
    result: list[str] = []
    for item in value:
        raw = require_text(item, field)
        path = PurePosixPath(raw)
        if ("\\" in raw or path.is_absolute() or ".." in path.parts or "." in path.parts
                or ".git" in path.parts or raw != path.as_posix()):
            raise PreflightError(f"{field} contains a non-normalized relative path")
        result.append(raw)
    if len(set(result)) != len(result):
        raise PreflightError(f"{field} contains duplicate paths")
    return sorted(result)


def validate_changed_path_records(value: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate canonical path records emitted by review_fingerprint.py."""
    if not isinstance(value, list) or not value:
        raise PreflightError("changed_paths must contain full fingerprint records")
    records: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"after", "before", "path"}:
            raise PreflightError(f"changed_paths[{index}] must be a full path record")
        path = require_text(item.get("path"), f"changed_paths[{index}].path")
        paths.append(path)
        entries: dict[str, Any] = {}
        for side in ("before", "after"):
            entry = item.get(side)
            if entry is None:
                entries[side] = None
                continue
            if not isinstance(entry, dict) or set(entry) != {"blob", "mode", "type"}:
                raise PreflightError(f"changed_paths[{index}].{side} must contain blob, mode, and type")
            blob = require_digest(entry.get("blob"), f"changed_paths[{index}].{side}.blob", GIT_OBJECT_ID_RE)
            mode = require_text(entry.get("mode"), f"changed_paths[{index}].{side}.mode")
            object_type = require_text(entry.get("type"), f"changed_paths[{index}].{side}.type")
            if mode not in GIT_MODES or object_type not in GIT_OBJECT_TYPES:
                raise PreflightError(f"changed_paths[{index}].{side} has an unsupported Git mode or object type")
            entries[side] = {"blob": blob, "mode": mode, "type": object_type}
        if entries["before"] == entries["after"]:
            raise PreflightError(f"changed_paths[{index}] does not describe a changed Git entry")
        records.append({"after": entries["after"], "before": entries["before"], "path": path})
    normalized_paths = require_paths(paths, "changed_paths")
    if paths != normalized_paths:
        raise PreflightError("changed_paths records must be sorted by normalized path")
    return records, normalized_paths


def changed_path_records_fingerprint(records: list[dict[str, Any]]) -> str:
    """Recompute the versioned hash emitted by review_fingerprint.py."""
    payload = {"paths": records, "version": 2}
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_packet(packet: Any) -> dict[str, Any]:
    """Validate request fields before submitting a completion review."""
    if not isinstance(packet, dict):
        raise PreflightError("packet must be an object")
    risk = require_text(packet.get("risk"), "risk")
    if risk == "R0":
        return {"valid": True, "review_required": False, "decision": "review_not_required"}
    if risk not in REVIEW_RANKS:
        raise PreflightError("risk must be one of R0 through R4")
    if packet.get("schema_version") != SCHEMA_VERSION:
        raise PreflightError("schema_version is unsupported; use version 2 with complete path records")

    repository = require_text(packet.get("repository"), "repository")
    issue = packet.get("issue_number")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue < 1:
        raise PreflightError("issue_number must be a positive integer")
    branch = require_text(packet.get("branch"), "branch")
    base_ref = require_text(packet.get("base_ref"), "base_ref")
    base_sha = require_digest(packet.get("base_sha"), "base_sha", SHA1_RE)
    objective = require_text(packet.get("objective"), "objective")
    criteria = packet.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise PreflightError("acceptance_criteria must be a non-empty array")
    criteria = [require_text(item, "acceptance_criteria item") for item in criteria]
    if len(set(criteria)) != len(criteria):
        raise PreflightError("acceptance_criteria contains duplicates")
    risk_reason = require_text(packet.get("risk_reason"), "risk_reason")
    target_paths = require_paths(packet.get("target_paths"), "target_paths")

    declaration = require_text(
        packet.get("threat_model_supported_use_declaration"),
        "threat_model_supported_use_declaration",
    )
    declaration_hash = require_digest(
        packet.get("threat_model_supported_use_declaration_hash"),
        "threat_model_supported_use_declaration_hash",
        SHA256_RE,
    )
    actual_declaration_hash = hashlib.sha256(declaration.encode("utf-8")).hexdigest()
    if declaration_hash != actual_declaration_hash:
        raise PreflightError("threat model declaration hash does not match its exact text")

    patch_base_tree = require_digest(packet.get("patch_base_tree"), "patch_base_tree", SHA1_RE)
    if packet.get("fingerprint_scope") != FINGERPRINT_SCOPE:
        raise PreflightError("fingerprint_scope must be changed-paths-blob-mode")
    fingerprint = require_digest(
        packet.get("changed_path_fingerprint"), "changed_path_fingerprint", SHA256_RE
    )
    changed_path_records, changed_paths = validate_changed_path_records(packet.get("changed_paths"))
    if changed_path_records_fingerprint(changed_path_records) != fingerprint:
        raise PreflightError("changed_path_fingerprint does not match changed_paths records")
    if not set(changed_paths).issubset(target_paths):
        raise PreflightError("target_paths must include every changed path")

    evidence = packet.get("test_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise PreflightError("test_evidence must contain successful verification records")
    normalized_evidence: list[dict[str, str]] = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise PreflightError(f"test_evidence[{index}] must be an object")
        name = require_text(item.get("name"), f"test_evidence[{index}].name")
        command = require_text(item.get("command"), f"test_evidence[{index}].command")
        if item.get("result") != "passed":
            raise PreflightError(f"test_evidence[{index}] is not successful")
        source_fingerprint = require_digest(
            item.get("source_fingerprint"),
            f"test_evidence[{index}].source_fingerprint",
            SHA256_RE,
        )
        if source_fingerprint != fingerprint:
            raise PreflightError(f"test_evidence[{index}] is bound to a different source fingerprint")
        normalized_evidence.append({
            "name": name,
            "command": command,
            "result": "passed",
            "source_fingerprint": source_fingerprint,
        })

    reviewer = packet.get("reviewer")
    if not isinstance(reviewer, dict):
        raise PreflightError("reviewer must be an object")
    if reviewer.get("role") != REVIEWER_ROLE or reviewer.get("model") != REVIEWER_MODEL:
        raise PreflightError("reviewer must preserve the configured independent reviewer role and model")
    if reviewer.get("effort") != "max" or reviewer.get("fresh_context") is not True:
        raise PreflightError("reviewer must use max effort in a fresh context")
    if reviewer.get("read_only") is not True or reviewer.get("fork_turns") != "none":
        raise PreflightError("reviewer must be read-only with no inherited implementation turns")
    reviewer_id = require_text(reviewer.get("agent_id"), "reviewer.agent_id")
    round_number = packet.get("round")
    if isinstance(round_number, bool) or not isinstance(round_number, int) or not 1 <= round_number <= 3:
        raise PreflightError("round must be an integer from 1 through 3")
    lifecycle_key = canonical_hash({
        "repository": repository,
        "issue_number": issue,
        "branch": branch,
        "patch_base_tree": patch_base_tree,
        "reviewer_role": REVIEWER_ROLE,
    })
    context_key = canonical_hash({
        "objective": objective,
        "acceptance_criteria": criteria,
        "risk": risk,
        "target_paths": target_paths,
        "threat_model_supported_use_declaration_hash": declaration_hash,
    })
    round_key = canonical_hash({
        "review_lifecycle_key": lifecycle_key,
        "patch_base_tree": patch_base_tree,
        "changed_path_fingerprint": fingerprint,
    })
    if round_number == 3:
        approval = packet.get("round3_approval_record")
        if not isinstance(approval, dict) or approval.get("approved") is not True:
            raise PreflightError("Round 3 requires a context-bound direct user approval record")
        if approval.get("approval_source") != "direct_user":
            raise PreflightError("Round 3 approval record must identify direct user approval")
        require_text(approval.get("approval_reference"), "round3_approval_record.approval_reference")
        expected_bindings = {
            "review_lifecycle_key": lifecycle_key,
            "review_context_key": context_key,
            "review_round_key": round_key,
            "changed_path_fingerprint": fingerprint,
            "threat_model_supported_use_declaration_hash": declaration_hash,
        }
        for field, expected in expected_bindings.items():
            if approval.get(field) != expected:
                raise PreflightError(f"Round 3 approval record is not bound to current {field}")
        if isinstance(approval.get("round"), bool) or approval.get("round") != 3:
            raise PreflightError("Round 3 approval record must be bound to round 3")

    return {
        "valid": True,
        "review_required": True,
        "decision": "review_required",
        "review_lifecycle_key": lifecycle_key,
        "review_context_key": context_key,
        "review_round_key": round_key,
        "patch_base_tree": patch_base_tree,
        "changed_path_fingerprint": fingerprint,
        "changed_paths": changed_paths,
        "threat_model_supported_use_declaration_hash": declaration_hash,
        "test_evidence_hash": canonical_hash(normalized_evidence),
        "reviewer_agent_id": reviewer_id,
        "round": round_number,
    }


def compare_with_previous(current: dict[str, Any], previous: Any) -> dict[str, Any]:
    """Reuse an exact valid review or require the appropriate bounded review lifecycle."""
    if not isinstance(previous, dict):
        raise PreflightError("previous review result must be an object")
    findings = previous.get("findings")
    priorities = ("P0", "P1", "P2", "P3")
    if (previous.get("review_valid") is not True or previous.get("completed") is not True
            or not isinstance(findings, dict)
            or any(isinstance(findings.get(key), bool) or not isinstance(findings.get(key), int)
                   or findings[key] < 0 for key in priorities)):
        raise PreflightError("previous review result is incomplete or invalid")
    keys = ("review_lifecycle_key", "review_context_key", "review_round_key",
            "changed_path_fingerprint", "threat_model_supported_use_declaration_hash",
            "reviewer_agent_id")
    if any(not isinstance(previous.get(key), str) or not previous[key] for key in keys):
        raise PreflightError("previous review result is missing bound identity fields")
    if (previous.get("reviewer_role") != REVIEWER_ROLE
            or previous.get("reviewer_model") != REVIEWER_MODEL
            or previous.get("reviewer_effort") != "max"
            or previous.get("reviewer_read_only") is not True
            or previous.get("reviewer_fresh_context") is not True
            or previous.get("fork_turns") != "none"):
        raise PreflightError("previous review result does not prove the configured independent reviewer route")
    prior_round = previous.get("round")
    if isinstance(prior_round, bool) or not isinstance(prior_round, int) or not 1 <= prior_round <= 3:
        raise PreflightError("previous review result has an invalid round")

    new_lifecycle = (
        current["review_lifecycle_key"] != previous["review_lifecycle_key"]
        or current["review_context_key"] != previous["review_context_key"]
        or current["threat_model_supported_use_declaration_hash"]
        != previous["threat_model_supported_use_declaration_hash"]
    )
    if new_lifecycle:
        ready = current["round"] == 1 and current["reviewer_agent_id"] != previous["reviewer_agent_id"]
        return {
            "decision": "new_lifecycle_required",
            "ready_to_submit": ready,
            "fresh_reviewer_required": True,
        }

    same_round = (
        current["review_round_key"] == previous["review_round_key"]
        and current["changed_path_fingerprint"] == previous["changed_path_fingerprint"]
    )
    if same_round:
        identity_matches = (
            current["round"] == prior_round
            and current["reviewer_agent_id"] == previous["reviewer_agent_id"]
        )
        return {
            "decision": "reuse_existing_review" if identity_matches else "blocked_review_identity_mismatch",
            "ready_to_submit": identity_matches,
            "skip_redundant_review": identity_matches,
            "delivery_blocked": sum(findings[key] for key in ("P0", "P1", "P2")) > 0,
            "findings": {key: findings[key] for key in priorities},
        }

    next_round = (
        current["round"] == prior_round + 1
        and current["round"] <= 3
        and current["reviewer_agent_id"] == previous["reviewer_agent_id"]
    )
    return {
        "decision": "next_round_required" if next_round else "blocked_round_or_reviewer_mismatch",
        "ready_to_submit": next_round,
        "skip_redundant_review": False,
        "same_reviewer_required": True,
    }


def read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except OSError as exc:
        raise PreflightError("cannot read JSON input") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError("input is not valid JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a review request packet")
    validate.add_argument("--packet", required=True)
    compare = commands.add_parser("compare", help="compare against a prior review result")
    compare.add_argument("--packet", required=True)
    compare.add_argument("--previous-report", required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_packet(read_json(args.packet))
        if args.command == "compare" and result["review_required"]:
            result.update(compare_with_previous(result, read_json(args.previous_report)))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except PreflightError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
