#!/usr/bin/env python3
"""Collect and validate deterministic evidence before starting Issue work.

The helper deliberately treats an Issue, a PR list, and source text as data.  A
natural-language Issue never proves that work is missing or complete.  A
caller supplies machine-checkable criteria (paths and literal/regular-expression
searches); this module records the exact target commit, Git blobs, API snapshots,
and the resulting ``satisfied``/``needs_work``/``unknown`` status.

The module is also imported by ``parallel-worktree/scripts/pw-helper``.  Keep
the public functions small and side-effect explicit so active lifecycle Git
mutations can use the same evidence gate as the standalone CLI.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
EVIDENCE_KIND = "git-workflow-issue-preflight"
DECISIONS = {"satisfied", "needs_work", "unknown"}
STATUSES = {"satisfied", "missing", "unknown"}
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_REF_RE = re.compile(r"^(?:refs/)?(?:heads|remotes|tags)/[A-Za-z0-9._/@-]+$")
ISSUE_REF_RE = re.compile(r"(?<![A-Za-z0-9_/#])#([1-9][0-9]*)(?![A-Za-z0-9_])")
PR_URL_RE = re.compile(r"/pull/([1-9][0-9]*)(?:[/?#]|$)")
FULL_PR_REF_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)(?![A-Za-z0-9_])")
DIAGNOSTIC_TOKEN_RE = re.compile(r"(?i)(token|password|passwd|secret|credential)=([^\s&]+)")
DIAGNOSTIC_URL_CREDENTIAL_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^/\s@]+)@")
DIAGNOSTIC_URL_USERINFO_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^/\s@]+)@")


class PreflightError(RuntimeError):
    """A deterministic preflight input or verification failure."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PreflightError(f"value is not canonical JSON: {exc}") from exc


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def redact_diagnostic(value: str) -> str:
    """Remove credentials before a subprocess diagnostic enters evidence."""

    value = DIAGNOSTIC_TOKEN_RE.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    value = DIAGNOSTIC_URL_CREDENTIAL_RE.sub(r"\1<redacted>@", value)
    return DIAGNOSTIC_URL_USERINFO_RE.sub(r"\1<redacted>@", value)


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightError(f"command failed to start: {' '.join(command[:2])}: {exc}") from exc


def run_git(repo: Path, *args: str, check: bool = True, timeout: int = 60) -> bytes:
    result = _run(("git", "-C", str(repo), *args), timeout=timeout)
    if check and result.returncode:
        message = redact_diagnostic(result.stderr.decode("utf-8", "replace").strip())
        raise PreflightError(message or f"git {' '.join(args)} failed")
    return result.stdout


def run_gh(repo: Path, *args: str, check: bool = True, timeout: int = 60) -> Any:
    result = _run(("gh", *args), cwd=repo, timeout=timeout)
    if check and result.returncode:
        message = redact_diagnostic(result.stderr.decode("utf-8", "replace").strip())
        raise PreflightError(message or f"gh {' '.join(args)} failed")
    if result.returncode:
        return None
    raw = result.stdout.decode("utf-8", "replace").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"gh returned invalid JSON for {' '.join(args)}") from exc


def repo_root(repo: str | os.PathLike[str]) -> Path:
    path = Path(repo).expanduser().resolve()
    if not path.is_dir():
        raise PreflightError(f"repository is not a directory: {path}")
    root = run_git(path, "rev-parse", "--show-toplevel").decode().strip()
    return Path(root).resolve()


def _remote_slug_from_url(raw: str) -> str | None:
    value = raw.strip()
    value = re.sub(r"\.git$", "", value)
    if "://" in value:
        value = value.split("://", 1)[1]
        value = value.split("/", 1)[1] if "/" in value else ""
    elif ":" in value and "@" in value:
        value = value.split(":", 1)[1]
    value = value.strip("/")
    pieces = value.split("/")
    if len(pieces) >= 2 and all(pieces[-2:]):
        return "/".join(pieces[-2:])
    return None


def _remote_host(raw: str) -> str | None:
    value = raw.strip()
    if "://" not in value:
        if ":" in value and "@" in value:
            value = "ssh://" + value.replace(":", "/", 1)
        else:
            return None
    parsed = urllib.parse.urlsplit(value)
    return parsed.hostname.lower() if parsed.hostname else None


def _safe_remote(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if "://" not in value and ":" in value and "@" in value:
        host, path = value.split(":", 1)
        value = f"ssh://{host}/{path}"
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname.lower()
        if parsed.port:
            host = f"{host}:{parsed.port}"
        path = re.sub(r"(?:\.git)?/$", "", parsed.path)
        path = re.sub(r"\.git$", "", path)
        return urllib.parse.urlunsplit((parsed.scheme.lower(), host, path, "", ""))
    return value


def repository_identity(repo: Path) -> dict[str, str | None]:
    # ``remote get-url`` applies url.*.insteadOf rewrites.  Evidence must bind
    # to the configured origin identity, so read the stored remote first and
    # only fall back to the resolved URL when older Git lacks the key.
    remote = run_git(repo, "config", "--get", "remote.origin.url", check=False).decode("utf-8", "replace").strip()
    if not remote:
        remote = run_git(repo, "remote", "get-url", "origin", check=False).decode("utf-8", "replace").strip()
    branch = run_git(repo, "branch", "--show-current", check=False).decode().strip()
    head = run_git(repo, "rev-parse", "HEAD", check=False).decode().strip()
    return {
        "path": str(repo),
        "remote": _safe_remote(remote),
        "remote_host": _remote_host(remote),
        "slug": _remote_slug_from_url(remote),
        "current_branch": branch or None,
        "current_sha": head if SHA_RE.fullmatch(head) else None,
    }


def normalize_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise PreflightError("criteria path must be a non-empty string")
    path = raw.replace("\\", "/")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or path.startswith("//"):
        raise PreflightError(f"unsafe criteria path: {raw!r}")
    if any(part in {"", "."} for part in pure.parts) or ".git" in pure.parts:
        raise PreflightError(f"criteria path is not normalized: {raw!r}")
    return "/".join(pure.parts)


def normalize_ref(raw: str) -> str:
    if not isinstance(raw, str) or not raw or raw.startswith("-"):
        raise PreflightError("ref must be a non-empty value")
    if SHA_RE.fullmatch(raw):
        return raw.lower()
    if raw.startswith("refs/remotes/") or raw.startswith("refs/heads/") or raw.startswith("refs/tags/"):
        return raw
    if raw.startswith("origin/"):
        return f"refs/remotes/{raw}"
    if raw.startswith("refs/"):
        return raw
    return f"refs/heads/{raw}"


def normalize_target_ref(raw: str) -> str:
    """Return the live ``origin`` branch used for current-target evidence."""

    if not isinstance(raw, str) or not raw or raw.startswith("-"):
        raise PreflightError("current target must be an origin branch")
    if SHA_RE.fullmatch(raw):
        raise PreflightError("current target must be a live origin branch, not a commit SHA")
    value = raw
    if value == "refs/remotes/origin/HEAD":
        return value
    if value.startswith("refs/remotes/origin/"):
        branch = value.removeprefix("refs/remotes/origin/")
    elif value.startswith("origin/"):
        branch = value.removeprefix("origin/")
    elif value.startswith("refs/heads/"):
        branch = value.removeprefix("refs/heads/")
    elif value.startswith("refs/"):
        raise PreflightError("current target must be a live origin branch")
    else:
        branch = value
    if not branch or any(part in {"", ".", ".."} for part in branch.split("/")) or "\\" in branch:
        raise PreflightError("current target branch is invalid")
    return f"refs/remotes/origin/{branch}"


def resolve_commit(repo: Path, ref: str, *, check: bool = True) -> str | None:
    raw = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False).decode().strip()
    if not SHA_RE.fullmatch(raw):
        if check:
            raise PreflightError(f"ref does not resolve to a commit: {ref}")
        return None
    return raw.lower()


def default_target_ref(repo: Path) -> str:
    symbolic = run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", check=False).decode().strip()
    if symbolic:
        return symbolic
    branches = [
        line.strip()
        for line in run_git(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/origin", check=False).decode().splitlines()
        if line.strip() and line.strip() != "refs/remotes/origin/HEAD"
    ]
    if len(branches) == 1:
        # A single remote branch is an unambiguous target even when a bare
        # fixture did not advertise origin/HEAD locally.
        return branches[0]
    # A repository without origin/HEAD is an explicit discovery failure.  Do not
    # silently guess ``main`` or ``master``.
    raise PreflightError("origin/HEAD is unavailable; pass --target explicitly")


def fetch_origin(repo: Path) -> tuple[bool, str | None]:
    result = _run(("git", "-C", str(repo), "fetch", "origin"), timeout=120)
    if result.returncode:
        message = redact_diagnostic(result.stderr.decode("utf-8", "replace").strip())
        return False, message or "git fetch origin failed"
    return True, None


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"cannot read JSON file: {path}") from exc


def load_criteria(path: str | os.PathLike[str] | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    value = _read_json_file(Path(path).expanduser().resolve())
    if isinstance(value, dict):
        value = value.get("criteria")
    if not isinstance(value, list):
        raise PreflightError("criteria file must contain a JSON array or {criteria: []}")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise PreflightError(f"criterion {index} must be an object")
        criterion = json.loads(json.dumps(item))
        criterion.setdefault("id", f"criterion-{index + 1}")
        if not isinstance(criterion["id"], str) or not criterion["id"]:
            raise PreflightError(f"criterion {index} has an invalid id")
        criterion.setdefault("requirement", criterion["id"])
        if not isinstance(criterion["requirement"], str) or not criterion["requirement"].strip():
            raise PreflightError(f"criterion {criterion['id']} has an empty requirement")
        result.append(criterion)
    ids = [item["id"] for item in result]
    if len(ids) != len(set(ids)):
        raise PreflightError("criterion ids must be unique")
    return result


def _tree_entries(repo: Path, commit: str) -> dict[str, dict[str, str]]:
    raw = run_git(repo, "ls-tree", "-r", "-l", "-z", commit)
    entries: dict[str, dict[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_raw = record.split(b"\t", 1)
            mode, kind, blob, size = metadata.decode("ascii").split(" ", 3)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PreflightError("target tree contains an invalid ls-tree record") from exc
        path = normalize_path(path_raw.decode("utf-8", "surrogateescape"))
        entries[path] = {"mode": mode, "type": kind, "blob": blob, "size": size}
    return entries


def _blob_bytes(repo: Path, commit: str, path: str) -> bytes:
    # ``--`` cannot be used with git show's tree:path syntax; path was already
    # normalized and cannot escape the target tree.
    return run_git(repo, "show", f"{commit}:{path}")


def _source_record(target_sha: str, path: str, entry: Mapping[str, str] | None, *, status: str, expected: Any = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": path,
        "target_sha": target_sha,
        "status": status,
        "expected": expected,
    }
    if entry:
        record.update({"blob": entry["blob"], "mode": entry["mode"], "type": entry["type"], "size": int(entry["size"])})
    return record


def _as_specs(value: Any, aliases: Sequence[str] = ()) -> list[Any]:
    values: list[Any] = []
    if value is not None:
        values.extend(value if isinstance(value, list) else [value])
    return values


def _criterion_specs(criterion: Mapping[str, Any], key: str, aliases: Sequence[str] = ()) -> list[Any]:
    value = criterion.get(key)
    if value is None:
        for alias in aliases:
            if alias in criterion:
                value = criterion[alias]
                break
    return _as_specs(value)


def _search_bytes(content: bytes, spec: Mapping[str, Any]) -> tuple[int, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8", "replace")
    if "literal" in spec:
        needle = spec.get("literal")
        if not isinstance(needle, str) or not needle:
            raise PreflightError("search literal must be a non-empty string")
        return text.count(needle), f"literal:{needle}"
    pattern = spec.get("regex")
    if not isinstance(pattern, str) or not pattern:
        raise PreflightError("search requires a non-empty literal or regex")
    try:
        return len(re.findall(pattern, text, flags=re.MULTILINE)), f"regex:{pattern}"
    except re.error as exc:
        raise PreflightError(f"invalid deterministic search regex: {pattern}") from exc


def _evaluate_search(
    repo: Path,
    target_sha: str,
    entries: Mapping[str, Mapping[str, str]],
    spec: Any,
    *,
    evidence_kind: str,
) -> dict[str, Any]:
    if isinstance(spec, str):
        spec = {"path": spec, "literal": ""}
    if not isinstance(spec, Mapping):
        return {"status": "unknown", "kind": evidence_kind, "rationale": "search specification is not an object"}
    raw_path = spec.get("path")
    try:
        path = normalize_path(raw_path)
    except PreflightError as exc:
        return {"status": "unknown", "kind": evidence_kind, "rationale": str(exc)}
    entry = entries.get(path)
    if not entry or entry.get("type") != "blob":
        return {
            "status": "missing",
            "kind": evidence_kind,
            **_source_record(target_sha, path, entry, status="missing", expected=spec),
            "matches": 0,
        }
    try:
        count, expression = _search_bytes(_blob_bytes(repo, target_sha, path), spec)
    except PreflightError as exc:
        return {"status": "unknown", "kind": evidence_kind, "path": path, "rationale": str(exc)}
    present = bool(spec.get("present", True))
    minimum = int(spec.get("min_count", 1 if present else 0))
    maximum = spec.get("max_count")
    if not isinstance(minimum, int) or minimum < 0:
        return {"status": "unknown", "kind": evidence_kind, "path": path, "rationale": "min_count must be a non-negative integer"}
    if maximum is not None and (not isinstance(maximum, int) or maximum < 0):
        return {"status": "unknown", "kind": evidence_kind, "path": path, "rationale": "max_count must be a non-negative integer"}
    matches = (count >= minimum and (maximum is None or count <= maximum)) if present else count == 0
    return {
        "status": "satisfied" if matches else "missing",
        "kind": evidence_kind,
        **_source_record(target_sha, path, entry, status="satisfied" if matches else "missing", expected=spec),
        "matches": count,
        "expression": expression,
    }


def _evaluate_path(
    target_sha: str,
    entries: Mapping[str, Mapping[str, str]],
    spec: Any,
    *,
    evidence_kind: str,
) -> dict[str, Any]:
    if isinstance(spec, str):
        spec = {"path": spec}
    if not isinstance(spec, Mapping):
        return {"status": "unknown", "kind": evidence_kind, "rationale": "path specification is not an object"}
    try:
        path = normalize_path(spec.get("path"))
    except PreflightError as exc:
        return {"status": "unknown", "kind": evidence_kind, "rationale": str(exc)}
    entry = entries.get(path)
    expected_exists = bool(spec.get("exists", True))
    exists = entry is not None
    status = "satisfied" if exists == expected_exists else "missing"
    if status == "satisfied" and spec.get("blob") and spec.get("blob") != entry.get("blob"):
        status = "missing"
    result: dict[str, Any] = {
        "kind": evidence_kind,
        **_source_record(target_sha, path, entry, status=status, expected=spec),
        "exists": exists,
    }
    if status == "satisfied" and entry and spec.get("mode") and spec.get("mode") != entry.get("mode"):
        result["status"] = "missing"
        result["rationale"] = "Git mode does not match the criterion"
    if status == "satisfied" and entry and spec.get("type") and spec.get("type") != entry.get("type"):
        result["status"] = "missing"
        result["rationale"] = "Git object type does not match the criterion"
    return result


def evaluate_criteria(
    repo: Path,
    target_sha: str,
    criteria: Sequence[Mapping[str, Any]],
    *,
    issue_relevant_sha256: str | None = None,
) -> list[dict[str, Any]]:
    entries = _tree_entries(repo, target_sha)
    results: list[dict[str, Any]] = []
    for index, criterion in enumerate(criteria):
        criterion_id = str(criterion.get("id", f"criterion-{index + 1}"))
        requirement = str(criterion.get("requirement", criterion_id))
        evidence: list[dict[str, Any]] = []
        assessment = criterion.get("assessment") if isinstance(criterion.get("assessment"), Mapping) else None
        if assessment is None:
            results.append({
                "id": criterion_id,
                "requirement": requirement,
                "status": "unknown",
                "rationale": "an explicit requirement assessment bound to the inspected target and Issue is required",
                "residual_scope": requirement,
                "evidence": [],
            })
            continue
        assessed_status = assessment.get("status")
        assessed_rationale = assessment.get("rationale")
        assessed_residual = assessment.get("residual_scope")
        if assessed_status not in STATUSES or not isinstance(assessed_rationale, str) or not assessed_rationale.strip() or not isinstance(assessed_residual, str) or not assessed_residual.strip():
            results.append({
                "id": criterion_id,
                "requirement": requirement,
                "status": "unknown",
                "rationale": "assessment status, rationale, and residual_scope must be non-empty and deterministic",
                "residual_scope": requirement,
                "evidence": [],
            })
            continue
        if assessment.get("assessed_target_sha") != target_sha or assessment.get("assessed_issue_relevant_sha256") != issue_relevant_sha256:
            results.append({
                "id": criterion_id,
                "requirement": requirement,
                "status": "unknown",
                "rationale": "assessment is bound to a different target commit or Issue content hash",
                "residual_scope": assessed_residual,
                "evidence": [],
                "assessment": dict(assessment),
            })
            continue
        source_specs = _criterion_specs(criterion, "source", ("source_paths", "paths"))
        search_specs = _criterion_specs(criterion, "search", ("searches",))
        test_specs = _criterion_specs(criterion, "tests", ("test", "test_paths"))
        for item in assessment.get("evidence", []) if isinstance(assessment.get("evidence"), list) else []:
            if not isinstance(item, Mapping):
                continue
            if item.get("kind") == "source":
                source_specs.append(item)
            elif item.get("kind") == "search":
                search_specs.append(item)
            elif item.get("kind") == "test":
                test_specs.append(item)
        if not source_specs and not search_specs and not test_specs:
            results.append({
                "id": criterion_id,
                "requirement": requirement,
                "status": "unknown",
                "rationale": assessed_rationale,
                "residual_scope": assessed_residual,
                "evidence": [],
                "assessment": dict(assessment),
            })
            continue
        for spec in source_specs:
            evidence.append(_evaluate_path(target_sha, entries, spec, evidence_kind="source"))
        for spec in search_specs:
            evidence.append(_evaluate_search(repo, target_sha, entries, spec, evidence_kind="search"))
        for spec in test_specs:
            # Test evidence is source-backed by design.  A criteria file cannot
            # smuggle an arbitrary shell command into the collector.  Callers
            # may provide an explicit ``argv`` only as a declaration; it is
            # recorded as unknown and is never executed here.
            if isinstance(spec, Mapping) and ("command" in spec or "argv" in spec):
                evidence.append({"status": "unknown", "kind": "test", "rationale": "test commands are not executed from evidence"})
            elif isinstance(spec, str) or (isinstance(spec, Mapping) and not ("literal" in spec or "regex" in spec)):
                evidence.append(_evaluate_path(target_sha, entries, spec, evidence_kind="test"))
            else:
                evidence.append(_evaluate_search(repo, target_sha, entries, spec, evidence_kind="test"))
        statuses = [item.get("status") for item in evidence]
        if "unknown" in statuses:
            status = "unknown"
            rationale = "a cited source/search/test fact could not be verified for the bound assessment"
            residual = assessed_residual
        elif assessed_status == "satisfied" and "missing" in statuses:
            status = "unknown"
            rationale = "the explicit satisfied assessment is contradicted by a current source/search/test fact"
            residual = assessed_residual
        else:
            # Facts corroborate or invalidate an explicit assessment; they do
            # not infer product semantics from a matching keyword or file.
            status = assessed_status
            rationale = assessed_rationale
            residual = assessed_residual
        results.append({
            "id": criterion_id,
            "requirement": requirement,
            "status": status,
            "rationale": rationale,
            "residual_scope": residual or requirement,
            "evidence": evidence,
            "assessment": dict(assessment),
        })
    return results


def _issue_relevant(issue: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("number", "title", "body", "state", "url", "updatedAt", "closedAt", "labels")
    value = {key: issue.get(key) for key in fields if key in issue}
    return {"fields": value, "sha256": sha256(canonical_json(value))}


def _parse_issue_refs(value: Any, issue_number: int, slug: str | None = None) -> list[int]:
    text = value if isinstance(value, str) else ""
    numbers = {int(match.group(1)) for match in ISSUE_REF_RE.finditer(text)}
    numbers.update(int(match.group(1)) for match in PR_URL_RE.finditer(text))
    if slug:
        for match in FULL_PR_REF_RE.finditer(text):
            if match.group(1).lower() == slug.lower():
                numbers.add(int(match.group(2)))
    numbers.discard(issue_number)
    return sorted(numbers)


def _parse_linked_pr_refs(value: Any, issue_number: int, slug: str | None = None) -> list[int]:
    """Parse only PR-shaped references from free-form Issue text.

    A bare ``#42`` can be another Issue (for example ``Depends on #42``).
    Accept the explicit ``Related to``/``PR`` relation and same-repository PR
    URLs; typed timeline cross-references are handled separately.
    """

    text = value if isinstance(value, str) else ""
    numbers: set[int] = set()
    if slug:
        repo_path = re.escape(slug.strip("/"))
        url_pattern = re.compile(rf"(?i)(?:https?://[^\s/]+/)?{repo_path}/pull/([1-9][0-9]*)")
        numbers.update(int(match.group(1)) for match in url_pattern.finditer(text))
        for match in FULL_PR_REF_RE.finditer(text):
            if match.group(1).lower() == slug.lower():
                numbers.add(int(match.group(2)))
    related = re.compile(r"(?i)\b(?:related\s+to|pr)\s+#([1-9][0-9]*)\b")
    numbers.update(int(match.group(1)) for match in related.finditer(text))
    numbers.discard(issue_number)
    return sorted(numbers)


def _walk_references(value: Any, issue_number: int, slug: str | None = None) -> list[int]:
    found: set[int] = set()
    if isinstance(value, str):
        found.update(_parse_issue_refs(value, issue_number, slug))
    elif isinstance(value, Mapping):
        for item in value.values():
            found.update(_walk_references(item, issue_number, slug))
    elif isinstance(value, list):
        for item in value:
            found.update(_walk_references(item, issue_number, slug))
    return sorted(found)


def _walk_pr_urls(value: Any, slug: str | None = None) -> list[int]:
    found: set[int] = set()
    if isinstance(value, str):
        if slug:
            repo_path = re.escape(slug.strip("/"))
            url_pattern = re.compile(rf"(?i)(?:https?://[^\s/]+/)?{repo_path}/pull/([1-9][0-9]*)")
            found.update(int(match.group(1)) for match in url_pattern.finditer(value))
            found.update(int(match.group(2)) for match in FULL_PR_REF_RE.finditer(value) if match.group(1).lower() == slug.lower())
    elif isinstance(value, Mapping):
        for item in value.values():
            found.update(_walk_pr_urls(item, slug))
    elif isinstance(value, list):
        for item in value:
            found.update(_walk_pr_urls(item, slug))
    return sorted(found)


def _timeline_pr_numbers(value: Any) -> list[int]:
    """Extract PR numbers from REST cross-reference event shape."""

    found: set[int] = set()
    if isinstance(value, Mapping):
        source = value.get("source")
        if isinstance(source, Mapping):
            source_issue = source.get("issue")
            if isinstance(source_issue, Mapping) and isinstance(source_issue.get("pull_request"), Mapping):
                number = source_issue.get("number")
                if isinstance(number, int) and number > 0:
                    found.add(number)
        for item in value.values():
            found.update(_timeline_pr_numbers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_timeline_pr_numbers(item))
    return sorted(found)


def _gh_json(repo: Path, args: Sequence[str], fallbacks: Sequence[Sequence[str]] = ()) -> tuple[Any, str | None]:
    try:
        return run_gh(repo, *args), None
    except PreflightError as exc:
        for fallback in fallbacks:
            try:
                return run_gh(repo, *fallback), f"primary query failed; fallback used: {exc}"
            except PreflightError:
                continue
        return None, str(exc)


def collect_issue_context(
    repo: Path,
    issue_number: int,
    slug: str | None,
    *,
    current_branch: str | None = None,
    target_ref: str | None = None,
) -> dict[str, Any]:
    if not slug:
        return {"status": "unknown", "issue": None, "related": {"status": "unknown", "items": [], "errors": ["repository slug is unavailable"]}}
    issue, issue_error = _gh_json(
        repo,
        ("issue", "view", str(issue_number), "--repo", slug, "--json", "number,title,body,state,url,updatedAt,closedAt,labels"),
        (("issue", "view", str(issue_number), "--repo", slug, "--json", "number,title,body,state,url"),),
    )
    if issue_error or not isinstance(issue, Mapping):
        issue_data: dict[str, Any] = {"number": issue_number}
        return {"status": "unknown", "issue": issue_data, "issue_error": issue_error or "issue API returned no object", "related": {"status": "unknown", "items": [], "errors": ["issue context unavailable"]}}
    timeline, timeline_error = _gh_json(repo, ("api", f"repos/{slug}/issues/{issue_number}/timeline", "--paginate"))
    pr_list, list_error = _gh_json(
        repo,
        ("pr", "list", "--repo", slug, "--state", "all", "--limit", "1000", "--search", f"#{issue_number}", "--json", "number,title,body,state,isDraft,url,baseRefName,baseRefOid,headRefName,headRefOid,mergeCommit,mergedAt,updatedAt"),
        (("pr", "list", "--repo", slug, "--state", "all", "--limit", "1000", "--json", "number,title,body,state,url,baseRefName,baseRefOid,headRefName,headRefOid,mergeCommit,mergedAt"),),
    )
    branch_prs: Any = []
    branch_error: str | None = None
    target_branch = target_ref.removeprefix("refs/remotes/origin/") if isinstance(target_ref, str) else None
    if current_branch and current_branch != target_branch:
        branch_prs, branch_error = _gh_json(
            repo,
            ("pr", "list", "--repo", slug, "--state", "all", "--limit", "1000", "--head", current_branch, "--json", "number,title,body,state,isDraft,url,baseRefName,baseRefOid,headRefName,headRefOid,mergeCommit,mergedAt,updatedAt"),
        )
        if branch_error is None and not isinstance(branch_prs, list):
            branch_error = "current branch PR discovery returned no list"
    timeline_refs = sorted(set(_walk_pr_urls(timeline, slug)) | set(_timeline_pr_numbers(timeline))) if timeline_error is None else []
    body_refs = _parse_linked_pr_refs(issue.get("body"), issue_number, slug)
    candidates: set[int] = set(timeline_refs) | set(body_refs)
    discovered: list[dict[str, Any]] = []
    if isinstance(pr_list, list):
        for item in pr_list:
            if not isinstance(item, Mapping):
                continue
            try:
                number = int(item.get("number"))
            except (TypeError, ValueError):
                continue
            refs = _parse_issue_refs(item.get("body"), 0, slug)
            # ``gh pr list --search`` is a discovery aid, never semantic proof.
            # Retain candidates only when an exact issue reference or timeline
            # event binds them to this Issue.
            linked = number in candidates or issue_number in refs
            discovered.append({**dict(item), "number": number, "linked_by_exact_reference": linked, "reference_numbers": refs})
            if linked:
                candidates.add(number)
    branch_truncated = isinstance(branch_prs, list) and len(branch_prs) >= 1000
    if isinstance(branch_prs, list):
        for item in branch_prs:
            if not isinstance(item, Mapping):
                continue
            try:
                number = int(item.get("number"))
            except (TypeError, ValueError):
                continue
            refs = _parse_issue_refs(item.get("body"), 0, slug)
            existing = next((entry for entry in discovered if entry.get("number") == number), None)
            if existing is None:
                discovered.append({
                    **dict(item),
                    "number": number,
                    "linked_by_exact_reference": number in candidates or issue_number in refs,
                    "linked_by_current_branch": True,
                    "current_branch": current_branch,
                    "reference_numbers": refs,
                })
            else:
                existing["linked_by_current_branch"] = True
                existing["current_branch"] = current_branch
            candidates.add(number)
    list_truncated = isinstance(pr_list, list) and len(pr_list) >= 1000
    if list_error or list_truncated:
        list_status = "unknown"
    else:
        list_status = "ok"
    items_by_number: dict[int, dict[str, Any]] = {}
    for item in discovered:
        if item.get("linked_by_exact_reference") or item.get("linked_by_current_branch"):
            items_by_number[int(item["number"])] = item
    # Exact references in the Issue/timeline may not be returned by ``pr list``;
    # fetch each referenced PR in all states by number.
    for number in sorted(candidates):
        if number in items_by_number:
            continue
        pr, pr_error = _gh_json(
            repo,
            ("pr", "view", str(number), "--repo", slug, "--json", "number,title,body,state,isDraft,url,baseRefName,baseRefOid,headRefName,headRefOid,mergeCommit,mergedAt,updatedAt"),
            (("pr", "view", str(number), "--repo", slug, "--json", "number,title,body,state,url,baseRefName,baseRefOid,headRefName,headRefOid,mergeCommit,mergedAt"),),
        )
        if pr_error or not isinstance(pr, Mapping):
            items_by_number[number] = {"number": number, "status": "unknown", "error": pr_error or "PR API returned no object"}
        else:
            item = dict(pr)
            item["number"] = number
            item["linked_by_exact_reference"] = True
            item["reference_numbers"] = _parse_issue_refs(item.get("body"), 0, slug)
            items_by_number[number] = item
    lookup_errors = [str(item.get("error")) for item in items_by_number.values() if item.get("status") == "unknown" and item.get("error")]
    errors = [value for value in (timeline_error, list_error) if value]
    if branch_error:
        errors.append(branch_error)
    errors.extend(lookup_errors)
    if list_truncated:
        errors.append("related PR discovery reached its bounded --limit=1000")
    if branch_truncated:
        errors.append("current branch PR discovery reached its bounded --limit=1000")
    related_status = "unknown" if errors else "ok"
    return {
        "status": "ok",
        "issue": dict(issue),
        "issue_relevant": _issue_relevant(issue),
        "issue_error": None,
        "related": {
            "status": related_status,
            "items": [items_by_number[number] for number in sorted(items_by_number)],
            "discovered_candidates": discovered,
            "timeline_reference_numbers": timeline_refs,
            "body_reference_numbers": body_refs,
            "current_branch": current_branch,
            "current_branch_reference_numbers": sorted(
                int(item["number"])
                for item in discovered
                if item.get("linked_by_current_branch") and isinstance(item.get("number"), int)
            ),
            "errors": errors,
        },
    }


def _criteria_snapshot(criteria: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(json.dumps(item)) for item in criteria]


def _fetch_and_target(repo: Path, target: str | None, base: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    target_ref = normalize_target_ref(target) if target else normalize_target_ref(default_target_ref(repo))
    base_ref = normalize_ref(base) if base else None
    creation_base_sha = resolve_commit(repo, base_ref, check=False) if base_ref else None
    before_target_sha = resolve_commit(repo, target_ref, check=False)
    ok, fetch_error = fetch_origin(repo)
    current_target_sha = resolve_commit(repo, target_ref, check=False) if ok else None
    return {
        "ref": target_ref,
        "sha": current_target_sha,
        "before_fetch_sha": before_target_sha,
        "fetch_status": "ok" if ok else "unknown",
        "fetch_error": redact_diagnostic(fetch_error) if fetch_error else None,
    }, {
        "ref": base_ref,
        "sha": creation_base_sha,
        "captured_before_fetch": bool(base_ref),
        "status": "known" if base_ref else "unknown",
        "reason": None if base_ref else "not_provided",
    }


def collect_evidence(
    repo_arg: str | os.PathLike[str],
    issue_number: int,
    *,
    criteria: Sequence[Mapping[str, Any]] = (),
    target: str | None = None,
    creation_base: str | None = None,
    fetch: bool = True,
) -> dict[str, Any]:
    repo = repo_root(repo_arg)
    if not isinstance(issue_number, int) or issue_number < 1:
        raise PreflightError("Issue number must be positive")
    identity = repository_identity(repo)
    if fetch:
        try:
            current_target, base = _fetch_and_target(repo, target, creation_base)
        except PreflightError as exc:
            try:
                target_ref = normalize_target_ref(target) if target else None
            except PreflightError:
                target_ref = None
            current_target = {"ref": target_ref, "sha": None, "before_fetch_sha": None, "fetch_status": "unknown", "fetch_error": redact_diagnostic(str(exc))}
            base_ref = normalize_ref(creation_base) if creation_base else None
            base = {
                "ref": base_ref,
                "sha": resolve_commit(repo, base_ref, check=False) if base_ref else None,
                "captured_before_fetch": bool(creation_base),
                "status": "known" if creation_base else "unknown",
                "reason": None if creation_base else "not_provided",
            }
    else:
        target_ref = normalize_target_ref(target) if target else normalize_target_ref(default_target_ref(repo))
        current_target = {"ref": target_ref, "sha": resolve_commit(repo, target_ref, check=False), "before_fetch_sha": None, "fetch_status": "not_requested", "fetch_error": None}
        base_ref = normalize_ref(creation_base) if creation_base else None
        base = {
            "ref": base_ref,
            "sha": resolve_commit(repo, base_ref, check=False) if base_ref else None,
            "captured_before_fetch": bool(base_ref),
            "status": "known" if base_ref else "unknown",
            "reason": None if base_ref else "not_provided",
        }
    slug = identity.get("slug")
    api_binding_error: str | None = None
    # The GitHub CLI's repository metadata is authoritative when available,
    # but it must be queried for the exact origin owner/repository rather than
    # trusting GH_REPO or the ambient current directory.
    if not slug or not identity.get("remote_host"):
        api_binding_error = "origin repository host/owner/repository identity is unavailable"
        repo_view = None
    else:
        try:
            repo_view_args = ("repo", "view", "--repo", str(slug), "--json", "nameWithOwner,defaultBranchRef")
            repo_view = run_gh(repo, *repo_view_args)
            if isinstance(repo_view, Mapping) and isinstance(repo_view.get("nameWithOwner"), str):
                if repo_view["nameWithOwner"].lower() != str(slug).lower():
                    api_binding_error = "GitHub repository metadata does not match origin owner/repository"
                slug = repo_view["nameWithOwner"]
            else:
                api_binding_error = "GitHub repository metadata is unavailable"
        except PreflightError as exc:
            api_binding_error = str(exc)
            repo_view = None
    context = collect_issue_context(
        repo,
        issue_number,
        slug,
        current_branch=identity.get("current_branch"),
        target_ref=current_target.get("ref"),
    )
    if api_binding_error:
        context["status"] = "unknown"
        context["issue_error"] = api_binding_error
    if current_target.get("sha"):
        if current_target.get("fetch_status") in {"ok", "not_requested"}:
            try:
                criterion_results = evaluate_criteria(
                    repo,
                    str(current_target["sha"]),
                    criteria,
                    issue_relevant_sha256=(context.get("issue_relevant") or {}).get("sha256"),
                )
            except PreflightError as exc:
                criterion_results = [{"id": "collection", "requirement": "target tree", "status": "unknown", "rationale": str(exc), "residual_scope": "target tree", "evidence": []}]
        else:
            criterion_results = [{"id": item.get("id", f"criterion-{index + 1}"), "requirement": item.get("requirement", item.get("id", "criterion")), "status": "unknown", "rationale": "git fetch failed; current target was not verified", "residual_scope": "target fetch", "evidence": []} for index, item in enumerate(criteria)]
    else:
        criterion_results = [{"id": item.get("id", f"criterion-{index + 1}"), "requirement": item.get("requirement", item.get("id", "criterion")), "status": "unknown", "rationale": "current target commit is unavailable", "residual_scope": "target commit", "evidence": []} for index, item in enumerate(criteria)]
    statuses = [item["status"] for item in criterion_results]
    related = context.get("related") or {}
    if not criteria:
        decision = "unknown"
    elif (
        "unknown" in statuses
        or current_target.get("fetch_status") == "unknown"
        or context.get("status") == "unknown"
        or related.get("status") == "unknown"
    ):
        decision = "unknown"
    elif all(status == "satisfied" for status in statuses):
        decision = "satisfied"
    else:
        decision = "needs_work"
    issue = context.get("issue") or {"number": issue_number}
    issue_relevant = context.get("issue_relevant") or {"fields": {"number": issue_number}, "sha256": sha256(canonical_json({"number": issue_number}))}
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "kind": EVIDENCE_KIND,
        "collected_at": utc_now(),
        "repository": {**identity, "slug": slug},
        "issue": {"number": issue_number, "state": issue.get("state"), "title": issue.get("title"), "url": issue.get("url")},
        "issue_relevant": issue_relevant,
        "issue_snapshot": issue,
        "creation_base": base,
        "current_target": current_target,
        "criteria_specs": _criteria_snapshot(criteria),
        "requirements": criterion_results,
        "related_prs": context.get("related", {"status": "unknown", "items": [], "errors": ["related PR context unavailable"]}),
        "collection": {
            "fetch": {"status": current_target.get("fetch_status"), "error": current_target.get("fetch_error")},
            "issue": {"status": context.get("status"), "error": context.get("issue_error")},
            "related_prs": {"status": (context.get("related") or {}).get("status", "unknown"), "errors": (context.get("related") or {}).get("errors", [])},
        },
        "decision": decision,
        "no_edit_or_pr": decision == "satisfied",
    }
    return evidence


def _validate_shape(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "kind", "repository", "issue", "creation_base", "current_target", "criteria_specs", "requirements", "related_prs", "collection", "decision"}
    errors.extend(f"missing field: {key}" for key in sorted(required - set(data)))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported evidence schema")
    if data.get("kind") != EVIDENCE_KIND:
        errors.append("unsupported evidence kind")
    if data.get("decision") not in DECISIONS:
        errors.append("invalid decision")
    if not isinstance(data.get("criteria_specs"), list) or not isinstance(data.get("requirements"), list):
        errors.append("criteria_specs and requirements must be arrays")
    ids: set[str] = set()
    for item in data.get("requirements", []):
        if not isinstance(item, Mapping):
            errors.append("requirement entry must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in ids:
            errors.append("requirement ids must be non-empty and unique")
        if isinstance(item_id, str):
            ids.add(item_id)
        if item.get("status") not in STATUSES:
            errors.append(f"invalid requirement status: {item_id}")
        if not isinstance(item.get("rationale"), str) or not item.get("rationale", "").strip():
            errors.append(f"requirement rationale is empty: {item_id}")
        if not isinstance(item.get("residual_scope"), str) or not item.get("residual_scope", "").strip():
            errors.append(f"requirement residual_scope is empty: {item_id}")
        if not isinstance(item.get("evidence"), list):
            errors.append(f"requirement evidence must be an array: {item_id}")
        elif item.get("status") in {"satisfied", "missing"} and not item["evidence"]:
            errors.append(f"confirmed requirement lacks source/search/test evidence: {item_id}")
    target = data.get("current_target")
    if not isinstance(target, Mapping) or not SHA_RE.fullmatch(str(target.get("sha", ""))):
        errors.append("current_target.sha must be a full commit SHA")
    elif not isinstance(target.get("ref"), str) or not str(target.get("ref")).startswith("refs/remotes/origin/"):
        errors.append("current_target.ref must be a live origin remote ref")
    base = data.get("creation_base")
    if not isinstance(base, Mapping) or base.get("sha") is not None and not SHA_RE.fullmatch(str(base.get("sha"))):
        errors.append("creation_base.sha must be a full commit SHA or null")
    return errors


def _verify_source_bindings(repo: Path, data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    target = data.get("current_target") or {}
    target_sha = target.get("sha")
    if not isinstance(target_sha, str):
        return ["current target SHA is unavailable"]
    resolved = resolve_commit(repo, target_sha, check=False)
    if resolved != target_sha.lower():
        return ["current target commit is unavailable or changed"]
    try:
        entries = _tree_entries(repo, target_sha)
    except PreflightError as exc:
        return [str(exc)]
    for requirement in data.get("requirements", []):
        for item in requirement.get("evidence", []) if isinstance(requirement, Mapping) else []:
            if not isinstance(item, Mapping) or item.get("kind") not in {"source", "search", "test"}:
                continue
            path = item.get("path")
            blob = item.get("blob")
            if not isinstance(path, str):
                if item.get("status") in {"satisfied", "missing"}:
                    errors.append(f"cited evidence lacks path: {requirement.get('id')}")
                continue
            try:
                normalized = normalize_path(path)
            except PreflightError:
                errors.append(f"cited evidence path is unsafe: {path}")
                continue
            entry = entries.get(normalized)
            if not isinstance(blob, str):
                if item.get("status") == "satisfied" and item.get("exists") is False and entry is None:
                    continue
                if item.get("status") == "missing" and entry is None:
                    continue
                if item.get("status") == "satisfied":
                    errors.append(f"satisfied evidence lacks a blob binding: {path}")
                continue
            if entry is None:
                if item.get("status") == "satisfied":
                    errors.append(f"satisfied evidence path disappeared: {path}")
                continue
            if item.get("status") == "satisfied" and entry.get("blob") != blob:
                errors.append(f"cited blob does not bind to current target: {path}")
    return errors


def _repository_binding_errors(expected: Any, actual: Any, *, label: str = "repository") -> list[str]:
    """Compare only the stable origin identity carried by an evidence packet.

    A clone path, current checkout branch, and current checkout SHA are local
    state and may legitimately differ while a packet is being resumed.  The
    remote host and owner/repository identity are the binding that prevents a
    packet from another repository with the same tree and Issue-shaped data
    from being reused.
    """

    if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
        return [f"{label} identity is unavailable"]
    errors: list[str] = []
    for key in ("remote_host", "slug"):
        expected_value = expected.get(key)
        actual_value = actual.get(key)
        if not isinstance(expected_value, str) or not expected_value.strip():
            errors.append(f"{label}.{key} is unavailable")
        elif not isinstance(actual_value, str) or not actual_value.strip():
            errors.append(f"current {label}.{key} is unavailable")
        elif expected_value.casefold() != actual_value.casefold():
            errors.append(f"{label}.{key} does not match current repository")
    return errors


def validate_evidence_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    errors = _validate_shape(data)
    return {"valid": not errors, "errors": errors}


def validate_bound_evidence(repo_arg: str | os.PathLike[str], data: Mapping[str, Any]) -> dict[str, Any]:
    shape = validate_evidence_shape(data)
    if not shape["valid"]:
        return {**shape, "bound": False}
    repo = repo_root(repo_arg)
    errors = _repository_binding_errors(data.get("repository"), repository_identity(repo))
    errors.extend(_verify_source_bindings(repo, data))
    return {"valid": not errors, "bound": not errors, "errors": errors}


def validate_evidence(
    repo_arg: str | os.PathLike[str],
    data: Mapping[str, Any],
    *,
    refresh: bool = True,
) -> dict[str, Any]:
    repo = repo_root(repo_arg)
    bound = validate_bound_evidence(repo, data)
    if not bound.get("valid"):
        return {"valid": False, "fresh": False, "bound": bound.get("bound", False), "errors": bound.get("errors", [])}
    if not refresh:
        return {"valid": True, "fresh": False, "bound": True, "errors": []}
    stored_base = data.get("creation_base") or {}
    stored_base_sha = stored_base.get("sha") if isinstance(stored_base, Mapping) else None
    stored_base_ref = stored_base.get("ref") if isinstance(stored_base, Mapping) else None
    # Re-collect against the immutable creation SHA.  The recorded ref is
    # provenance only; it may move or disappear after the lifecycle starts.
    creation_base_arg = stored_base_sha if isinstance(stored_base_sha, str) else None
    current = collect_evidence(
        repo,
        int(data["issue"]["number"]),
        criteria=data.get("criteria_specs", []),
        target=str(data["current_target"]["ref"]),
        creation_base=creation_base_arg,
        fetch=True,
    )
    mismatches: list[str] = []
    collected_base = current.get("creation_base") or {}
    collected_base_snapshot = dict(collected_base) if isinstance(collected_base, Mapping) else {}
    current["creation_base"] = {
        **collected_base_snapshot,
        "ref": stored_base_ref,
        "sha": stored_base_sha,
        "status": stored_base.get("status") if isinstance(stored_base, Mapping) else "unknown",
        "reason": stored_base.get("reason") if isinstance(stored_base, Mapping) else "not_provided",
    }
    if not isinstance(stored_base_sha, str):
        mismatches.append("creation base SHA is unavailable")
    else:
        resolved_base = resolve_commit(repo, stored_base_sha, check=False)
        if resolved_base != stored_base_sha.lower():
            mismatches.append("creation base SHA is unavailable")
        if collected_base_snapshot.get("sha") != stored_base_sha.lower():
            mismatches.append("creation base SHA changed during recheck")
    if current.get("current_target", {}).get("sha") != data.get("current_target", {}).get("sha"):
        mismatches.append("current target SHA changed")
    mismatches.extend(_repository_binding_errors(data.get("repository"), current.get("repository"), label="repository"))
    if current.get("issue_relevant", {}).get("sha256") != data.get("issue_relevant", {}).get("sha256"):
        mismatches.append("Issue relevant content changed")
    if current.get("related_prs", {}).get("status") == "unknown":
        mismatches.append("related PR/API recheck is unknown")
    if current.get("collection", {}).get("fetch", {}).get("status") == "unknown":
        mismatches.append("origin fetch failed")
    if current.get("collection", {}).get("issue", {}).get("status") == "unknown":
        mismatches.append("Issue API recheck failed")
    if current.get("decision") != data.get("decision") or current.get("requirements") != data.get("requirements"):
        mismatches.append("requirement evidence changed")
    return {
        "valid": not mismatches,
        "fresh": not mismatches,
        "bound": True,
        "errors": mismatches,
        "current": current,
    }


def _patch_bytes(repo: Path, base_sha: str, head_sha: str) -> bytes:
    return run_git(repo, "diff", "--no-ext-diff", "--binary", "--no-renames", base_sha, head_sha, "--")


def _safe_merge_tree(repo: Path, base_sha: str, head_sha: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="issue-preflight-merge-") as temp:
        temp_path = Path(temp)
        init = _run(("git", "init", "--bare", "--quiet", str(temp_path)), timeout=30)
        if init.returncode:
            raise PreflightError("cannot initialize isolated merge object directory")
        objects = run_git(repo, "rev-parse", "--git-path", "objects").decode().strip()
        objects_path = Path(objects)
        if not objects_path.is_absolute():
            objects_path = (repo / objects_path).resolve()
        alternate_dir = temp_path / "objects" / "info"
        alternate_dir.mkdir(parents=True, exist_ok=True)
        (alternate_dir / "alternates").write_text(str(objects_path) + "\n", encoding="utf-8")
        env = os.environ.copy()
        for key in list(env):
            if key.startswith("GIT_"):
                env.pop(key, None)
        env.update({
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_DIR": str(temp_path),
        })
        # The temporary bare object database has no repository config, hooks,
        # or custom merge-driver definitions.  Attributes in a tree may name a
        # driver, but an unconfigured driver cannot execute a repository command.
        result = _run(("git", "--git-dir", str(temp_path), "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null", "merge-tree", "--write-tree", base_sha, head_sha), env=env, timeout=60)
        output = (result.stdout + result.stderr).decode("utf-8", "replace")
        tree_match = re.search(r"(?m)^([0-9a-f]{40,64})\s*$", output)
        tree_sha = tree_match.group(1).lower() if tree_match else None
        effective_paths: list[str] = []
        effective_patch_hash: str | None = None
        if result.returncode == 0 and tree_sha:
            diff = _run(
                ("git", "--git-dir", str(temp_path), "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null", "diff", "--no-ext-diff", "--binary", "--no-renames", base_sha, tree_sha, "--"),
                env=env,
                timeout=60,
            )
            if diff.returncode:
                return {"status": "unknown", "returncode": diff.returncode, "tree": tree_sha, "output": (diff.stderr.decode("utf-8", "replace") or output)[-4000:]}
            effective_patch = diff.stdout
            effective_patch_hash = sha256(effective_patch)
            names = _run(
                ("git", "--git-dir", str(temp_path), "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null", "diff", "--name-only", "-z", "--no-renames", base_sha, tree_sha, "--"),
                env=env,
                timeout=60,
            )
            if names.returncode:
                return {"status": "unknown", "returncode": names.returncode, "tree": tree_sha, "output": (names.stderr.decode("utf-8", "replace") or output)[-4000:]}
            effective_paths = sorted(item for item in names.stdout.decode("utf-8", "surrogateescape").split("\0") if item)
        return {
            "status": "ok" if result.returncode == 0 else "conflict",
            "returncode": result.returncode,
            "tree": tree_sha,
            "effective_paths": effective_paths,
            "effective_patch_sha256": effective_patch_hash,
            "output": output[-4000:],
        }


def validate_pr(
    repo_arg: str | os.PathLike[str],
    *,
    base_ref: str,
    head_sha: str,
    expected_head_sha: str | None = None,
    related_prs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo = repo_root(repo_arg)
    base = normalize_ref(base_ref)
    current_base = resolve_commit(repo, base, check=False)
    current_head = resolve_commit(repo, head_sha, check=False)
    reasons: list[str] = []
    if current_base is None:
        reasons.append("current base ref is unavailable")
    if current_head is None:
        reasons.append("submitted head is unavailable")
    if expected_head_sha and current_head != expected_head_sha.lower():
        reasons.append("submitted head SHA is stale")
    try:
        status_result = _run(
            ("git", "-C", str(repo), "status", "--porcelain=v2", "--untracked-files=all"),
            timeout=60,
        )
    except PreflightError as exc:
        reasons.append(f"worktree status could not be verified: {exc}")
    else:
        if status_result.returncode:
            reasons.append("worktree status could not be verified")
        elif status_result.stdout:
            reasons.append("worktree is not clean")
    if current_base and current_head:
        try:
            merge = _safe_merge_tree(repo, current_base, current_head)
            if merge["status"] != "ok":
                reasons.append("virtual merge has conflicts")
            elif not merge.get("effective_paths") or not merge.get("effective_patch_sha256"):
                reasons.append("effective merge delta is empty (possible squash duplicate or revert)")
            changed_paths = list(merge.get("effective_paths", []))
            patch_hash = merge.get("effective_patch_sha256")
        except PreflightError as exc:
            changed_paths = []
            patch_hash = None
            merge = {"status": "unknown", "output": str(exc)}
            reasons.append(str(exc))
    else:
        changed_paths = []
        patch_hash = None
        merge = {"status": "unknown", "output": "base/head unavailable"}
    # A merged PR is context, never semantic proof.  A squash duplicate is
    # denied only when the isolated merge result has a zero effective delta.
    duplicate_numbers: list[int] = []
    outcome = "deny" if reasons else "allow"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": outcome,
        "base_ref": base,
        "base_sha": current_base,
        "head_sha": current_head,
        "expected_head_sha": expected_head_sha,
        "changed_paths": changed_paths,
        "patch_sha256": patch_hash,
        "merge_tree": merge,
        "duplicate_related_prs": duplicate_numbers,
        "reasons": reasons,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="fetch and collect one deterministic Issue evidence packet")
    collect.add_argument("--repo", required=True)
    collect.add_argument("--issue", required=True, type=int)
    collect.add_argument("--criteria-file", "--criteria", dest="criteria_file")
    collect.add_argument("--target")
    collect.add_argument("--base", "--creation-base", dest="base")
    collect.add_argument("--output")
    validate = sub.add_parser("validate", help="re-fetch and validate an evidence packet")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--evidence-file", "--evidence", dest="evidence_file", required=True)
    validate.add_argument("--no-refresh", action="store_true")
    pr = sub.add_parser("pre-pr", help="validate a submitted head against the current target")
    pr.add_argument("--repo", required=True)
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    pr.add_argument("--expected-head")
    pr.add_argument("--evidence-file", "--evidence")
    return parser


def _main(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.command == "collect":
        criteria = load_criteria(args.criteria_file)
        evidence = collect_evidence(args.repo, args.issue, criteria=criteria, target=args.target, creation_base=args.base)
        if args.output:
            write_json(Path(args.output).expanduser().resolve(), evidence)
        return 0, evidence
    if args.command == "validate":
        data = _read_json_file(Path(args.evidence_file).expanduser().resolve())
        if not isinstance(data, Mapping):
            raise PreflightError("evidence root must be an object")
        result = validate_evidence(args.repo, data, refresh=not args.no_refresh)
        return 0 if result.get("valid") else 2, result
    if args.command == "pre-pr":
        related: Mapping[str, Any] | None = None
        evidence_validation: dict[str, Any] | None = None
        evidence_data: Mapping[str, Any] | None = None
        if args.evidence_file:
            value = _read_json_file(Path(args.evidence_file).expanduser().resolve())
            if isinstance(value, Mapping):
                evidence_data = value
                related = value.get("related_prs")
                evidence_validation = validate_evidence(args.repo, value, refresh=True)
        base_binding_errors: list[str] = []
        base_for_pr = args.base
        if evidence_data is not None and evidence_validation and evidence_validation.get("valid"):
            expected_target = evidence_data.get("current_target")
            if not isinstance(expected_target, Mapping):
                base_binding_errors.append("evidence current target is unavailable")
            else:
                expected_ref = expected_target.get("ref")
                expected_sha = expected_target.get("sha")
                try:
                    requested_ref = normalize_target_ref(args.base)
                except PreflightError as exc:
                    base_binding_errors.append(f"submitted base is not a live origin branch: {exc}")
                else:
                    base_for_pr = requested_ref
                    if requested_ref != expected_ref:
                        base_binding_errors.append("submitted base ref does not match evidence current target")
                    current_base = resolve_commit(repo_root(args.repo), requested_ref, check=False)
                    if current_base != expected_sha:
                        base_binding_errors.append("submitted base SHA does not match evidence current target")
        result = validate_pr(args.repo, base_ref=base_for_pr, head_sha=args.head, expected_head_sha=args.expected_head, related_prs=related)
        if not args.evidence_file:
            result["status"] = "unknown"
            result["reasons"] = ["Issue preflight evidence is required for readiness"] + list(result.get("reasons", []))
        elif evidence_validation is None or not evidence_validation.get("valid"):
            result["status"] = "unknown"
            result["reasons"] = ["Issue preflight evidence could not be freshly validated"] + list((evidence_validation or {}).get("errors", [])) + list(result.get("reasons", []))
        elif evidence_data.get("decision") != "needs_work":
            result["status"] = "unknown"
            result["reasons"] = [f"Issue preflight decision is {evidence_data.get('decision', 'unknown')}; readiness requires needs_work"] + list(result.get("reasons", []))
        if base_binding_errors:
            result["status"] = "unknown"
            result["reasons"] = base_binding_errors + list(result.get("reasons", []))
        result["ready"] = result.get("status") == "allow"
        return 0 if result["ready"] else 2, result
    raise PreflightError("unknown command")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        code, result = _main(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return code
    except (PreflightError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
