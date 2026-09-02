from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/external_pr_snapshot.py"


class ExternalPrSnapshotTest(unittest.TestCase):
    def run_git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def run_git_bytes(self, repo: Path, *args: str) -> bytes:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        return result.stdout

    def init_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        self.run_git(repo, "init", "-q", "-b", "main")
        self.run_git(repo, "config", "user.name", "Workflow Test")
        self.run_git(repo, "config", "user.email", "workflow@example.invalid")
        return repo

    def snapshot(
        self,
        repo: Path,
        pr_number: str,
        base_sha: str,
        head_sha: str,
        *extra: str,
    ) -> dict[str, object]:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--repo",
                str(repo),
                "--pr-number",
                pr_number,
                "--base-sha",
                base_sha,
                "--head-sha",
                head_sha,
                *extra,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def snapshot_process(
        self,
        repo: Path,
        pr_number: str,
        base_sha: str,
        head_sha: str,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--repo",
                str(repo),
                "--pr-number",
                pr_number,
                "--base-sha",
                base_sha,
                "--head-sha",
                head_sha,
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_snapshot_binds_exact_objects_and_is_read_only_with_advanced_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.init_repo(Path(directory))
            (repo / "shared.txt").write_text("base\n")
            self.run_git(repo, "add", "shared.txt")
            self.run_git(repo, "commit", "-qm", "base")
            common = self.run_git(repo, "rev-parse", "HEAD")

            self.run_git(repo, "switch", "-q", "-c", "feature")
            (repo / "feature.txt").write_text("feature\n")
            self.run_git(repo, "add", "feature.txt")
            self.run_git(repo, "commit", "-qm", "feature")
            head = self.run_git(repo, "rev-parse", "HEAD")

            self.run_git(repo, "switch", "-q", "main")
            (repo / "base-only.txt").write_text("advanced base\n")
            self.run_git(repo, "add", "base-only.txt")
            self.run_git(repo, "commit", "-qm", "advance base")
            advanced_base = self.run_git(repo, "rev-parse", "HEAD")

            # External review must ignore both the worktree and the index.
            (repo / "shared.txt").write_text("dirty worktree\n")
            (repo / "staged.txt").write_text("staged\n")
            self.run_git(repo, "add", "staged.txt")
            status_before = self.run_git(repo, "status", "--porcelain=v1")
            raw_index_path = Path(self.run_git(repo, "rev-parse", "--git-path", "index"))
            index_path = raw_index_path if raw_index_path.is_absolute() else repo / raw_index_path
            index_before = index_path.read_bytes()

            measured = self.snapshot(repo, "42", advanced_base, head)
            self.assertEqual(measured["pr_number"], 42)
            self.assertEqual(measured["base_sha"], advanced_base)
            self.assertEqual(measured["head_sha"], head)
            self.assertEqual(measured["merge_base"], common)
            self.assertEqual(measured["changed_paths"], ["feature.txt"])
            self.assertRegex(str(measured["patch_hash"]), r"^[0-9a-f]{64}$")
            self.assertNotEqual(advanced_base, head)
            self.assertEqual(status_before, self.run_git(repo, "status", "--porcelain=v1"))
            self.assertEqual(index_before, index_path.read_bytes())

            (repo / "unrelated.txt").write_text("new untracked file\n")
            repeated = self.snapshot(repo, "42", advanced_base, head)
            self.assertEqual(measured, repeated)

    def test_snapshot_patch_hash_ignores_dirty_worktree_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.init_repo(Path(directory))
            (repo / ".gitattributes").write_text("# committed attributes\n")
            (repo / "file.txt").write_text("before\n")
            self.run_git(repo, "add", "-A")
            self.run_git(repo, "commit", "-qm", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            (repo / "file.txt").write_text("after\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "head")
            head = self.run_git(repo, "rev-parse", "HEAD")

            clean = self.snapshot(repo, "43", base, head)
            (repo / ".gitattributes").write_text("*.txt binary\n")
            dirty = self.snapshot(repo, "43", base, head)

            self.assertEqual(clean, dirty)

    def test_snapshot_includes_gitlink_updates_when_submodules_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            repo = root / "repo"
            source.mkdir()
            repo.mkdir()
            for target in (source, repo):
                self.run_git(target, "init", "-q", "-b", "main")
                self.run_git(target, "config", "user.name", "Workflow Test")
                self.run_git(target, "config", "user.email", "workflow@example.invalid")

            (source / "version.txt").write_text("one\n")
            self.run_git(source, "add", "version.txt")
            self.run_git(source, "commit", "-qm", "version one")
            (repo / "tracked.txt").write_text("parent\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            self.run_git(
                repo,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "-q",
                str(source),
                "modules/sample",
            )
            self.run_git(repo, "commit", "-qam", "add submodule")
            base = self.run_git(repo, "rev-parse", "HEAD")

            (source / "version.txt").write_text("two\n")
            self.run_git(source, "add", "version.txt")
            self.run_git(source, "commit", "-qm", "version two")
            source_head = self.run_git(source, "rev-parse", "HEAD")
            submodule = repo / "modules/sample"
            self.run_git(submodule, "fetch", "-q", "origin")
            self.run_git(submodule, "checkout", "-q", source_head)
            self.run_git(repo, "add", "modules/sample")
            self.run_git(repo, "commit", "-qm", "update submodule")
            head = self.run_git(repo, "rev-parse", "HEAD")

            clean = self.snapshot(repo, "44", base, head)
            self.assertEqual(clean["changed_paths"], ["modules/sample"])
            (submodule / "version.txt").write_text("dirty nested worktree\n")
            self.run_git(repo, "config", "diff.ignoreSubmodules", "all")
            self.run_git(repo, "config", "submodule.modules/sample.ignore", "all")
            ignored = self.snapshot(repo, "44", base, head)

            self.assertEqual(clean, ignored)

    def test_changed_paths_are_sorted_and_patch_hash_covers_rename_delete_and_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.init_repo(Path(directory))
            for name, contents in {
                "rename-me.txt": b"rename\n",
                "delete-me.txt": b"delete\n",
                "binary.bin": b"\x00\x01before\xff",
            }.items():
                (repo / name).write_bytes(contents)
            self.run_git(repo, "add", "-A")
            self.run_git(repo, "commit", "-qm", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")

            self.run_git(repo, "mv", "rename-me.txt", "renamed.txt")
            (repo / "delete-me.txt").unlink()
            (repo / "binary.bin").write_bytes(b"\x00\x01after\xfe")
            self.run_git(repo, "add", "-A")
            self.run_git(repo, "commit", "-qm", "changes")
            head = self.run_git(repo, "rev-parse", "HEAD")

            measured = self.snapshot(repo, "7", base, head)
            self.assertEqual(
                measured["changed_paths"],
                ["binary.bin", "delete-me.txt", "rename-me.txt", "renamed.txt"],
            )
            self.assertEqual(measured["changed_paths"], sorted(measured["changed_paths"]))
            base_tree = self.run_git(repo, "rev-parse", f"{base}^{{tree}}")
            head_tree = self.run_git(repo, "rev-parse", f"{head}^{{tree}}")
            self.assertEqual(
                measured["diff_sha256"],
                hashlib.sha256(self.run_git_bytes(
                    repo,
                    "-c",
                    "core.quotePath=true",
                    "-c",
                    "diff.algorithm=myers",
                    "diff-tree",
                    "--raw",
                    "-z",
                    "--full-index",
                    "--abbrev=40",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--no-renames",
                    "--no-color",
                    "--no-indent-heuristic",
                    "--submodule=short",
                    "--diff-algorithm=myers",
                    "-O/dev/null",
                    "-r",
                    base_tree,
                    head_tree,
                    "--",
                )).hexdigest(),
            )

    def test_snapshot_rejects_invalid_or_unrelated_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.init_repo(Path(directory))
            (repo / "file.txt").write_text("one\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")
            (repo / "file.txt").write_text("two\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "head")
            head = self.run_git(repo, "rev-parse", "HEAD")
            blob = self.run_git(repo, "rev-parse", f"{head}:file.txt")

            for args, message in (
                (("0", base, head), "positive"),
                (("1", "not-a-sha", head), "sha"),
                (("1", blob, head), "commit"),
            ):
                result = self.snapshot_process(repo, args[0], args[1], args[2])
                self.assertNotEqual(result.returncode, 0, message)

            unrelated_tree = self.run_git(repo, "write-tree")
            unrelated = self.run_git(repo, "commit-tree", unrelated_tree, "-m", "unrelated")
            result = self.snapshot_process(repo, "1", base, unrelated)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("merge base", result.stderr.lower())

    def test_missing_changed_blob_fails_closed_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.init_repo(Path(directory))
            (repo / "file.txt").write_text("one\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")
            (repo / "file.txt").write_text("two\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "head")
            head = self.run_git(repo, "rev-parse", "HEAD")
            blob = self.run_git(repo, "rev-parse", f"{head}:file.txt")
            git_dir = Path(self.run_git(repo, "rev-parse", "--git-dir"))
            if not git_dir.is_absolute():
                git_dir = repo / git_dir
            object_path = git_dir / "objects" / blob[:2] / blob[2:]
            self.assertTrue(object_path.is_file())
            object_path.unlink()

            result = self.snapshot_process(repo, "2", base, head)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("object", result.stderr.lower())

    def test_expected_snapshot_validation_rejects_stale_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.init_repo(root)
            (repo / "file.txt").write_text("one\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "base")
            base = self.run_git(repo, "rev-parse", "HEAD")
            (repo / "file.txt").write_text("two\n")
            self.run_git(repo, "add", "file.txt")
            self.run_git(repo, "commit", "-qm", "head")
            head = self.run_git(repo, "rev-parse", "HEAD")
            measured = self.snapshot(repo, "1", base, head)

            expected = root / "expected.json"
            expected.write_text(json.dumps(measured, sort_keys=True) + "\n")
            validated = self.snapshot(repo, "1", base, head, "--expected", str(expected))
            self.assertEqual(validated, measured)

            stale = dict(measured)
            stale["patch_hash"] = "0" * 64
            expected.write_text(json.dumps(stale, sort_keys=True) + "\n")
            result = self.snapshot_process(repo, "1", base, head, "--expected", str(expected))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match", result.stderr)

            for key in ("schema_version", "pr_number"):
                boolean_expected = dict(measured)
                boolean_expected[key] = True
                expected.write_text(json.dumps(boolean_expected, sort_keys=True) + "\n")
                result = self.snapshot_process(repo, "1", base, head, "--expected", str(expected))
                self.assertNotEqual(result.returncode, 0, key)
                self.assertIn(key, result.stderr)

    def test_external_helper_has_no_completion_fingerprint_or_checkout_operations(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn('"diff-tree"', source)
        self.assertNotIn('        "diff",\n', source)
        self.assertIn('environment["GIT_NO_LAZY_FETCH"] = "1"', source)
        self.assertIn('"cat-file", "-t", object_id', source)
        for forbidden in (
            "review_fingerprint",
            "update-index",
            "read-tree",
            "worktree add",
            "TemporaryDirectory",
            "tempfile",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
