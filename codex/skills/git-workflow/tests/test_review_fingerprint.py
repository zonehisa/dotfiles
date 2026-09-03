from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/review_fingerprint.py"


class ReviewFingerprintTest(unittest.TestCase):
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

    def legacy_artifact_hash(self, repo: Path, base: str = "HEAD") -> str:
        base_commit = self.run_git(repo, "rev-parse", base)
        head_commit = self.run_git(repo, "rev-parse", "HEAD")
        tracked_patch = self.run_git_bytes(repo, "diff", "--binary", "HEAD", "--")
        submodule_status = self.run_git_bytes(repo, "submodule", "status", "--recursive")
        untracked_output = self.run_git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z")
        untracked_paths = sorted(path for path in untracked_output.split(b"\0") if path)
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
        return fingerprint.hexdigest()

    def fingerprint(self, repo: Path, *args: str, base: str = "HEAD") -> dict[str, object]:
        result = subprocess.run(
            ["python3", str(SCRIPT), "--repo", str(repo), "--base", base, *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def fingerprint_process(
        self,
        repo: Path,
        *args: str,
        base: str = "HEAD",
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), "--repo", str(repo), "--base", base, *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_equal_base_trees_and_patches_can_reuse_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")

            (repo / "tracked.txt").write_text("after\n")
            self.run_git(repo, "add", "tracked.txt")
            reviewed = self.fingerprint(repo)

            self.run_git(repo, "restore", "--staged", "--worktree", "tracked.txt")
            self.run_git(repo, "commit", "--allow-empty", "-qm", "tree-equivalent base")
            (repo / "tracked.txt").write_text("after\n")
            self.run_git(repo, "add", "tracked.txt")
            transferred = self.fingerprint(repo)

            # Commit metadata is deliberately outside the path fingerprint.
            self.assertEqual(reviewed["artifact_hash"], transferred["artifact_hash"])
            self.assertEqual(reviewed["patch_base_tree"], transferred["patch_base_tree"])
            self.assertEqual(reviewed["patch_hash"], transferred["patch_hash"])
            self.assertEqual(reviewed["head_tree"], transferred["head_tree"])

    def test_patch_base_recovers_reviewed_patch_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            base = self.run_git(repo, "rev-parse", "HEAD")

            (repo / "tracked.txt").write_text("after\n")
            self.run_git(repo, "add", "tracked.txt")
            reviewed = self.fingerprint(repo)
            self.run_git(repo, "commit", "-qm", "change")
            committed = self.fingerprint(repo, "--patch-base", base)

            self.assertEqual(reviewed["patch_base_tree"], committed["patch_base_tree"])
            self.assertEqual(reviewed["patch_hash"], committed["patch_hash"])
            self.assertTrue(committed["index_matches_head"])

    def test_staged_file_keeps_review_evidence_when_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            base = self.run_git(repo, "rev-parse", "HEAD")

            (repo / "added.txt").write_text("new\n")
            self.run_git(repo, "add", "added.txt")
            reviewed = self.fingerprint(repo)

            self.run_git(repo, "commit", "-qm", "add file")
            committed = self.fingerprint(repo, "--patch-base", base)

            self.assertEqual(reviewed["patch_base_tree"], committed["patch_base_tree"])
            self.assertEqual(reviewed["patch_hash"], committed["patch_hash"])
            self.assertTrue(committed["index_matches_head"])

    def test_artifact_hash_uses_changed_path_blobs_and_ignores_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            (repo / "tracked.txt").write_text("after\n")
            (repo / "untracked.txt").write_text("new\n")
            self.run_git(repo, "add", "tracked.txt", "untracked.txt")

            measured = self.fingerprint(repo)

            self.assertNotEqual(self.legacy_artifact_hash(repo), measured["artifact_hash"])
            self.assertEqual(measured["fingerprint_scope"], "changed-paths-blob-mode")
            self.assertEqual([entry["path"] for entry in measured["changed_paths"]], ["tracked.txt", "untracked.txt"])

            (repo / "unrelated.log").write_text("ignored by the staged target\n")
            unchanged = self.fingerprint(repo)
            self.assertEqual(measured["path_fingerprint"], unchanged["path_fingerprint"])

            before_mode = measured["changed_paths"][0]["after"]["mode"]
            self.assertEqual(before_mode, "100644")

    @unittest.skipIf(os.name == "nt", "Git executable-bit behavior is POSIX-specific")
    def test_owner_execute_bit_changes_patch_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            script = repo / "script.sh"
            script.write_text("#!/bin/sh\n")
            script.chmod(0o645)
            self.run_git(repo, "add", "script.sh")
            not_executable = self.fingerprint(repo)

            script.chmod(0o744)
            self.run_git(repo, "add", "script.sh")
            executable = self.fingerprint(repo)

            self.assertNotEqual(not_executable["patch_hash"], executable["patch_hash"])
            self.assertNotEqual(not_executable["content_hash"], executable["content_hash"])

    def test_file_to_directory_replacement_survives_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            entry = repo / "entry"
            entry.write_text("file\n")
            self.run_git(repo, "add", "entry")
            self.run_git(repo, "commit", "-qm", "initial")
            base = self.run_git(repo, "rev-parse", "HEAD")

            entry.unlink()
            entry.mkdir()
            (entry / "nested.txt").write_text("nested\n")
            self.run_git(repo, "add", "-A")
            reviewed = self.fingerprint(repo)
            self.run_git(repo, "commit", "-qm", "replace file with directory")
            committed = self.fingerprint(repo, "--patch-base", base, "--content-base", base)

            self.assertEqual(reviewed["patch_hash"], committed["patch_hash"])
            self.assertEqual(reviewed["content_hash"], committed["content_hash"])

    def test_submodule_update_survives_stage_and_commit(self) -> None:
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
            reviewed = self.fingerprint(repo)

            staged = self.fingerprint(repo)
            self.assertEqual(reviewed["patch_hash"], staged["patch_hash"])
            self.assertEqual(reviewed["content_hash"], staged["content_hash"])

            self.run_git(repo, "commit", "-qm", "update submodule")
            committed = self.fingerprint(repo, "--patch-base", base, "--content-base", base)
            self.assertEqual(reviewed["patch_hash"], committed["patch_hash"])
            self.assertEqual(reviewed["content_hash"], committed["content_hash"])

    def test_changed_target_base_invalidates_patch_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            self.run_git(repo, "branch", "target")

            (repo / "tracked.txt").write_text("topic\n")
            self.run_git(repo, "add", "tracked.txt")
            reviewed = self.fingerprint(repo, base="target")

            self.run_git(repo, "restore", "tracked.txt")
            self.run_git(repo, "switch", "-qc", "target-update", "target")
            (repo / "tracked.txt").write_text("new target\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "move target")
            moved_target = self.run_git(repo, "rev-parse", "HEAD")
            self.run_git(repo, "switch", "-q", "main")
            self.run_git(repo, "branch", "-f", "target", moved_target)
            (repo / "tracked.txt").write_text("topic\n")
            self.run_git(repo, "add", "tracked.txt")
            transferred = self.fingerprint(repo, base="target")

            self.assertNotEqual(reviewed["patch_base_tree"], transferred["patch_base_tree"])
            self.assertNotEqual(reviewed["patch_hash"], transferred["patch_hash"])

    def test_patch_evidence_uses_only_the_staged_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")

            (repo / "tracked.txt").write_text("after\n")
            (repo / "untracked.txt").write_text("new\n")
            unstaged = self.fingerprint(repo)
            self.assertTrue(unstaged["index_matches_head"])

            self.run_git(repo, "add", "tracked.txt")
            staged = self.fingerprint(repo)
            self.assertFalse(staged["index_matches_head"])
            self.assertNotEqual(unstaged["patch_hash"], staged["patch_hash"])

            self.run_git(repo, "add", "untracked.txt")
            fully_staged = self.fingerprint(repo)
            self.assertNotEqual(staged["patch_hash"], fully_staged["patch_hash"])

    def test_fingerprint_does_not_execute_clean_filter_or_modify_real_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            marker = repo / "filter-ran"
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            self.run_git(repo, "config", "filter.side.clean", f"sh -c 'touch {marker}; cat'")
            (repo / ".gitattributes").write_text("*.filtered filter=side\n")
            (repo / "tracked.filtered").write_text("before\n")
            self.run_git(repo, "add", ".gitattributes", "tracked.filtered")
            self.run_git(repo, "commit", "-qm", "initial")

            (repo / "tracked.filtered").write_text("after\n")
            self.run_git(repo, "add", "tracked.filtered")
            marker.unlink(missing_ok=True)
            raw_index = Path(self.run_git(repo, "rev-parse", "--git-path", "index"))
            index = raw_index if raw_index.is_absolute() else repo / raw_index
            before = index.read_bytes()
            before_mtime = index.stat().st_mtime_ns

            self.fingerprint(repo)

            self.assertFalse(marker.exists())
            self.assertEqual(before, index.read_bytes())
            self.assertEqual(before_mtime, index.stat().st_mtime_ns)

    def test_repo_local_tmpdir_does_not_enter_patch_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("before\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            (repo / "tracked.txt").write_text("after\n")
            self.run_git(repo, "add", "tracked.txt")
            expected = self.fingerprint(repo)
            local_tmp = repo / "tmp"
            (repo / ".git/info/exclude").write_text("tmp/\n")
            local_tmp.mkdir()
            env = os.environ.copy()
            env["TMPDIR"] = str(local_tmp)

            result = self.fingerprint_process(repo, env=env)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(expected, json.loads(result.stdout))
            self.assertFalse(any(path.name.startswith("review-fingerprint-") for path in local_tmp.iterdir()))

    def test_intent_to_add_entry_is_rejected_until_fully_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.run_git(repo, "init", "-q", "-b", "main")
            self.run_git(repo, "config", "user.name", "Workflow Test")
            self.run_git(repo, "config", "user.email", "workflow@example.invalid")
            (repo / "tracked.txt").write_text("tracked\n")
            self.run_git(repo, "add", "tracked.txt")
            self.run_git(repo, "commit", "-qm", "initial")
            (repo / "candidate.txt").write_text("candidate\n")
            self.run_git(repo, "add", "-N", "candidate.txt")

            rejected = self.fingerprint_process(repo)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("intent-to-add", rejected.stderr)

            self.run_git(repo, "add", "candidate.txt")
            accepted = self.fingerprint(repo)
            self.assertFalse(accepted["index_matches_head"])

    def test_dirty_submodule_requires_separate_review(self) -> None:
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
            submodule = repo / "modules/sample"
            (submodule / "version.txt").write_text("dirty\n")

            result = self.fingerprint_process(repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dirty submodule requires separate review", result.stderr)

    def test_submodule_head_must_match_the_parent_index_gitlink(self) -> None:
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
            (source / "version.txt").write_text("two\n")
            self.run_git(source, "add", "version.txt")
            self.run_git(source, "commit", "-qm", "version two")
            source_head = self.run_git(source, "rev-parse", "HEAD")
            submodule = repo / "modules/sample"
            self.run_git(submodule, "fetch", "-q", "origin")
            self.run_git(submodule, "checkout", "-q", source_head)

            self.assertEqual("", self.run_git(submodule, "status", "--short"))
            result = self.fingerprint_process(repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("submodule HEAD does not match its staged gitlink", result.stderr)

    def test_touched_clean_submodule_is_accepted(self) -> None:
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
            submodule = repo / "modules/sample"
            tracked = submodule / "version.txt"
            stat = tracked.stat()
            os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

            status_env = os.environ.copy()
            status_env["GIT_OPTIONAL_LOCKS"] = "0"
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=submodule,
                check=True,
                capture_output=True,
                text=True,
                env=status_env,
            )
            self.assertEqual("", status.stdout)
            result = self.fingerprint_process(repo)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_filtered_submodule_fails_closed_without_executing_clean_filter(self) -> None:
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
            (source / ".gitattributes").write_text("*.filtered filter=side\n")
            (source / "tracked.filtered").write_text("before\n")
            self.run_git(source, "add", ".gitattributes", "tracked.filtered")
            self.run_git(source, "commit", "-qm", "filtered source")
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
            submodule = repo / "modules/sample"
            marker = submodule / "clean-filter-ran"
            self.run_git(
                submodule,
                "config",
                "filter.side.clean",
                f"sh -c 'touch {marker}; sed \"s/^smudged://\"'",
            )
            marker.unlink(missing_ok=True)
            tracked = submodule / "tracked.filtered"
            tracked.write_text("smudged:before\n")
            self.assertEqual("smudged:before\n", tracked.read_text())

            result = self.fingerprint_process(repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot be verified without executing its clean filter", result.stderr)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
