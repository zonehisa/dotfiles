#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
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


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def safe_temp_parent(repo: Path) -> Path:
    candidates = [Path("/tmp"), Path("/var/tmp"), Path(tempfile.gettempdir())]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved == repo or is_within(resolved, repo):
            continue
        if resolved.is_dir() and os.access(resolved, os.W_OK):
            return resolved
    raise RuntimeError("no writable temporary directory outside the repository")


def index_debug_entries(repo: Path, read_env: dict[str, str]) -> list[tuple[bytes, bytes]]:
    output = git_bytes("ls-files", "--debug", "-z", cwd=repo, env=read_env)
    entries: list[tuple[bytes, bytes]] = []
    position = 0
    while position < len(output):
        separator = output.find(b"\0", position)
        if separator < 0:
            raise RuntimeError("cannot parse Git index debug output")
        raw_path = output[position:separator]
        metadata_start = separator + 1
        metadata_end = metadata_start
        for _ in range(5):
            metadata_end = output.find(b"\n", metadata_end)
            if metadata_end < 0:
                raise RuntimeError("cannot parse Git index stat metadata")
            metadata_end += 1
        entries.append((raw_path, output[metadata_start:metadata_end]))
        position = metadata_end
    return entries


def staged_index_entries(repo: Path, read_env: dict[str, str]) -> dict[bytes, tuple[bytes, bytes]]:
    output = git_bytes("ls-files", "--stage", "-z", cwd=repo, env=read_env)
    entries: dict[bytes, tuple[bytes, bytes]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, object_id, stage = header.split(b" ")
        if stage != b"0":
            raise RuntimeError("review fingerprint requires a conflict-free staged index")
        entries[raw_path] = (mode, object_id)
    return entries


def index_flags(metadata: bytes) -> int:
    match = re.search(rb"\bflags: ([0-9a-fA-F]+)\n$", metadata)
    if not match:
        raise RuntimeError("cannot parse Git index flags")
    return int(match.group(1), 16)


def intent_to_add_paths(repo: Path, read_env: dict[str, str]) -> list[bytes]:
    return [
        raw_path
        for raw_path, metadata in index_debug_entries(repo, read_env)
        if index_flags(metadata) & 0x20000000
    ]


def custom_filter_driver(repo: Path, raw_path: bytes, read_env: dict[str, str]) -> bytes | None:
    output = git_bytes(
        "check-attr",
        "-z",
        "filter",
        "--",
        os.fsdecode(raw_path),
        cwd=repo,
        env=read_env,
    )
    parts = output.split(b"\0")
    if len(parts) != 4 or parts[0] != raw_path or parts[1] != b"filter" or parts[3] != b"":
        raise RuntimeError("cannot parse Git filter attribute")
    return None if parts[2] in {b"unspecified", b"unset"} else parts[2]


def has_stat_dirty_tracked_file(repo: Path, read_env: dict[str, str]) -> bool:
    entries = staged_index_entries(repo, read_env)
    filemode = git("config", "--bool", "core.filemode", cwd=repo, env=read_env) != "false"
    stat_pattern = re.compile(
        rb"^  ctime: (\d+):(\d+)\n"
        rb"  mtime: (\d+):(\d+)\n"
        rb"  dev: \d+\tino: \d+\n"
        rb"  uid: \d+\tgid: \d+\n"
        rb"  size: (\d+)\tflags: [0-9a-fA-F]+\n$"
    )
    for raw_path, metadata in index_debug_entries(repo, read_env):
        entry = entries.get(raw_path)
        if entry is None:
            raise RuntimeError("cannot match Git index stat metadata to its staged entry")
        mode, object_id = entry
        if mode == b"160000":
            continue
        flags = index_flags(metadata)
        path = repo / os.fsdecode(raw_path)
        if not path.exists() and not path.is_symlink():
            if flags & 0x40000000:
                continue
            return True
        match = stat_pattern.fullmatch(metadata)
        if not match:
            raise RuntimeError("cannot parse Git index stat metadata")
        current = path.lstat()
        ctime_ns = int(match.group(1)) * 1_000_000_000 + int(match.group(2))
        mtime_ns = int(match.group(3)) * 1_000_000_000 + int(match.group(4))
        size = int(match.group(5))
        if filemode and mode in {b"100644", b"100755"}:
            executable = bool(current.st_mode & 0o100)
            if executable != (mode == b"100755"):
                return True
        stat_changed = (
            current.st_ctime_ns != ctime_ns
            or current.st_mtime_ns != mtime_ns
            or current.st_size != size
        )
        if stat_changed:
            raw_content = (
                os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
            )
            current_object_id = git_bytes(
                "hash-object",
                "--stdin",
                cwd=repo,
                env=read_env,
                input_data=raw_content,
            ).strip()
            if current_object_id == object_id:
                continue
            if mode in {b"100644", b"100755"} and custom_filter_driver(
                repo, raw_path, read_env
            ):
                raise RuntimeError(
                    "filtered submodule file cannot be verified without executing its clean filter; "
                    f"review separately: {path}"
                )
            canonical_object_id = (
                git_bytes(
                    "hash-object",
                    f"--path={os.fsdecode(raw_path)}",
                    "--stdin",
                    cwd=repo,
                    env=read_env,
                    input_data=raw_content,
                ).strip()
                if mode in {b"100644", b"100755"}
                else current_object_id
            )
            if canonical_object_id != object_id:
                return True
    return False


def ensure_submodule_head_matches_staged_gitlink(
    submodule: Path,
    read_env: dict[str, str],
) -> None:
    superproject_raw = git(
        "rev-parse",
        "--show-superproject-working-tree",
        cwd=submodule,
        env=read_env,
    )
    if not superproject_raw:
        raise RuntimeError(f"cannot resolve superproject for submodule: {submodule}")
    superproject = Path(superproject_raw).resolve()
    try:
        relative_path = submodule.relative_to(superproject)
    except ValueError as error:
        raise RuntimeError(f"submodule is outside its reported superproject: {submodule}") from error
    entry = staged_index_entries(superproject, read_env).get(os.fsencode(relative_path))
    if entry is None or entry[0] != b"160000":
        raise RuntimeError(f"cannot find staged gitlink for submodule: {submodule}")
    submodule_head = git("rev-parse", "HEAD", cwd=submodule, env=read_env).encode()
    if submodule_head != entry[1]:
        raise RuntimeError(
            "submodule HEAD does not match its staged gitlink; stage it or review separately: "
            f"{submodule}"
        )


def ensure_clean_submodules(repo: Path, read_env: dict[str, str]) -> None:
    output = git_bytes(
        "submodule",
        "foreach",
        "--quiet",
        "--recursive",
        'printf "%s\\0" "$PWD"',
        cwd=repo,
        env=read_env,
    )
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        submodule = Path(os.fsdecode(raw_path)).resolve()
        ensure_submodule_head_matches_staged_gitlink(submodule, read_env)
        staged = git_bytes(
            "diff-index", "--cached", "--name-only", "HEAD", "--", cwd=submodule, env=read_env
        )
        untracked = git_bytes(
            "ls-files", "--others", "--exclude-standard", "-z", cwd=submodule, env=read_env
        )
        if staged or untracked or intent_to_add_paths(submodule, read_env) or has_stat_dirty_tracked_file(
            submodule, read_env
        ):
            raise RuntimeError(f"dirty submodule requires separate review: {submodule}")


def intended_tree(repo: Path, read_env: dict[str, str]) -> str:
    unmerged = git_bytes("ls-files", "--unmerged", "-z", cwd=repo, env=read_env)
    if unmerged:
        raise RuntimeError("review fingerprint requires a conflict-free staged index")
    if intent_to_add_paths(repo, read_env):
        raise RuntimeError("review fingerprint does not accept intent-to-add entries; stage or remove them")

    raw_objects_path = Path(git("rev-parse", "--git-path", "objects", cwd=repo, env=read_env))
    objects_path = raw_objects_path if raw_objects_path.is_absolute() else repo / raw_objects_path
    objects_path = objects_path.resolve()
    index_entries = git_bytes("ls-files", "--stage", "-z", cwd=repo, env=read_env)

    with tempfile.TemporaryDirectory(
        prefix="review-fingerprint-",
        dir=safe_temp_parent(repo),
    ) as directory:
        temp_root = Path(directory)
        if is_within(temp_root.resolve(), repo):
            raise RuntimeError("temporary fingerprint state must be outside the repository")
        temp_index = temp_root / "index"
        temp_objects = temp_root / "objects"
        temp_objects.mkdir()
        env = read_env.copy()
        env["GIT_INDEX_FILE"] = str(temp_index)
        env["GIT_OBJECT_DIRECTORY"] = str(temp_objects)
        alternates = [str(objects_path)]
        if env.get("GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            alternates.append(env["GIT_ALTERNATE_OBJECT_DIRECTORIES"])
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(alternates)

        git("read-tree", "--empty", cwd=repo, env=env)
        git_bytes("update-index", "-z", "--index-info", cwd=repo, env=env, input_data=index_entries)
        return git("write-tree", cwd=repo, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fingerprint the staged Git tree and its review base without changing the repository index.",
    )
    parser.add_argument("--base", required=True, help="Review base ref, for example origin/main")
    parser.add_argument(
        "--content-base",
        help="Commit used to identify changed paths; defaults to HEAD. Pass the reviewed HEAD after committing.",
    )
    parser.add_argument(
        "--patch-base",
        help="Commit whose tree is compared with the current worktree; defaults to --base.",
    )
    parser.add_argument("--repo", default=".", help="Repository path (defaults to the current directory)")
    args = parser.parse_args()

    read_env = os.environ.copy()
    read_env["GIT_OPTIONAL_LOCKS"] = "0"
    repo = Path(git("rev-parse", "--show-toplevel", cwd=Path(args.repo), env=read_env)).resolve()
    base_commit = git("rev-parse", args.base, cwd=repo, env=read_env)
    head_commit = git("rev-parse", "HEAD", cwd=repo, env=read_env)
    content_base = git("rev-parse", args.content_base or "HEAD", cwd=repo, env=read_env)
    patch_base = git("rev-parse", args.patch_base, cwd=repo, env=read_env) if args.patch_base else base_commit
    head_tree = git("rev-parse", "HEAD^{tree}", cwd=repo, env=read_env)
    patch_base_tree = git("rev-parse", f"{patch_base}^{{tree}}", cwd=repo, env=read_env)
    ensure_clean_submodules(repo, read_env)
    submodule_status = git_bytes("submodule", "status", "--recursive", cwd=repo, env=read_env)
    tracked_patch = git_bytes("diff", "--cached", "--binary", "HEAD", "--", cwd=repo, env=read_env)
    untracked_output = git_bytes(
        "ls-files", "--others", "--exclude-standard", "-z", cwd=repo, env=read_env
    )
    untracked_paths = sorted(path for path in untracked_output.split(b"\0") if path)
    intended_tree_hash = intended_tree(repo, read_env)

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

    patch_fingerprint = hashlib.sha256()
    patch_fingerprint.update(b"patch-base-tree\0" + patch_base_tree.encode() + b"\0")
    patch_fingerprint.update(b"intended-tree\0" + intended_tree_hash.encode() + b"\0")

    content_fingerprint = hashlib.sha256()
    content_fingerprint.update(b"content-base\0" + content_base.encode() + b"\0")
    content_fingerprint.update(b"intended-tree\0" + intended_tree_hash.encode() + b"\0")

    print(json.dumps({
        "artifact_hash": fingerprint.hexdigest(),
        "base_commit": base_commit,
        "content_base": content_base,
        "content_hash": content_fingerprint.hexdigest(),
        "head_tree": head_tree,
        "head_commit": head_commit,
        "patch_base": patch_base,
        "patch_base_tree": patch_base_tree,
        "patch_hash": patch_fingerprint.hexdigest(),
        "index_matches_head": intended_tree_hash == head_tree,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
