#!/usr/bin/env python3
"""Build and validate deterministic evidence for user-visible UI deliveries.

This helper intentionally does not invoke Git. The UI source fingerprint describes only the
explicit changed-path scope using deterministic path/type/Git-mode/blob records; review_fingerprint.py
remains the source of truth for staged-target review evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from urllib.parse import urlparse


MATERIAL_PACKET_SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:")

MATERIAL_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "checkpoint_token",
        "checkpoint_scope",
        "accepted_source_fingerprint",
        "browser_executor",
        "selector",
        "browser_family",
        "automatic_fallback",
        "checked_url",
        "primary_flow_view",
        "viewport",
        "result",
        "evidence_artifacts",
        "exception_reason",
        "user_approval_evidence",
        "matching_family",
    }
)
REQUIRED_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "checkpoint_token",
        "checkpoint_scope",
        "accepted_source_fingerprint",
        "browser_executor",
        "selector",
        "browser_family",
        "automatic_fallback",
        "checked_url",
        "primary_flow_view",
        "viewport",
        "result",
        "evidence_artifacts",
    }
)
EXCEPTION_PACKET_FIELDS = frozenset(
    {"exception_reason", "user_approval_evidence", "matching_family"}
)
METADATA_FIELDS = frozenset({"generated_at", "generator_version"})


class UIEvidenceError(ValueError):
    """Raised when a source scope, packet, or metadata sidecar is unsafe or invalid."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON with deterministic key ordering and compact separators."""

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise UIEvidenceError(f"value cannot be serialized as canonical JSON: {error}") from error
    return serialized.encode("utf-8")


def _repo_root(repo: os.PathLike[str] | str) -> Path:
    try:
        root = Path(repo).resolve()
    except (OSError, RuntimeError) as error:
        raise UIEvidenceError(f"repository root cannot be resolved: {repo}") from error
    if not root.is_dir():
        raise UIEvidenceError(f"repository root is not a directory: {root}")
    return root


def normalize_scope(scope: Sequence[str] | Iterable[str]) -> list[str]:
    """Return a sorted POSIX scope and reject ambiguous or duplicate paths."""

    if isinstance(scope, (str, bytes)):
        raise UIEvidenceError("checkpoint scope must be an array of relative paths")

    normalized: list[str] = []
    seen: set[str] = set()
    try:
        items = list(scope)
    except TypeError as error:
        raise UIEvidenceError("checkpoint scope must be an iterable of relative paths") from error

    if not items:
        raise UIEvidenceError("checkpoint scope must not be empty")

    for raw_path in items:
        if not isinstance(raw_path, str):
            raise UIEvidenceError("checkpoint scope paths must be strings")
        if not raw_path or "\x00" in raw_path:
            raise UIEvidenceError("checkpoint scope contains an empty or NUL-containing path")

        # Accept a Windows separator in input only to canonicalize it; validate the
        # canonical form so .. cannot be hidden behind a different separator.
        path = raw_path.replace("\\", "/")
        if (
            path.startswith("/")
            or path.startswith("//")
            or WINDOWS_ABSOLUTE_RE.match(raw_path)
            or Path(raw_path).is_absolute()
        ):
            raise UIEvidenceError(f"checkpoint scope path must be relative: {raw_path!r}")

        components = path.split("/")
        if any(component in {"", ".", ".."} for component in components):
            raise UIEvidenceError(f"checkpoint scope path is not normalized: {raw_path!r}")
        if ".git" in components:
            raise UIEvidenceError("checkpoint scope cannot include the Git metadata directory")

        canonical_path = "/".join(components)
        if canonical_path in seen:
            raise UIEvidenceError(f"checkpoint scope contains a duplicate path: {canonical_path}")
        seen.add(canonical_path)
        normalized.append(canonical_path)

    return sorted(normalized)


def _scoped_path(root: Path, relative_path: str) -> Path:
    candidate = root.joinpath(*relative_path.split("/"))
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise UIEvidenceError(f"cannot resolve scoped path: {relative_path}") from error

    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise UIEvidenceError(f"scoped path escapes the repository: {relative_path}") from error

    try:
        candidate.lstat()
    except FileNotFoundError as error:
        raise UIEvidenceError(f"scoped path does not exist: {relative_path}") from error
    except OSError as error:
        raise UIEvidenceError(f"cannot inspect scoped path: {relative_path}") from error
    return candidate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise UIEvidenceError(f"cannot read scoped file: {path}") from error
    return digest.hexdigest()


def _git_mode(metadata: os.stat_result) -> str:
    """Return the Git mode recorded for a regular file or symlink."""

    if stat.S_ISLNK(metadata.st_mode):
        return "120000"
    return "100755" if metadata.st_mode & stat.S_IXUSR else "100644"


def source_records(repo: os.PathLike[str] | str, scope: Sequence[str] | Iterable[str]) -> list[dict[str, str]]:
    """Describe only the explicit target paths using deterministic blob/mode records.

    The scope is the caller's changed-path set.  Git/index state, mtimes, and files outside
    that scope are intentionally not consulted.  ``sha256`` is retained as a compatibility
    alias for regular-file callers; the canonical fingerprint uses ``blob`` and ``mode``.
    """

    root = _repo_root(repo)
    normalized_scope = normalize_scope(scope)
    records: list[dict[str, str]] = []

    for relative_path in normalized_scope:
        path = _scoped_path(root, relative_path)
        try:
            metadata = path.lstat()
        except OSError as error:
            raise UIEvidenceError(f"cannot inspect scoped path: {relative_path}") from error

        mode_text = _git_mode(metadata)
        if stat.S_ISREG(metadata.st_mode):
            blob = _file_sha256(path)
            records.append(
                {
                    "blob": blob,
                    "mode": mode_text,
                    "path": relative_path,
                    "sha256": blob,
                    "type": "file",
                }
            )
        elif stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(path)
            except OSError as error:
                raise UIEvidenceError(f"cannot read scoped symlink: {relative_path}") from error
            target_bytes = os.fsencode(target)
            records.append(
                {
                    "blob": hashlib.sha256(target_bytes).hexdigest(),
                    "mode": mode_text,
                    "path": relative_path,
                    "target": target,
                    "type": "symlink",
                }
            )
        else:
            raise UIEvidenceError(
                f"unsupported special file in checkpoint scope: {relative_path}"
            )

    return records


def source_fingerprint(repo: os.PathLike[str] | str, scope: Sequence[str] | Iterable[str]) -> str:
    """Hash only normalized changed-path blob/mode records, never Git/index state."""

    records = source_records(repo, scope)
    canonical_records = [
        {
            key: record[key]
            for key in ("blob", "mode", "path", "target", "type")
            if key in record
        }
        for record in records
    ]
    return hashlib.sha256(canonical_json_bytes(canonical_records)).hexdigest()


# Descriptive aliases keep call sites readable without introducing another state mechanism.
compute_source_fingerprint = source_fingerprint
build_source_fingerprint = source_fingerprint


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UIEvidenceError(f"{field} must be a non-empty string")
    return value


def _sha256(value: object, field: str) -> str:
    value = _non_empty_string(value, field)
    if not SHA256_RE.fullmatch(value):
        raise UIEvidenceError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _viewport(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise UIEvidenceError("viewport must be an object")
    allowed = {"width", "height", "device_scale_factor"}
    unknown = set(value) - allowed
    if unknown:
        raise UIEvidenceError(f"viewport has unsupported fields: {sorted(unknown)}")
    if "width" not in value or "height" not in value:
        raise UIEvidenceError("viewport requires positive width and height")

    normalized: dict[str, int] = {}
    for field in ("width", "height", "device_scale_factor"):
        if field not in value:
            continue
        field_value = value[field]
        if isinstance(field_value, bool) or not isinstance(field_value, (int, float)):
            raise UIEvidenceError(f"viewport.{field} must be a positive number")
        if field_value <= 0:
            raise UIEvidenceError(f"viewport.{field} must be positive")
        if isinstance(field_value, float) and not field_value.is_integer():
            raise UIEvidenceError(f"viewport.{field} must be an integer")
        normalized[field] = int(field_value)
    return normalized


def _artifacts(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise UIEvidenceError("evidence_artifacts must be a non-empty array")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for artifact in value:
        if not isinstance(artifact, Mapping):
            raise UIEvidenceError("each evidence artifact must be an object")
        if set(artifact) != {"id", "sha256"}:
            raise UIEvidenceError("each evidence artifact requires only id and sha256")
        artifact_id = _non_empty_string(artifact["id"], "evidence artifact id")
        if artifact_id in seen:
            raise UIEvidenceError(f"duplicate evidence artifact id: {artifact_id}")
        seen.add(artifact_id)
        normalized.append({"id": artifact_id, "sha256": _sha256(artifact["sha256"], "evidence artifact sha256")})
    return sorted(normalized, key=lambda artifact: artifact["id"])


def validate_material_packet(
    packet: Mapping[str, object],
    repo: os.PathLike[str] | str | None = None,
) -> dict[str, object]:
    """Validate and normalize the schema-versioned material browser packet."""

    if not isinstance(packet, Mapping):
        raise UIEvidenceError("material browser packet must be an object")
    keys = set(packet)
    missing = REQUIRED_PACKET_FIELDS - keys
    unknown = keys - MATERIAL_PACKET_FIELDS
    if missing:
        raise UIEvidenceError(f"material browser packet is missing fields: {sorted(missing)}")
    if unknown:
        raise UIEvidenceError(f"material browser packet has unsupported fields: {sorted(unknown)}")

    version = packet["schema_version"]
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != MATERIAL_PACKET_SCHEMA_VERSION
    ):
        raise UIEvidenceError(
            f"schema_version must be {MATERIAL_PACKET_SCHEMA_VERSION}"
        )

    checkpoint_token = _non_empty_string(packet["checkpoint_token"], "checkpoint_token")
    scope = normalize_scope(packet["checkpoint_scope"] if isinstance(packet["checkpoint_scope"], list) else [])
    fingerprint = _sha256(packet["accepted_source_fingerprint"], "accepted_source_fingerprint")
    browser_executor = _non_empty_string(packet["browser_executor"], "browser_executor")
    if browser_executor != "coordinator/main":
        raise UIEvidenceError("browser_executor must be coordinator/main")

    selector = _non_empty_string(packet["selector"], "selector")
    family = _non_empty_string(packet["browser_family"], "browser_family")
    automatic_fallback = packet["automatic_fallback"]
    if not isinstance(automatic_fallback, bool) or automatic_fallback:
        raise UIEvidenceError("automatic_fallback must be false")
    if selector not in {"iab", "chrome", "edge"}:
        raise UIEvidenceError("selector must be iab, chrome, or edge")
    if selector == "iab":
        if family != "iab":
            raise UIEvidenceError("iab selector requires browser_family iab")
        if keys & EXCEPTION_PACKET_FIELDS:
            raise UIEvidenceError("IAB packet cannot include browser-exception fields")
    else:
        if family != selector or not EXCEPTION_PACKET_FIELDS <= keys:
            raise UIEvidenceError(
                "Chrome/Edge packets require matching family, reason, approval, and matching_family"
            )
        for field in EXCEPTION_PACKET_FIELDS:
            _non_empty_string(packet[field], field)
        if packet["matching_family"] != selector:
            raise UIEvidenceError("matching_family must match selector")

    checked_url = _non_empty_string(packet["checked_url"], "checked_url")
    parsed_url = urlparse(checked_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise UIEvidenceError("checked_url must be an absolute http(s) URL")
    primary_flow_view = _non_empty_string(packet["primary_flow_view"], "primary_flow_view")

    normalized: dict[str, object] = {
        "accepted_source_fingerprint": fingerprint,
        "automatic_fallback": False,
        "browser_executor": browser_executor,
        "browser_family": family,
        "checked_url": checked_url,
        "checkpoint_scope": scope,
        "checkpoint_token": checkpoint_token,
        "evidence_artifacts": _artifacts(packet["evidence_artifacts"]),
        "primary_flow_view": primary_flow_view,
        "result": _non_empty_string(packet["result"], "result"),
        "schema_version": MATERIAL_PACKET_SCHEMA_VERSION,
        "selector": selector,
        "viewport": _viewport(packet["viewport"]),
    }
    if selector != "iab":
        for field in EXCEPTION_PACKET_FIELDS:
            normalized[field] = _non_empty_string(packet[field], field)

    if repo is not None:
        expected_fingerprint = source_fingerprint(repo, scope)
        if expected_fingerprint != fingerprint:
            raise UIEvidenceError(
                "accepted_source_fingerprint does not match the scoped working tree"
            )
    return normalized


def validate_metadata(metadata: Mapping[str, object] | None) -> dict[str, str]:
    """Validate the separate non-material metadata sidecar."""

    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise UIEvidenceError("metadata sidecar must be an object")
    unknown = set(metadata) - METADATA_FIELDS
    if unknown or set(metadata) & MATERIAL_PACKET_FIELDS:
        raise UIEvidenceError(
            "metadata sidecar may contain only generated_at and generator_version"
        )
    normalized: dict[str, str] = {}
    for field in sorted(metadata):
        normalized[field] = _non_empty_string(metadata[field], field)
    return normalized


def material_packet_bytes(
    packet: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
    *,
    repo: os.PathLike[str] | str | None = None,
) -> bytes:
    """Return canonical bytes for material packet fields only."""

    validate_metadata(metadata)
    return canonical_json_bytes(validate_material_packet(packet, repo=repo))


def material_packet_hash(
    packet: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
    *,
    repo: os.PathLike[str] | str | None = None,
) -> str:
    """Hash material packet bytes; a valid metadata sidecar never affects this hash."""

    return hashlib.sha256(material_packet_bytes(packet, metadata, repo=repo)).hexdigest()


browser_evidence_hash = material_packet_hash
packet_hash = material_packet_hash


def _read_json(path: str) -> object:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise UIEvidenceError(f"cannot read JSON file {path}: {error}") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser(
        "source-fingerprint", help="hash scoped working-tree source content"
    )
    source_parser.add_argument("--repo", default=".")
    source_parser.add_argument("--scope", nargs="+", required=True)

    packet_parser = subparsers.add_parser(
        "packet-hash", help="validate and hash a material browser packet"
    )
    packet_parser.add_argument("--packet", required=True)
    packet_parser.add_argument("--metadata")
    packet_parser.add_argument("--repo")

    args = parser.parse_args(argv)
    try:
        if args.command == "source-fingerprint":
            print(source_fingerprint(args.repo, args.scope))
        else:
            packet = _read_json(args.packet)
            if not isinstance(packet, Mapping):
                raise UIEvidenceError("material browser packet JSON must be an object")
            metadata = _read_json(args.metadata) if args.metadata else None
            if metadata is not None and not isinstance(metadata, Mapping):
                raise UIEvidenceError("metadata sidecar JSON must be an object")
            print(material_packet_hash(packet, metadata, repo=args.repo))
    except UIEvidenceError as error:
        print(f"ui_evidence: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
