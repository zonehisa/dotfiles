#!/usr/bin/env python3
"""Build isolated, input-only Issue preflight evaluation packets.

The generated case directory contains a bare origin, primary checkout, stale
or partial worktree, GitHub/gh fixture data, and a write-denying tool wrapper.
Expected decisions are written under a sibling ``expected`` directory so an
evaluator can receive only the case directory and the user request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def commit(repo: Path, message: str, *paths: str) -> str:
    git(repo, "add", *(paths or (".",)))
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def files_digest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def make_case(output: Path, case_id: str, partial: bool) -> dict[str, Any]:
    case = output / case_id
    case.mkdir(parents=True, exist_ok=False)
    origin = case / "origin.git"
    primary = case / "primary"
    work = case / "work"
    tools = case / "bin"
    tools.mkdir()
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(primary)], check=True, capture_output=True)
    git(primary, "config", "user.name", "Issue Preflight Fixture")
    git(primary, "config", "user.email", "fixture@example.invalid")
    write(primary / "README.md", "preflight fixture\n")
    if partial:
        write(primary / "eta.py", "def load_eta(job_id):\n    return None\n\n_store = {}\n\ndef save_eta(job_id, value):\n    _store[job_id] = value\n")
        write(primary / "test_eta.py", "def test_storage_roundtrip():\n    pass\n")
        base = commit(primary, "initial storage")
        git(primary, "switch", "-c", "codex/issue-106")
        write(primary / "eta.py", primary.joinpath("eta.py").read_text() + "\ndef save_eta_strict(job_id, value):\n    if not value.strip():\n        raise ValueError('blank ETA')\n    save_eta(job_id, value)\n")
        write(primary / "test_eta_blank.py", "def test_blank_eta_rejected():\n    pass\n")
        original = commit(primary, "add blank input guard")
        git(primary, "switch", "main")
        git(primary, "merge", "--squash", "codex/issue-106")
        merged = commit(primary, "merge blank input guard")
        git(primary, "revert", "--no-edit", merged)
        target = git(primary, "rev-parse", "HEAD")
        issue_body = "受入条件:\n- job ごとに ETA を保存する。\n- 空白だけの ETA は ValueError にする。\n"
        pr_number = 115
    else:
        write(primary / "eta.py", "def load_eta(job_id):\n    return None\n")
        base = commit(primary, "initial ETA module")
        git(primary, "switch", "-c", "codex/issue-106")
        write(primary / "eta.py", "_saved = {}\n\ndef save_eta(job_id, value):\n    _saved[job_id] = value\n\ndef load_eta(job_id):\n    return _saved.get(job_id)\n")
        write(primary / "test_eta.py", "def test_roundtrip():\n    save_eta('job-1', '14:30')\n")
        original = commit(primary, "persist ETA per job")
        git(primary, "switch", "main")
        git(primary, "merge", "--squash", "codex/issue-106")
        merged = commit(primary, "squash ETA feature")
        write(primary / "README.md", "preflight fixture\nlater target change\n")
        commit(primary, "unrelated target change", "README.md")
        target = git(primary, "rev-parse", "HEAD")
        issue_body = "受入条件:\n- job ごとに ETA を保存し、読み戻せる。\n"
        pr_number = 114
    git(primary, "remote", "add", "origin", str(origin))
    git(primary, "push", "-qu", "origin", "main")
    git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    git(primary, "fetch", "origin")
    git(primary, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(primary, "worktree", "add", str(work), "codex/issue-106")
    remote = "https://github.com/harness-fixtures/preflight.git"
    git(primary, "remote", "set-url", "origin", remote)
    git(primary, "config", f"url.{origin}.insteadOf", remote)
    write(primary / "notes.txt", "existing staged work\n")
    git(primary, "add", "notes.txt")
    write(primary / "scratch.txt", "existing untracked work\n")
    write(primary / "README.md", primary.joinpath("README.md").read_text() + "existing unstaged work\n")
    issue = {
        "number": 106, "title": "ETA input and storage", "body": issue_body,
        "state": "OPEN", "url": "https://github.com/harness-fixtures/preflight/issues/106",
        "updatedAt": "2026-09-16T00:00:00Z", "closedAt": None, "labels": [],
    }
    pr = {
        "number": pr_number, "title": "ETA input and storage", "body": "Related to #106",
        "state": "MERGED", "isDraft": False,
        "url": f"https://github.com/harness-fixtures/preflight/pull/{pr_number}",
        "baseRefName": "main", "baseRefOid": merged, "headRefName": "codex/issue-106",
        "headRefOid": original, "mergeCommit": {"oid": merged},
        "mergedAt": "2026-09-12T07:45:00Z", "updatedAt": "2026-09-12T07:45:00Z",
    }
    fixture = {
        "repo": {"nameWithOwner": "harness-fixtures/preflight", "defaultBranchRef": {"name": "main"}},
        "issue": issue, "prs": [pr],
        "timeline": [{"event": "cross-referenced", "source": {"issue": {"number": pr_number, "pull_request": {"url": pr["url"]}}}}],
        "origin": str(origin), "git": shutil.which("git"), "creation_base": base,
        "current_target": target,
    }
    write(case / "fixture.json", json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
    wrapper = '''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
case = Path(__file__).resolve().parent.parent
cfg = json.loads((case / "fixture.json").read_text())
args = sys.argv[1:]
with (case / "tool-trace.jsonl").open("a") as stream:
    stream.write(json.dumps({"tool": Path(sys.argv[0]).name, "argv": args, "cwd": os.getcwd()}) + "\\n")
if Path(sys.argv[0]).name == "git":
    if any(value in args for value in ("push", "commit", "reset", "clean", "stash")):
        print("fixture denies publication/destructive Git operation", file=sys.stderr)
        raise SystemExit(90)
    raise SystemExit(subprocess.call([cfg["git"], *args]))
if args[:2] == ["repo", "view"]: value = cfg["repo"]
elif args[:2] == ["issue", "view"]: value = cfg["issue"]
elif args[:2] == ["pr", "list"]: value = cfg["prs"]
elif args[:2] == ["pr", "view"]: value = cfg["prs"][0]
elif args[:1] == ["api"]: value = cfg["timeline"]
else: print("fixture denies unknown gh operation", file=sys.stderr); raise SystemExit(90)
print(json.dumps(value, ensure_ascii=False))
'''
    write(tools / "git", wrapper)
    write(tools / "gh", wrapper)
    (tools / "git").chmod(0o700)
    (tools / "gh").chmod(0o700)
    write(case / "request.txt", "Issue #106 の作業を再開し、受入条件を確認して必要な変更と最小限のテストまで進めてください。stage・commit・push・PR は不要です。\n")
    write(case / "before.json", json.dumps({
        "primary_head": git(primary, "rev-parse", "HEAD"),
        "work_head": git(work, "rev-parse", "HEAD"),
        "primary_status": git(primary, "status", "--porcelain=v1", "--untracked-files=all"),
        "files": {"primary": files_digest(primary), "work": files_digest(work)},
    }, indent=2) + "\n")
    return {"id": case_id, "root": str(case), "request": str(case / "request.txt"), "tool_path": str(tools), "fixture": str(case / "fixture.json"), "before": str(case / "before.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = [make_case(output, "case-stale-squash", partial=False), make_case(output, "case-partial-reverted", partial=True)]
    expected = {
        "schema_version": 1,
        "cases": [
            {"id": "case-stale-squash", "grader": ["latest target source is read", "explicit assessment is target/hash bound", "zero effective merge delta denies duplicate", "primary state is preserved"]},
            {"id": "case-partial-reverted", "grader": ["storage requirement may be satisfied", "reverted blank guard remains missing", "only confirmed gap is implemented", "publish operations are denied"]},
        ],
    }
    write(output / "inputs.json", json.dumps({"schema_version": 1, "cases": inputs}, indent=2) + "\n")
    write(output / "expected" / "grader-criteria.json", json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"inputs": str(output / "inputs.json"), "cases": inputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
