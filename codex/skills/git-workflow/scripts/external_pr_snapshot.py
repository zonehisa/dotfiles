#!/usr/bin/env python3
"""Build a read-only, Git-object snapshot identity for an external PR review.

This helper deliberately operates on two existing commit objects.  It only reads
Git objects and does not modify repository state or invoke the local completion-review
fingerprint helper.  The resulting identity is suitable for binding a remote PR review
to one exact repository/PR/base/head/diff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
SHA_RE = re.compile(r"\A[0-9a-fA-F]{40}\Z")
PR_NUMBER_RE = re.compile(r"\A[1-9][0-9]*\Z")

# Keep every diff-affecting choice explicit.  Raw object records keep the
# representation independent of worktree attributes; disabling rename
# detection makes changed_paths an unambiguous sorted set of old/new paths.
DIFF_OPTIONS = (
    "--raw",
    "-z",
    "--full-index",
    "--abbrev=40",
    "--no-ext-diff",
    "--no-textconv",
    "--no-renames",
    "--no-color",
    "--no-indent-heuristic",
    "--ignore-submodules=none",
    "--submodule=short",
    "--diff-algorithm=myers",
    "-O/dev/null",
    "-r",
)

IDENTITY_KEYS = (
    "schema_version",
    "snapshot_type",
    "repository",
    "pr_number",
    "base_sha",
    "head_sha",
    "merge_base",
    "changed_paths",
    "patch_hash",
    "diff_sha256",
    "base_tree",
    "merge_base_tree",
    "head_tree",
)


class SnapshotError(ValueError):
    """Raised when an external PR snapshot cannot be proven unambiguous."""


def _run_git(repo: Path, args: Sequence[str]) -> bytes:
    """Run a read-only Git command with optional lock acquisition disabled."""

    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_DIFF_OPTS"] = ""
    environment["GIT_PAGER"] = "cat"
    environment["PAGER"] = "cat"
    environment["LC_ALL"] = "C"
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        command = "git " + " ".join(args)
        raise SnapshotError(detail or f"{command} failed")
    return result.stdout


def _resolve_repository(repo_argument: str | os.PathLike[str]) -> Path:
    try:
        candidate = Path(repo_argument)
        if not candidate.exists() or not candidate.is_dir():
            raise SnapshotError("repository must be an existing directory")
        top_level_raw = _run_git(candidate, ("rev-parse", "--show-toplevel")).strip()
    except OSError as error:
        raise SnapshotError(f"cannot access repository: {error}") from error

    if not top_level_raw:
        raise SnapshotError("cannot resolve repository root")
    try:
        top_level = Path(os.fsdecode(top_level_raw)).resolve(strict=True)
    except OSError as error:
        raise SnapshotError(f"repository root is unsafe or unavailable: {error}") from error
    if not top_level.is_dir():
        raise SnapshotError("repository root must be a directory")
    return top_level


def _commit_sha(repo: Path, value: str, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise SnapshotError(f"{label} must be an exact 40-character hexadecimal commit SHA")

    try:
        resolved_raw = _run_git(
            repo,
            ("rev-parse", "--verify", "--end-of-options", f"{value}^{{commit}}"),
        ).strip()
    except SnapshotError as error:
        raise SnapshotError(f"{label} does not resolve to a commit: {error}") from error
    resolved = resolved_raw.decode(errors="replace")
    if not SHA_RE.fullmatch(resolved) or resolved.lower() != value.lower():
        raise SnapshotError(f"{label} is ambiguous or does not identify the supplied commit")

    object_type = _run_git(repo, ("cat-file", "-t", resolved)).strip()
    if object_type != b"commit":
        raise SnapshotError(f"{label} must identify a commit object")
    return resolved.lower()


def _tree_sha(repo: Path, commit: str, label: str) -> str:
    tree_raw = _run_git(repo, ("rev-parse", "--verify", f"{commit}^{{tree}}")).strip()
    tree = tree_raw.decode(errors="replace")
    if not SHA_RE.fullmatch(tree):
        raise SnapshotError(f"cannot resolve {label} tree")
    return tree.lower()


def _merge_base(repo: Path, base_sha: str, head_sha: str) -> str:
    try:
        raw_bases = _run_git(repo, ("merge-base", "--all", base_sha, head_sha))
    except SnapshotError as error:
        raise SnapshotError(f"cannot determine merge base: {error}") from error
    bases = sorted(
        {
            line.strip().decode(errors="replace").lower()
            for line in raw_bases.splitlines()
            if line.strip()
        }
    )
    if not bases:
        raise SnapshotError("base and head have no common merge base")
    if len(bases) != 1:
        raise SnapshotError("base and head have an ambiguous merge base")
    if not SHA_RE.fullmatch(bases[0]):
        raise SnapshotError("merge base is not a valid commit SHA")
    return _commit_sha(repo, bases[0], "merge base")


def _diff_args(kind: str, merge_base_tree: str, head_tree: str) -> tuple[str, ...]:
    common = (
        "-c",
        "core.quotePath=true",
        "-c",
        "diff.algorithm=myers",
        "diff-tree",
        *DIFF_OPTIONS,
        merge_base_tree,
        head_tree,
        "--",
    )
    if kind in {"names", "patch"}:
        return common
    raise SnapshotError(f"unsupported diff kind: {kind}")


def _validate_git_path(raw_path: bytes) -> str:
    if not raw_path or b"\0" in raw_path:
        raise SnapshotError("Git diff contains an unsafe path")
    path = os.fsdecode(raw_path)
    posix_path = PurePosixPath(path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise SnapshotError(f"Git diff contains an unsafe path: {path!r}")
    if path in {"", "."}:
        raise SnapshotError("Git diff contains an empty path")
    return path


def _raw_diff_records(raw_diff: bytes) -> list[tuple[bytes, ...]]:
    """Parse NUL-delimited raw records without consulting the worktree."""

    tokens = raw_diff.split(b"\0")
    records: list[tuple[bytes, ...]] = []
    cursor = 0
    while cursor < len(tokens):
        header = tokens[cursor]
        cursor += 1
        if not header:
            continue
        fields = header.split()
        if not header.startswith(b":") or len(fields) != 5:
            raise SnapshotError("Git diff contains an invalid raw object record")
        status = fields[4]
        path_count = 2 if status[:1] in {b"R", b"C"} else 1
        if cursor + path_count > len(tokens):
            raise SnapshotError("Git diff contains an incomplete raw object record")
        paths = tuple(tokens[cursor : cursor + path_count])
        cursor += path_count
        if any(not path for path in paths):
            raise SnapshotError("Git diff contains an empty path")
        records.append((*fields, *paths))
    return records


def _validate_raw_objects(repo: Path, records: list[tuple[bytes, ...]]) -> None:
    """Require changed blob objects to be locally available without lazy fetch."""

    null_object = b"0" * 40
    for record in records:
        old_mode, new_mode, old_object, new_object = record[:4]
        for mode, object_id in ((old_mode, old_object), (new_mode, new_object)):
            if object_id == null_object or mode.lstrip(b":") == b"160000":
                # A gitlink points at an object in the submodule repository, not
                # the parent repository.  Its OID remains bound in the raw record.
                continue
            if not re.fullmatch(rb"[0-9a-f]{40}", object_id):
                raise SnapshotError("Git diff contains an invalid object ID")
            object_type = _run_git(repo, ("cat-file", "-t", object_id)).strip()
            if object_type != b"blob":
                raise SnapshotError(f"Git diff object {object_id.decode()} is not a blob")


def _changed_paths(repo: Path, merge_base_tree: str, head_tree: str) -> list[str]:
    records = _raw_diff_records(_run_git(repo, _diff_args("names", merge_base_tree, head_tree)))
    _validate_raw_objects(repo, records)
    raw_paths = [path for record in records for path in record[5:]]
    if len(raw_paths) != len(set(raw_paths)):
        raise SnapshotError("Git diff contains duplicate changed paths")
    # Sort by the Git path bytes, then expose the deterministic filesystem-safe
    # representation.  This avoids locale-dependent path ordering.
    return [_validate_git_path(raw) for raw in sorted(raw_paths)]


def _canonical_patch_hash(
    *,
    base_sha: str,
    head_sha: str,
    merge_base: str,
    base_tree: str,
    merge_base_tree: str,
    head_tree: str,
    changed_paths: list[str],
    diff_sha256: str,
    diff_length: int,
) -> str:
    material = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": "git-object-diff-v1-raw-full-index-no-renames",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base": merge_base,
        "base_tree": base_tree,
        "merge_base_tree": merge_base_tree,
        "head_tree": head_tree,
        "changed_paths": changed_paths,
        "diff_sha256": diff_sha256,
        "diff_length": diff_length,
    }
    canonical = json.dumps(
        material,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _pr_number(value: int | str) -> int:
    text = str(value)
    if not PR_NUMBER_RE.fullmatch(text):
        raise SnapshotError("pr number must be a positive decimal integer")
    return int(text)


def compute_snapshot(
    repo: str | os.PathLike[str],
    pr_number: int | str,
    base_sha: str,
    head_sha: str,
) -> dict[str, Any]:
    """Compute a deterministic external-PR snapshot from existing Git objects."""

    repository = _resolve_repository(repo)
    number = _pr_number(pr_number)
    base = _commit_sha(repository, base_sha, "base SHA")
    head = _commit_sha(repository, head_sha, "head SHA")
    merge_base = _merge_base(repository, base, head)
    base_tree = _tree_sha(repository, base, "base")
    merge_base_tree = _tree_sha(repository, merge_base, "merge base")
    head_tree = _tree_sha(repository, head, "head")
    changed_paths = _changed_paths(repository, merge_base_tree, head_tree)
    patch = _run_git(repository, _diff_args("patch", merge_base_tree, head_tree))
    _validate_raw_objects(repository, _raw_diff_records(patch))
    diff_sha256 = hashlib.sha256(patch).hexdigest()
    patch_hash = _canonical_patch_hash(
        base_sha=base,
        head_sha=head,
        merge_base=merge_base,
        base_tree=base_tree,
        merge_base_tree=merge_base_tree,
        head_tree=head_tree,
        changed_paths=changed_paths,
        diff_sha256=diff_sha256,
        diff_length=len(patch),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_type": "external_pr",
        "repository": str(repository),
        "pr_number": number,
        "base_sha": base,
        "head_sha": head,
        "merge_base": merge_base,
        "changed_paths": changed_paths,
        "patch_hash": patch_hash,
        "diff_sha256": diff_sha256,
        "base_tree": base_tree,
        "merge_base_tree": merge_base_tree,
        "head_tree": head_tree,
    }


def validate_snapshot(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    """Require every material identity field in *expected* to match *actual*."""

    if not isinstance(expected, Mapping):
        raise SnapshotError("expected snapshot must be a JSON object")
    for key in IDENTITY_KEYS:
        if key not in expected:
            raise SnapshotError(f"expected snapshot is missing {key}")
        if key in {"schema_version", "pr_number"} and type(expected[key]) is not int:
            raise SnapshotError(f"expected snapshot {key} must be an integer")
        if expected[key] != actual.get(key):
            raise SnapshotError(f"expected snapshot {key} does not match current Git objects")


def _load_expected(path_value: str) -> Mapping[str, Any]:
    try:
        with Path(path_value).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotError(f"cannot read expected snapshot: {error}") from error
    if not isinstance(value, Mapping):
        raise SnapshotError("expected snapshot must be a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute a read-only external PR snapshot identity from local Git objects."
    )
    parser.add_argument("--repo", default=".", help="Git repository path (defaults to current directory)")
    parser.add_argument("--pr-number", "--pr", dest="pr_number", required=True, help="Positive PR number")
    parser.add_argument(
        "--base-sha",
        "--base",
        dest="base_sha",
        required=True,
        help="Exact 40-character PR base commit SHA",
    )
    parser.add_argument(
        "--head-sha",
        "--head",
        dest="head_sha",
        required=True,
        help="Exact 40-character PR head commit SHA",
    )
    parser.add_argument(
        "--expected",
        "--expected-json",
        dest="expected",
        help="Optional JSON snapshot file to validate against the current Git objects",
    )
    args = parser.parse_args(argv)

    try:
        snapshot = compute_snapshot(args.repo, args.pr_number, args.base_sha, args.head_sha)
        if args.expected:
            validate_snapshot(_load_expected(args.expected), snapshot)
    except SnapshotError as error:
        print(f"external PR snapshot rejected: {error}", file=sys.stderr)
        return 2

    print(json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
