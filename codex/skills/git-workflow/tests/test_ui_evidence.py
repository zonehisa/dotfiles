from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ui_evidence.py"
SPEC = importlib.util.spec_from_file_location("ui_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ui_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui_evidence)


class UIEvidenceTest(unittest.TestCase):
    def git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def make_repo(self, directory: str) -> Path:
        repo = Path(directory)
        self.git(repo, "init", "-q", "-b", "main")
        self.git(repo, "config", "user.name", "UI Evidence Test")
        self.git(repo, "config", "user.email", "ui-evidence@example.invalid")
        return repo

    def packet(self, source_fingerprint: str | None = None) -> dict[str, object]:
        return {
            "schema_version": 1,
            "checkpoint_token": "ui-checkpoint-1",
            "checkpoint_scope": ["resources/app.css", "resources/app.js"],
            "accepted_source_fingerprint": source_fingerprint or "a" * 64,
            "browser_executor": "coordinator/main",
            "selector": "iab",
            "browser_family": "iab",
            "automatic_fallback": False,
            "checked_url": "http://localhost:3000/settings",
            "primary_flow_view": "settings form submit",
            "viewport": {"height": 900, "width": 1440},
            "result": "pass",
            "evidence_artifacts": [
                {"id": "iab-screenshot-1", "sha256": "b" * 64},
            ],
        }

    def test_source_fingerprint_is_deterministic_and_ignores_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            css = repo / "resources/app.css"
            css.parent.mkdir()
            css.write_text("body { color: black; }\n")
            self.git(repo, "add", "resources/app.css")
            before_fingerprint_index = (repo / ".git/index").read_bytes()
            first = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            packet = self.packet(first)
            packet["checkpoint_scope"] = ["resources/app.css"]
            first_material_hash = ui_evidence.material_packet_hash(packet)
            self.assertEqual(before_fingerprint_index, (repo / ".git/index").read_bytes())
            before_index = (repo / ".git/index").read_bytes()
            (repo / "unrelated.txt").write_text("staged only\n")
            self.git(repo, "add", "unrelated.txt")
            before_second_fingerprint_index = (repo / ".git/index").read_bytes()
            second = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            second_material_hash = ui_evidence.material_packet_hash(packet)

            self.assertEqual(first, second)
            self.assertEqual(first_material_hash, second_material_hash)
            self.assertEqual(
                before_second_fingerprint_index,
                (repo / ".git/index").read_bytes(),
            )
            self.assertNotEqual(before_index, (repo / ".git/index").read_bytes())

    def test_source_records_expose_only_changed_path_blob_and_git_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            path = repo / "resources/app.css"
            path.parent.mkdir()
            content = b"body {}\n"
            path.write_bytes(content)

            records = ui_evidence.source_records(repo, ["resources/app.css"])

            self.assertEqual(
                records,
                [
                    {
                        "blob": hashlib.sha256(content).hexdigest(),
                        "mode": "100644",
                        "path": "resources/app.css",
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "type": "file",
                    }
                ],
            )
            canonical = [
                {key: record[key] for key in ("blob", "mode", "path", "type")}
                for record in records
            ]
            self.assertEqual(
                ui_evidence.source_fingerprint(repo, ["resources/app.css"]),
                hashlib.sha256(ui_evidence.canonical_json_bytes(canonical)).hexdigest(),
            )

    def test_scoped_stage_then_unstage_does_not_change_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            css = repo / "resources/app.css"
            css.parent.mkdir()
            css.write_text("body { color: black; }\n")
            self.git(repo, "add", "resources/app.css")
            self.git(repo, "commit", "-qm", "initial")

            css.write_text("body { color: white; }\n")
            before_stage = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            self.git(repo, "add", "resources/app.css")
            after_stage = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            self.git(repo, "restore", "--staged", "--", "resources/app.css")
            after_unstage = ui_evidence.source_fingerprint(repo, ["resources/app.css"])

            self.assertEqual(before_stage, after_stage)
            self.assertEqual(after_stage, after_unstage)

    @unittest.skipIf(os.name == "nt", "symlink behavior is POSIX-specific")
    def test_regular_file_to_symlink_and_symlink_target_changes_invalidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            assets = repo / "assets"
            assets.mkdir()
            current = assets / "current.css"
            current.write_text(".app {}\n")
            regular = ui_evidence.source_fingerprint(repo, ["assets/current.css"])

            (assets / "target-a.css").write_text(".a {}\n")
            (assets / "target-b.css").write_text(".b {}\n")
            current.unlink()
            current.symlink_to("target-a.css")
            target_a = ui_evidence.source_fingerprint(repo, ["assets/current.css"])
            current.unlink()
            current.symlink_to("target-b.css")
            target_b = ui_evidence.source_fingerprint(repo, ["assets/current.css"])

            self.assertNotEqual(regular, target_a)
            self.assertNotEqual(target_a, target_b)

    def test_scoped_deletion_fails_closed_and_invalidates_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            app = repo / "resources/app.js"
            app.parent.mkdir()
            app.write_text("console.log('ok');\n")
            before_deletion = ui_evidence.source_fingerprint(repo, ["resources/app.js"])
            app.unlink()

            with self.assertRaises(ui_evidence.UIEvidenceError):
                ui_evidence.source_fingerprint(repo, ["resources/app.js"])
            self.assertEqual(len(before_deletion), 64)

    def test_out_of_scope_working_tree_mutation_does_not_change_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            scoped = repo / "resources/app.css"
            scoped.parent.mkdir()
            scoped.write_text("body {}\n")
            unrelated = repo / "docs/notes.txt"
            unrelated.parent.mkdir()
            unrelated.write_text("before\n")

            before_mutation = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            unrelated.write_text("after\n")
            after_mutation = ui_evidence.source_fingerprint(repo, ["resources/app.css"])

            self.assertEqual(before_mutation, after_mutation)

    def test_source_fingerprint_changes_for_content_and_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            script = repo / "bin/run.sh"
            script.parent.mkdir()
            script.write_text("#!/bin/sh\n")
            script.chmod(0o644)
            plain = ui_evidence.source_fingerprint(repo, ["bin/run.sh"])

            script.chmod(0o755)
            executable = ui_evidence.source_fingerprint(repo, ["bin/run.sh"])
            self.assertEqual(ui_evidence.source_records(repo, ["bin/run.sh"])[0]["mode"], "100755")
            script.write_text("#!/bin/sh\necho changed\n")
            changed = ui_evidence.source_fingerprint(repo, ["bin/run.sh"])

            self.assertNotEqual(plain, executable)
            self.assertNotEqual(executable, changed)

    @unittest.skipIf(os.name == "nt", "symlink behavior is POSIX-specific")
    def test_symlink_target_is_recorded_and_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            target = repo / "assets/target.css"
            target.parent.mkdir()
            target.write_text(".app {}\n")
            link = repo / "assets/current.css"
            link.symlink_to("target.css")

            records = ui_evidence.source_records(repo, ["assets/current.css"])
            self.assertEqual(records[0]["type"], "symlink")
            self.assertEqual(records[0]["target"], "target.css")

            link.unlink()
            link.symlink_to(Path(directory).parent / "outside.css")
            with self.assertRaises(ValueError):
                ui_evidence.source_fingerprint(repo, ["assets/current.css"])

    def test_scope_rejects_duplicates_absolute_parent_and_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            (repo / "app.js").write_text("console.log('ok');\n")

            for scope in (
                ["app.js", "app.js"],
                [str(repo / "app.js")],
                ["../app.js"],
                ["C:relative.js"],
                ["C:/absolute.js"],
                [r"\\server\share\app.js"],
                ["nested/.git/config"],
                ["missing.js"],
            ):
                with self.subTest(scope=scope), self.assertRaises(ValueError):
                    ui_evidence.source_fingerprint(repo, scope)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO support is unavailable")
    def test_special_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            fifo = repo / "named.pipe"
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                ui_evidence.source_fingerprint(repo, ["named.pipe"])

    def test_material_packet_hash_is_canonical_and_metadata_is_non_material(self) -> None:
        packet = self.packet()
        packet["checkpoint_scope"] = ["resources/app.js", "resources/app.css"]
        validated = ui_evidence.validate_material_packet(packet)
        material_hash = ui_evidence.material_packet_hash(packet)
        self.assertEqual(validated["checkpoint_scope"], ["resources/app.css", "resources/app.js"])
        self.assertEqual(
            material_hash,
            hashlib.sha256(ui_evidence.canonical_json_bytes(validated)).hexdigest(),
        )
        self.assertEqual(
            material_hash,
            ui_evidence.material_packet_hash(
                packet,
                metadata={"generated_at": "2026-09-01T00:00:00Z", "generator_version": "1"},
            ),
        )
        changed_result = json.loads(json.dumps(packet))
        changed_result["result"] = "changed"
        self.assertNotEqual(material_hash, ui_evidence.material_packet_hash(changed_result))
        changed_artifact = json.loads(json.dumps(packet))
        changed_artifact["evidence_artifacts"][0]["sha256"] = "c" * 64
        self.assertNotEqual(material_hash, ui_evidence.material_packet_hash(changed_artifact))

    def test_metadata_cannot_smuggle_material_fields(self) -> None:
        packet = self.packet()
        with self.assertRaises(ValueError):
            ui_evidence.validate_metadata(
                {"generated_at": "now", "checkpoint_scope": ["other.js"]}
            )
        packet["metadata"] = {"generated_at": "now"}
        with self.assertRaises(ValueError):
            ui_evidence.validate_material_packet(packet)

    def test_material_packet_rejects_scope_selector_artifact_and_fallback_errors(self) -> None:
        for mutate in (
            lambda packet: packet.update({"schema_version": 1.0}),
            lambda packet: packet.update({"checkpoint_scope": ["app.js", "app.js"]}),
            lambda packet: packet.update({"selector": "chrome"}),
            lambda packet: packet.update({"browser_family": "chrome"}),
            lambda packet: packet.update({"automatic_fallback": True}),
            lambda packet: packet.update({"evidence_artifacts": [{"id": "one", "sha256": "x"}]}),
            lambda packet: packet.update({"unexpected": "material"}),
        ):
            with self.subTest(mutate=mutate):
                packet = self.packet()
                mutate(packet)
                with self.assertRaises(ValueError):
                    ui_evidence.validate_material_packet(packet)

    def test_material_packet_source_fingerprint_can_be_built_from_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            css = repo / "resources/app.css"
            css.parent.mkdir()
            css.write_text("body {}\n")
            source_hash = ui_evidence.source_fingerprint(repo, ["resources/app.css"])
            packet = self.packet(source_hash)
            packet["checkpoint_scope"] = ["resources/app.css"]

            self.assertEqual(
                ui_evidence.material_packet_hash(packet),
                ui_evidence.material_packet_hash(
                    json.loads(json.dumps(packet, sort_keys=True))
                ),
            )

            index_path = repo / ".git/index"
            before_index = index_path.read_bytes() if index_path.exists() else None
            ui_evidence.validate_material_packet(packet, repo=repo)
            after_index = index_path.read_bytes() if index_path.exists() else None
            self.assertEqual(before_index, after_index)

            css.write_text("body { color: red; }\n")
            with self.assertRaises(ValueError):
                ui_evidence.validate_material_packet(packet, repo=repo)

    def test_packet_hash_cli_rejects_stale_source_fingerprint_with_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(directory)
            resources = repo / "resources"
            resources.mkdir()
            (resources / "app.css").write_text("body {}\n")
            (resources / "app.js").write_text("console.log('ok');\n")
            packet_path = repo / "packet.json"
            packet_path.write_text(json.dumps(self.packet()))

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "packet-hash",
                    "--packet",
                    str(packet_path),
                    "--repo",
                    str(repo),
                ],
                cwd=repo,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("accepted_source_fingerprint", result.stderr)


if __name__ == "__main__":
    unittest.main()
