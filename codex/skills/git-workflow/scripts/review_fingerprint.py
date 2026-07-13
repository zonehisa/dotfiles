#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")

    return result.stdout.strip()


def git_bytes(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_data: bytes | None = None,
) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        input=input_data,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")

    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fingerprint the intended Git tree and its review base without changing the repository index.",
    )
    parser.add_argument("--base", required=True, help="Review base ref, for example origin/main")
    parser.add_argument(
        "--content-base",
        help="Commit used to identify changed paths; defaults to HEAD. Pass the reviewed HEAD after committing.",
    )
    parser.add_argument("--repo", default=".", help="Repository path (defaults to the current directory)")
    args = parser.parse_args()

    repo = Path(git("rev-parse", "--show-toplevel", cwd=Path(args.repo))).resolve()
    base_commit = git("rev-parse", args.base, cwd=repo)
    head_commit = git("rev-parse", "HEAD", cwd=repo)
    content_base = git("rev-parse", args.content_base or "HEAD", cwd=repo)
    status = git("status", "--porcelain=v1", "--untracked-files=all", cwd=repo)
    git_bytes(
        "submodule",
        "foreach",
        "--quiet",
        "--recursive",
        'test -z "$(git status --porcelain --untracked-files=all)"',
        cwd=repo,
    )
    submodule_status = git_bytes("submodule", "status", "--recursive", cwd=repo)
    tracked_patch = git_bytes("diff", "--binary", "HEAD", "--", cwd=repo)
    untracked_output = git_bytes("ls-files", "--others", "--exclude-standard", "-z", cwd=repo)
    untracked_paths = sorted(path for path in untracked_output.split(b"\0") if path)
    changed_output = git_bytes("diff", "--name-only", "-z", content_base, "--", cwd=repo)
    changed_paths = sorted(set(path for path in changed_output.split(b"\0") if path) | set(untracked_paths))

    fingerprint = hashlib.sha256()
    fingerprint.update(b"base\0" + base_commit.encode() + b"\0")
    fingerprint.update(b"head\0" + head_commit.encode() + b"\0")
    fingerprint.update(b"tracked-diff\0" + tracked_patch + b"\0")
    fingerprint.update(b"submodules\0" + submodule_status + b"\0")

    for raw_path in untracked_paths:
        path = repo / os.fsdecode(raw_path)
        fingerprint.update(b"untracked\0" + raw_path + b"\0")
        fingerprint.update(str(path.lstat().st_mode).encode() + b"\0")
        if path.is_symlink():
            fingerprint.update(os.readlink(path).encode(errors="surrogateescape"))
        else:
            fingerprint.update(path.read_bytes())
        fingerprint.update(b"\0")

    content_fingerprint = hashlib.sha256()
    content_fingerprint.update(b"content-base\0" + content_base.encode() + b"\0")
    for raw_path in changed_paths:
        path = repo / os.fsdecode(raw_path)
        content_fingerprint.update(b"path\0" + raw_path + b"\0")
        if not path.exists() and not path.is_symlink():
            content_fingerprint.update(b"deleted\0")
            continue

        content_fingerprint.update(str(path.lstat().st_mode).encode() + b"\0")
        if path.is_symlink():
            content_fingerprint.update(os.readlink(path).encode(errors="surrogateescape"))
        elif path.is_dir():
            content_fingerprint.update(git("-C", str(path), "rev-parse", "HEAD", cwd=repo).encode())
        else:
            content_fingerprint.update(path.read_bytes())
        content_fingerprint.update(b"\0")

    print(json.dumps({
        "artifact_hash": fingerprint.hexdigest(),
        "base_commit": base_commit,
        "content_base": content_base,
        "content_hash": content_fingerprint.hexdigest(),
        "head_commit": head_commit,
        "working_tree_clean": status == "",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
