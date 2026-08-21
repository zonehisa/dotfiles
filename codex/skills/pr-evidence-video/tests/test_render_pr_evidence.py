#!/usr/bin/env python3
"""Contract tests for the PR evidence renderer."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_pr_evidence.py"
SPEC = importlib.util.spec_from_file_location("render_pr_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RenderEvidenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pr-evidence-test-")
        self.root = Path(self.temp.name)
        self.input_root = self.root / "recordings"
        self.output_root = self.root / "evidence"
        self.repo_root = self.root / "application"
        self.input_root.mkdir()
        self.output_root.mkdir()
        self.repo_root.mkdir()
        self.recording = self.input_root / "recording.mp4"
        self.recording.write_bytes(b"not a media file")
        self.browser_executable = self.root / "browser"
        self.browser_executable.write_bytes(b"browser")
        self.browser_executable.chmod(0o700)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def config(self):
        return {
            "schema_version": 1,
            "repo_root": str(self.repo_root),
            "allowed_input_roots": [str(self.input_root)],
            "recording": str(self.recording),
            "browser_executable": str(self.browser_executable),
            "target": {
                "repository": "OWNER/REPO",
                "pr_number": None,
                "branch": "feature/evidence",
                "head_sha": "a" * 40,
                "review_fingerprint": {"patch_base_tree": "b" * 40, "patch_hash": "c" * 64},
            },
            "decision": {
                "requires_captions": False,
                "requires_zoom": False,
                "requires_comparison": False,
            },
            "privacy": {
                "reviewed": True,
                "reviewer": "test-reviewer",
                "secrets": False,
                "personal_data": False,
                "customer_data": False,
            },
            "output": {
                "artifact": str(self.output_root / "artifact.mp4"),
                "manifest": str(self.output_root / "manifest.json"),
            },
        }

    def test_decision_truth_table(self):
        base = self.config()["decision"]
        mode, _ = MODULE.decide_mode(base)
        self.assertEqual(mode, "raw")
        for key in ("requires_captions", "requires_zoom", "requires_comparison"):
            decision = dict(base)
            decision[key] = True
            mode, _ = MODULE.decide_mode(decision)
            self.assertEqual(mode, "remotion")

    def test_missing_and_mismatched_decision_rejected(self):
        config = self.config()
        del config["decision"]["requires_zoom"]
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["decision"]["mode"] = "remotion"
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "raw"
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_url_data_and_path_escape_rejected(self):
        for value in ("https://example.invalid/recording.mp4", "data:video/mp4;base64,AAAA"):
            config = self.config()
            config["recording"] = value
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)
        config = self.config()
        config["recording"] = str(self.root / "outside.mp4")
        (self.root / "outside.mp4").write_bytes(b"x")
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["recording"] = str(self.repo_root / "inside.mp4")
        (self.repo_root / "inside.mp4").write_bytes(b"x")
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_privacy_flags_are_fail_closed(self):
        for key in ("reviewed", "secrets", "personal_data", "customer_data"):
            config = self.config()
            config["privacy"][key] = False if key == "reviewed" else True
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)
        config = self.config()
        del config["privacy"]["reviewer"]
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_repo_root_is_required_and_outputs_stay_outside_checkout(self):
        config = self.config()
        del config["repo_root"]
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

        for output_key, output_path in (
            ("artifact", self.repo_root / "inside.mp4"),
            ("manifest", self.repo_root / "inside.json"),
        ):
            config = self.config()
            config["output"][output_key] = str(output_path)
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)

    def test_force_cannot_overwrite_comparison_input(self):
        comparison = self.input_root / "comparison.mp4"
        comparison.write_bytes(b"comparison")
        config = self.config()
        config["comparison_recording"] = str(comparison)
        config["output"]["artifact"] = str(comparison)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.render(config, force=True)

    def test_target_and_fingerprint_validation(self):
        cases = [
            ("repository", "not-a-repository"),
            ("head_sha", "a" * 39),
        ]
        for key, value in cases:
            config = self.config()
            config["target"][key] = value
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)
        for key in ("patch_base_tree", "patch_hash"):
            config = self.config()
            config["target"]["review_fingerprint"][key] = ""
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)
            config = self.config()
            config["target"]["review_fingerprint"][key] = "not-hex"
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)

    def test_remotion_requirements_validate_props_and_paths(self):
        config = self.config()
        config["decision"]["requires_captions"] = True
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["decision"]["requires_zoom"] = True
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["decision"]["requires_comparison"] = True
        config["decision"]["mode"] = "remotion"
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

        comparison = self.input_root / "comparison.mov"
        comparison.write_bytes(b"comparison")
        config = self.config()
        config["decision"].update(
            {
                "requires_captions": True,
                "requires_zoom": True,
                "requires_comparison": True,
                "mode": "remotion",
            }
        )
        config["comparison_recording"] = str(comparison)
        config["captions"] = [{"text": "Saved", "startMs": 0, "endMs": 900, "confidence": 0.9}]
        config["zooms"] = [{"startMs": 200, "endMs": 800, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        self.assertEqual(validated.mode, "remotion")
        self.assertEqual(validated.comparison_recording, comparison.resolve())
        self.assertEqual(validated.captions[0]["text"], "Saved")
        self.assertEqual(validated.zooms[0]["scale"], 2.0)

    def test_remotion_annotation_ranges_and_secondary_boundary_rejected(self):
        invalid_cases = [
            ("captions", [{"text": "bad", "startMs": 10, "endMs": 10}]),
            ("captions", [{"text": "bad", "startMs": 0, "endMs": 61_000}]),
            ("zooms", [{"startMs": 0, "endMs": 100, "x": 2, "y": 0.5, "scale": 2}]),
            ("zooms", [{"startMs": 0, "endMs": 100, "x": 0.5, "y": 0.5, "scale": 5}]),
        ]
        for key, value in invalid_cases:
            config = self.config()
            config[key] = value
            with self.assertRaises(MODULE.ConfigError):
                MODULE.validate_config(config)
        outside = self.root / "outside.mov"
        outside.write_bytes(b"outside")
        config = self.config()
        config["comparison_recording"] = str(outside)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)
        config = self.config()
        config["comparison_recording"] = "https://example.invalid/comparison.mp4"
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_fixed_template_contract_files_are_local_and_pinned(self):
        template = SCRIPT.parent / "../assets/remotion-template"
        package = json.loads((template / "package.json").read_text())
        self.assertEqual(package["dependencies"]["remotion"], "4.0.506")
        self.assertEqual(package["dependencies"]["@remotion/cli"], "4.0.506")
        self.assertEqual(package["dependencies"]["@remotion/bundler"], "4.0.506")
        self.assertEqual(package["dependencies"]["@remotion/renderer"], "4.0.506")
        self.assertEqual(package["dependencies"]["react"], "18.2.0")
        self.assertEqual(package["dependencies"]["react-dom"], "18.2.0")
        self.assertEqual(package["dependencies"]["zod"], "4.4.3")
        self.assertEqual(package["devDependencies"]["typescript"], "5.4.5")
        evidence = (template / "src/EvidenceVideo.tsx").read_text()
        root = (template / "src/Root.tsx").read_text()
        self.assertIn("evidencePropsSchema", evidence)
        self.assertIn("staticFile", evidence)
        self.assertIn("muted", evidence)
        self.assertIn('id="PrEvidenceVideo"', root)
        self.assertIn("width={1280}", root)
        self.assertIn("height={720}", root)
        self.assertIn("fps={30}", root)
        self.assertTrue((template / "package-lock.json").is_file())

    def test_remotion_plan_copies_only_validated_local_assets(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-plan-") as parent:
            run_dir = Path(parent) / "run"
            with mock.patch.object(MODULE, "probe_duration", return_value=2.0):
                plan = MODULE.prepare_remotion_run(validated, run_dir)
            self.assertFalse(plan.props_path.exists())
            self.assertFalse((plan.public_dir / "primary.mp4").exists())
            MODULE.materialize_remotion_run(validated, plan, duration=2.0)
            props = json.loads(plan.props_path.read_text())
            self.assertEqual(props["primary"]["src"], "primary.mp4")
            self.assertNotIn(str(validated.recording), plan.props_path.read_text())
            self.assertTrue((plan.public_dir / "primary.mp4").is_file())
            self.assertTrue(plan.template_dir.is_dir())
            self.assertIn("npm", plan.install_command)
            self.assertIn("--no-install", plan.command)
            self.assertNotIn("--binaries-directory", plan.command)
            self.assertTrue(MODULE.is_within(plan.cache_dir, plan.run_dir))
            self.assertEqual(plan.cache_dir, plan.template_dir / ".npm-cache")
            self.assertNotIn("/proc/self/fd/", " ".join(plan.install_command))
            self.assertIn("--browser-executable", plan.command)
            self.assertTrue(plan.browser_executable.is_file())
            self.assertTrue(MODULE.is_within(plan.run_dir, Path(parent).resolve()))
        self.assertFalse(run_dir.exists())

    def test_remotion_install_finishes_before_evidence_materialization(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        events = []
        with tempfile.TemporaryDirectory(prefix="pr-evidence-order-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            self.assertFalse(plan.props_path.exists())
            self.assertFalse((plan.public_dir / "primary.mp4").exists())

            def fake_install(command, cwd=None, timeout=None, cwd_fd=None, **kwargs):
                events.append("install")
                self.assertIsNone(cwd)
                self.assertIsNotNone(cwd_fd)
                self.assertIn(".npm-cache", command)
                self.assertEqual(command[0], "/usr/bin/sandbox-exec")
                (plan.template_dir / "node_modules").mkdir(parents=True, exist_ok=True)

            with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_run_external", side_effect=fake_install
            ):
                MODULE._ensure_remotion_dependencies(plan)
            MODULE.materialize_remotion_run(validated, plan, duration=2.0, events=events)
            self.assertEqual(events, ["install", "materialize"])
            self.assertTrue((plan.public_dir / "primary.mp4").is_file())
            self.assertTrue(plan.props_path.is_file())
            self.assertTrue(plan.cache_dir.is_dir())
            self.assertTrue(MODULE.is_within(plan.cache_dir, plan.run_dir))

    def test_browser_executable_missing_fails_before_materialization(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        config["browser_executable"] = str(self.root / "missing-browser")
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-browser-missing-") as parent:
            with mock.patch.object(MODULE, "probe_duration", return_value=2.0), mock.patch.object(
                MODULE, "materialize_remotion_run"
            ) as materialize:
                with self.assertRaises(MODULE.RenderError):
                    MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            materialize.assert_not_called()

    def test_browser_executable_rejects_symlink_path(self):
        target = self.root / "browser-target"
        target.write_bytes(b"browser")
        target.chmod(0o700)
        link = self.root / "browser-link"
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        config = self.config()
        config["browser_executable"] = str(link)
        with self.assertRaises(MODULE.RenderError):
            MODULE.prepare_remotion_run(MODULE.validate_config(config), self.root / "run", duration=2.0)

    def test_open_bound_file_os_error_is_controlled_render_error(self):
        with mock.patch.object(MODULE.os, "open", side_effect=OSError("descriptor race")):
            with self.assertRaisesRegex(MODULE.RenderError, "could not open test file"):
                MODULE._open_bound_file(
                    123,
                    "recording.mp4",
                    flags=os.O_RDONLY,
                    label="test file",
                )

    def test_browser_executable_can_be_supplied_by_environment(self):
        executable = self.root / "browser"
        executable.write_bytes(b"browser")
        executable.chmod(0o700)
        config = self.config()
        del config["browser_executable"]
        validated = MODULE.validate_config(config)
        with mock.patch.dict(os.environ, {"PR_EVIDENCE_BROWSER_EXECUTABLE": str(executable)}):
            plan = MODULE.prepare_remotion_run(validated, self.root / "env-run", duration=2.0)
        self.assertEqual(plan.browser_executable, executable.resolve())

    def test_ensure_dependencies_uses_private_relative_cache_and_closes_fds(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-private-cache-") as parent:
            with mock.patch.object(MODULE, "probe_duration", return_value=2.0):
                plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run")
            seen = {}

            def fake_npm_ci(command, cwd=None, cwd_fd=None, timeout=None, pass_fds=(), **kwargs):
                seen.update(command=command, cwd=cwd, cwd_fd=cwd_fd, pass_fds=pass_fds)
                self.assertIsNone(cwd)
                self.assertIsNotNone(cwd_fd)
                self.assertIn(".npm-cache", command)
                self.assertIn(cwd_fd, pass_fds)
                self.assertEqual(len(pass_fds), 6)
                (plan.template_dir / "node_modules").mkdir(parents=True, exist_ok=True)

            with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_run_external", side_effect=fake_npm_ci
            ):
                MODULE._ensure_remotion_dependencies(plan)
            self.assertIsNone(seen["cwd"])
            self.assertTrue(MODULE.is_within(plan.cache_dir, plan.run_dir))
            self.assertEqual(seen["command"][seen["command"].index("--cache") + 1], ".npm-cache")
            self.assertEqual(seen["command"][0], "/usr/bin/sandbox-exec")
            self.assertIn(str(plan.run_dir.resolve()), " ".join(seen["command"]))
            for fd in seen["pass_fds"]:
                with self.assertRaises(OSError):
                    os.fstat(fd)

    def test_linux_bubblewrap_command_binds_disposable_run_by_fd(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-sandbox-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                with mock.patch.dict(os.environ, {"PATH": "./attacker:/tmp/attacker"}), mock.patch.object(
                    MODULE.sys, "platform", "linux"
                ), mock.patch.object(MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")), mock.patch.object(
                    MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")
                ):
                    command = MODULE._sandbox_npm_command(
                        plan,
                        ["npm", "ci"],
                        run_fd=descriptors.run_fd,
                        template_fd=descriptors.template_fd,
                        cache_fd=descriptors.cache_fd,
                        home_fd=descriptors.home_fd,
                        tmp_fd=descriptors.tmp_fd,
                    )
            finally:
                run_fd = descriptors.run_fd
                descriptors.close()

        self.assertEqual(command[0], "/usr/bin/bwrap")
        self.assertIn("--ro-bind", command)
        root_bind = command.index("--ro-bind")
        self.assertEqual(command[root_bind : root_bind + 3], ["--ro-bind", "/", "/"])
        for flag in ("--share-net", "--clearenv", "--unshare-user", "--disable-userns", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--cap-drop"):
            self.assertIn(flag, command)
        self.assertLess(command.index("--cap-drop"), root_bind)
        self.assertLess(root_bind, command.index("--proc"))
        self.assertLess(command.index("--proc"), command.index("--dev"))
        self.assertLess(command.index("--dev"), command.index("--bind-fd"))
        bind_fd_indices = [index for index, value in enumerate(command) if value == "--bind-fd"]
        self.assertEqual(len(bind_fd_indices), 5)
        self.assertEqual(command[bind_fd_indices[0] : bind_fd_indices[0] + 3], ["--bind-fd", str(run_fd), "/var/tmp"])
        self.assertEqual(command[bind_fd_indices[1] + 2], "/var/tmp/template")
        self.assertEqual(command[bind_fd_indices[2] + 2], "/var/tmp/npm-cache")
        self.assertEqual(command[bind_fd_indices[3] + 2], "/var/tmp/home")
        self.assertEqual(command[bind_fd_indices[4] + 2], "/var/tmp/tmp")
        self.assertLess(bind_fd_indices[-1], command.index("--share-net"))
        self.assertLess(command.index("--share-net"), command.index("--clearenv"))
        self.assertIn("--clearenv", command)
        self.assertIn("--bind-fd", command)
        self.assertNotIn("/proc/self/fd/", " ".join(command))
        self.assertIn("--setenv", command)
        self.assertEqual(command[command.index("--") + 1 :], ["/usr/bin/npm", "ci"])

        def env_value(name):
            index = command.index(name)
            self.assertEqual(command[index - 1], "--setenv")
            return command[index + 1]

        self.assertEqual(env_value("HOME"), "/var/tmp/home")
        self.assertEqual(env_value("TMPDIR"), "/var/tmp/tmp")
        self.assertEqual(
            env_value("PATH"),
            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        )
        self.assertEqual(env_value("NPM_CONFIG_CACHE"), "/var/tmp/npm-cache")
        self.assertEqual(env_value("npm_config_cache"), "/var/tmp/npm-cache")
        self.assertEqual(env_value("NPM_CONFIG_USERCONFIG"), "/var/tmp/home/.npmrc")
        self.assertEqual(env_value("npm_config_userconfig"), "/var/tmp/home/.npmrc")
        self.assertEqual(command[command.index("--") + 1], "/usr/bin/npm")

    def test_linux_bubblewrap_cache_fd_survives_path_swap_without_external_victim(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-cache-swap-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            victim = Path(parent) / "victim"
            victim.mkdir()
            detached_cache = Path(parent) / "detached-cache"
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                plan.cache_dir.rename(detached_cache)
                plan.cache_dir.symlink_to(victim, target_is_directory=True)
                with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                    MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
                ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")):
                    command = MODULE._sandbox_npm_command(
                        plan,
                        ["npm", "ci"],
                        run_fd=descriptors.run_fd,
                        template_fd=descriptors.template_fd,
                        cache_fd=descriptors.cache_fd,
                        home_fd=descriptors.home_fd,
                        tmp_fd=descriptors.tmp_fd,
                    )
                # A mocked child writes through the retained cache descriptor. The pathname now
                # points at an external victim, so a path-based implementation would hit it.
                marker_fd = os.open(
                    "descriptor-bound",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=descriptors.cache_fd,
                )
                try:
                    with os.fdopen(marker_fd, "wb") as cache_stream:
                        cache_stream.write(b"descriptor-bound")
                finally:
                    MODULE._close_fd(marker_fd)
            finally:
                descriptors.close()
            self.assertTrue((plan.cache_dir.parent / ".npm-cache").is_symlink())
            self.assertFalse((detached_cache / "escaped-marker").exists())
            self.assertTrue((detached_cache / "descriptor-bound").exists())
            self.assertFalse((victim / "escaped-marker").exists())
            self.assertFalse((victim / "descriptor-bound").exists())

        self.assertIn("--bind-fd", command)
        self.assertNotIn("/proc/self/fd/", " ".join(command))
        self.assertNotIn(str(victim), " ".join(command))

    def test_linux_missing_bubblewrap_fails_closed_before_materialization(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-no-sandbox-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            missing_bwrap = Path(parent) / "missing-bwrap"
            with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                MODULE, "_require_binary"
            ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")), mock.patch.object(
                MODULE, "BUBBLEWRAP_EXECUTABLE", missing_bwrap
            ):
                with self.assertRaisesRegex(MODULE.RenderError, "bubblewrap"):
                    MODULE._ensure_remotion_dependencies(plan)
            self.assertFalse((plan.public_dir / "primary.mp4").exists())

    def test_linux_bubblewrap_without_bind_fd_fails_closed(self):
        candidate = shutil.which("true")
        if candidate is None:
            self.skipTest("a local executable is needed to mock an old bubblewrap binary")
        with mock.patch.object(MODULE, "BUBBLEWRAP_EXECUTABLE", Path(candidate)), mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[candidate, "--version"], returncode=0, stdout="bubblewrap 0.10.0", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[candidate, "--help"], returncode=0, stdout="--ro-bind", stderr=""
                ),
            ],
        ):
            with self.assertRaisesRegex(MODULE.RenderError, "--bind-fd"):
                MODULE._bubblewrap_path()

    def test_linux_bubblewrap_unsafe_namespace_root_fails_closed(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-unsafe-root-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            (plan.run_dir / "home").mkdir()
            (plan.run_dir / "tmp").mkdir()
            unsafe_root = Path(parent) / "unsafe-root"
            victim_root = Path(parent) / "victim-root"
            victim_root.mkdir()
            unsafe_root.symlink_to(victim_root, target_is_directory=True)
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                with mock.patch.object(MODULE, "BUBBLEWRAP_NAMESPACE_ROOT", str(unsafe_root)), mock.patch.object(
                    MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
                ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")):
                    with self.assertRaisesRegex(MODULE.RenderError, "bubblewrap disposable mount root"):
                        MODULE._bubblewrap_npm_command(
                            plan,
                            ["npm", "ci"],
                            run_fd=descriptors.run_fd,
                            template_fd=descriptors.template_fd,
                            cache_fd=descriptors.cache_fd,
                            home_fd=descriptors.home_fd,
                            tmp_fd=descriptors.tmp_fd,
                        )
            finally:
                descriptors.close()

    def test_linux_bubblewrap_capability_probe_failure_fails_closed(self):
        candidate = shutil.which("true")
        if candidate is None:
            self.skipTest("a local executable is needed to mock a bubblewrap binary")
        with mock.patch.object(MODULE, "BUBBLEWRAP_EXECUTABLE", Path(candidate)), mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[candidate, "--version"], returncode=0, stdout="bubblewrap 0.10.0", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[candidate, "--help"], returncode=1, stdout="--bind-fd", stderr="capability probe failed"
                ),
            ],
        ):
            with self.assertRaisesRegex(MODULE.RenderError, "capability probe"):
                MODULE._bubblewrap_path()

    def test_linux_dependency_install_uses_absolute_run_cache_and_closes_fds(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-install-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            seen = {}

            def fake_install(command, cwd=None, cwd_fd=None, pass_fds=(), **kwargs):
                seen.update(command=command, cwd=cwd, cwd_fd=cwd_fd, pass_fds=pass_fds)
                (plan.template_dir / "node_modules").mkdir(parents=True, exist_ok=True)

            with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                MODULE, "_require_binary"
            ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")), mock.patch.object(
                MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
            ), mock.patch.object(
                MODULE, "_run_external", side_effect=fake_install
            ):
                MODULE._ensure_remotion_dependencies(plan)

            self.assertEqual(seen["command"][0], "/usr/bin/bwrap")
            self.assertEqual(
                seen["command"][seen["command"].index("--cache") + 1],
                "/var/tmp/npm-cache",
            )
            self.assertIsNone(seen["cwd"])
            self.assertEqual(len(seen["pass_fds"]), 6)
            for fd in seen["pass_fds"]:
                with self.assertRaises(OSError):
                    os.fstat(fd)

    def test_linux_dependency_install_uses_children_of_retained_run_fd(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-relative-fds-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            absolute_opens = []
            child_opens = []
            real_open = MODULE._open_bound_directory
            real_child_open = MODULE._open_bound_child_directory

            def track_absolute(path, **kwargs):
                if Path(path) in (plan.template_dir, plan.cache_dir):
                    absolute_opens.append(Path(path))
                return real_open(path, **kwargs)

            def track_child(parent_fd, name, **kwargs):
                child_opens.append(name)
                return real_child_open(parent_fd, name, **kwargs)

            def fake_install(command, cwd=None, cwd_fd=None, **kwargs):
                del command, cwd
                os.mkdir("node_modules", mode=0o700, dir_fd=cwd_fd)

            with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                MODULE, "_require_binary"
            ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")), mock.patch.object(
                MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
            ), mock.patch.object(
                MODULE, "_open_bound_directory", side_effect=track_absolute
            ), mock.patch.object(MODULE, "_open_bound_child_directory", side_effect=track_child), mock.patch.object(
                MODULE, "_run_external", side_effect=fake_install
            ):
                MODULE._ensure_remotion_dependencies(plan)

            self.assertEqual(absolute_opens, [])
            self.assertIn("template", child_opens)
            self.assertIn(".npm-cache", child_opens)

    def test_linux_wsl1_fails_before_dependency_materialization(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-wsl1-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)

            def fake_install(command, cwd=None, cwd_fd=None, **kwargs):
                del command, cwd, kwargs
                os.mkdir("node_modules", mode=0o700, dir_fd=cwd_fd)

            with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                MODULE, "_kernel_osrelease", return_value="4.4.0-Microsoft", create=True
            ), mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
            ), mock.patch.object(MODULE, "_run_external", side_effect=fake_install):
                with self.assertRaisesRegex(MODULE.RenderError, "WSL1"):
                    MODULE._ensure_remotion_dependencies(plan)
            self.assertFalse((plan.public_dir / "primary.mp4").exists())

    def test_linux_bubblewrap_uses_trusted_path_not_caller_path(self):
        with tempfile.TemporaryDirectory(prefix="pr-evidence-bwrap-trusted-") as parent:
            trusted = Path(parent) / "bwrap"
            trusted.write_bytes(b"trusted")
            trusted.chmod(0o700)
            malicious = Path(parent) / "malicious-bwrap"
            malicious.write_bytes(b"malicious")
            malicious.chmod(0o700)
            help_results = [
                subprocess.CompletedProcess(
                    args=[str(trusted), "--version"], returncode=0, stdout="bubblewrap 0.10.0", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[str(trusted), "--help"], returncode=0, stdout="--bind-fd", stderr=""
                ),
            ]
            with mock.patch.object(MODULE, "BUBBLEWRAP_EXECUTABLE", trusted, create=True), mock.patch.dict(
                os.environ, {"PATH": str(malicious)}
            ), mock.patch.object(MODULE.shutil, "which", return_value=str(malicious)), mock.patch.object(
                MODULE.subprocess, "run", side_effect=help_results
            ):
                self.assertEqual(MODULE._bubblewrap_path(), trusted)

    def test_linux_bubblewrap_rejects_old_version(self):
        with tempfile.TemporaryDirectory(prefix="pr-evidence-bwrap-old-") as parent:
            trusted = Path(parent) / "bwrap"
            trusted.write_bytes(b"trusted")
            trusted.chmod(0o700)
            with mock.patch.object(MODULE, "BUBBLEWRAP_EXECUTABLE", trusted, create=True), mock.patch.object(
                MODULE.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    args=[str(trusted), "--version"], returncode=0, stdout="bubblewrap 0.9.0", stderr=""
                ),
            ):
                with self.assertRaisesRegex(MODULE.RenderError, "0.10.0"):
                    MODULE._bubblewrap_path()

    def test_linux_private_run_directory_symlink_fails_closed(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-private-dir-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            victim = Path(parent) / "victim"
            victim.mkdir()
            (plan.run_dir / "home").symlink_to(victim, target_is_directory=True)
            with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                MODULE, "_require_binary"
            ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")), mock.patch.object(
                MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
            ):
                with self.assertRaisesRegex(MODULE.RenderError, "Remotion disposable HOME directory"):
                    MODULE._ensure_remotion_dependencies(plan)
            self.assertFalse((victim / "npm-cache-marker").exists())

    @unittest.skipUnless(sys.platform == "darwin", "macOS sandbox-exec is the supported npm write boundary")
    def test_npm_cache_symlink_swap_during_child_cannot_touch_victim(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-cache-child-swap-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            victim = Path(parent) / "victim"
            victim.mkdir()
            plan.cache_dir.mkdir()
            template_fd = MODULE._open_bound_directory(
                plan.template_dir, create=False, label="Remotion template directory"
            )
            cache_fd = MODULE._open_bound_directory(plan.cache_dir, create=False, label="Remotion npm cache")
            try:
                plan.cache_dir.rmdir()
                plan.cache_dir.symlink_to(victim, target_is_directory=True)
                command = MODULE._sandbox_npm_command(
                    plan,
                    [
                        "/bin/sh",
                        "-c",
                        "printf escaped > .npm-cache/escaped-marker",
                    ],
                )
                with self.assertRaises(MODULE.RenderError):
                    MODULE._run_external(
                        command,
                        cwd_fd=template_fd,
                        pass_fds=(template_fd, cache_fd),
                        timeout=10,
                    )
            finally:
                MODULE._close_fd(template_fd)
                MODULE._close_fd(cache_fd)
            self.assertFalse((victim / "escaped-marker").exists())

    def test_npm_cache_protection_fails_closed_without_supported_sandbox(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-cache-platform-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            with mock.patch.object(MODULE, "sys", mock.Mock(platform="linux")):
                with self.assertRaises(MODULE.RenderError):
                    MODULE._sandbox_npm_command(plan, ["npm", "ci"])

    def test_remotion_render_run_directory_is_cleaned_after_failure(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        captured = []
        original_prepare = MODULE.prepare_remotion_run

        def capture_prepare(validated, run_dir, **kwargs):
            plan = original_prepare(validated, run_dir, **kwargs)
            captured.append(plan.run_dir)
            return plan

        with mock.patch.object(MODULE, "prepare_remotion_run", side_effect=capture_prepare), mock.patch.object(
            MODULE, "probe_duration", return_value=2.0
        ), mock.patch.object(MODULE, "_ensure_remotion_dependencies", side_effect=MODULE.RenderError("dependency missing")):
            with self.assertRaises(MODULE.RenderError):
                MODULE.render(config)
        self.assertEqual(len(captured), 1)
        self.assertFalse(captured[0].exists())

    def test_linux_remotion_render_uses_bubblewrap_command(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        captured = {}

        def fake_materialize(_config, plan, **_kwargs):
            captured["plan"] = plan
            (plan.run_dir / "home").mkdir(exist_ok=True)
            (plan.run_dir / "tmp").mkdir(exist_ok=True)
            plan.cache_dir.mkdir(exist_ok=True)

        def fake_run(command, **_kwargs):
            captured["command"] = command
            captured["plan"].output_path.write_bytes(b"rendered")

        def fake_normalize(_source, destination, **_kwargs):
            destination.write_bytes(b"normalized")

        with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
            MODULE, "_preflight_inputs", side_effect=lambda validated: {validated.recording: 2.0}
        ), mock.patch.object(MODULE, "_ensure_remotion_dependencies"), mock.patch.object(
            MODULE, "materialize_remotion_run", side_effect=fake_materialize
        ), mock.patch.object(MODULE, "_sandbox_remotion_command", return_value=["sandboxed-remotion"]), mock.patch.object(
            MODULE, "_run_external", side_effect=fake_run
        ), mock.patch.object(MODULE, "_normalize", side_effect=fake_normalize), mock.patch.object(
            MODULE, "probe_media", return_value=MODULE.MediaInfo("h264", "yuv420p", 1280, 720, 2.0, False)
        ), mock.patch.object(MODULE, "validate_media"), mock.patch.object(
            MODULE, "_persist_artifact", return_value=(9, "a" * 64)
        ), mock.patch.object(MODULE, "_write_manifest"):
            MODULE.render(config)

        self.assertEqual(captured["command"], ["sandboxed-remotion"])

    def test_linux_remotion_bubblewrap_maps_workspace_paths(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-linux-render-command-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                    MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
                ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npx")):
                    command = MODULE._sandbox_remotion_command(
                        plan,
                        plan.command,
                        run_fd=descriptors.run_fd,
                        template_fd=descriptors.template_fd,
                        cache_fd=descriptors.cache_fd,
                        home_fd=descriptors.home_fd,
                        tmp_fd=descriptors.tmp_fd,
                    )
            finally:
                descriptors.close()

        self.assertEqual(command[command.index("--") + 1], "/usr/bin/npx")
        self.assertIn("/var/tmp/template/src/index.ts", command)
        self.assertIn("/var/tmp/remotion-output.mp4", command)
        self.assertIn("/var/tmp/props.json", command)
        self.assertNotIn(str(plan.entrypoint), command)
        self.assertNotIn(str(plan.output_path), command)
        self.assertNotIn(str(plan.props_path), command)

    def test_wsl1_rejected_for_raw_mode_before_normalization(self):
        config = self.config()
        with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
            MODULE, "_kernel_osrelease", return_value="4.19.128-microsoft-standard"
        ), mock.patch.object(
            MODULE, "_preflight_inputs", side_effect=lambda validated: {validated.recording: 2.0}
        ), mock.patch.object(
            MODULE, "_normalize"
        ) as normalize:
            with self.assertRaises(MODULE.RenderError):
                MODULE.render(config)
        normalize.assert_not_called()

    def test_linux_fixed_tool_paths_are_documented(self):
        readme = Path(__file__).resolve().parents[4] / "README.md"
        text = readme.read_text(encoding="utf-8")
        for executable in ("/usr/bin/bwrap", "/usr/bin/npm", "/usr/bin/npx"):
            self.assertIn(executable, text)

    def test_command_contract(self):
        command = MODULE.build_ffmpeg_command(Path("input.mov"), Path("output.mp4"))
        self.assertEqual(command[0], "ffmpeg")
        self.assertIn("-an", command)
        self.assertIn("-movflags", command)
        self.assertIn("+faststart", command)
        self.assertIn("yuv420p", command)
        self.assertIn("libx264", command)
        self.assertTrue(any("setparams=range=tv" in value for value in command))
        self.assertIn("-color_range", command)
        remotion = MODULE.build_remotion_command(
            Path("src/index.tsx"),
            Path("out.mp4"),
            Path("props.json"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        )
        self.assertEqual(remotion[:3], ["npx", "--no-install", "remotion"])
        self.assertNotIn("install", remotion)
        self.assertIn("--muted", remotion)
        self.assertIn("--video-bitrate", remotion)
        self.assertIn("--concurrency", remotion)
        self.assertIn("--timeout", remotion)
        self.assertIn("--overwrite", remotion)
        self.assertIn("--browser-executable", remotion)
        self.assertNotIn("--binaries-directory", remotion)
        npm_command = MODULE.build_npm_ci_command()
        self.assertEqual(npm_command[:2], ["npm", "ci"])
        self.assertIn("--cache", npm_command)
        self.assertIn("--ignore-scripts", npm_command)
        self.assertIn(".npm-cache", npm_command)
        self.assertNotIn("/tmp/", " ".join(npm_command))

    def test_preflight_rejects_oversize_before_work(self):
        huge = self.input_root / "oversize.mp4"
        with huge.open("wb") as handle:
            handle.truncate(MODULE.MAX_INPUT_BYTES + 1)
        config = self.config()
        config["recording"] = str(huge)
        output_dir = self.root / "preflight-output"
        config["output"] = {
            "artifact": str(output_dir / "artifact.mp4"),
            "manifest": str(output_dir / "manifest.json"),
        }
        with mock.patch.object(MODULE, "_run_external") as external:
            with self.assertRaises(MODULE.RenderError):
                MODULE.render(config)
        external.assert_not_called()
        self.assertFalse(output_dir.exists())

    def test_preflight_rejects_long_input_before_output_or_normalization(self):
        config = self.config()
        output_dir = self.root / "long-output"
        config["output"] = {
            "artifact": str(output_dir / "artifact.mp4"),
            "manifest": str(output_dir / "manifest.json"),
        }
        with mock.patch.object(MODULE, "probe_duration", return_value=61.0), mock.patch.object(
            MODULE, "_normalize"
        ) as normalize:
            with self.assertRaises(MODULE.RenderError):
                MODULE.render(config)
        normalize.assert_not_called()
        self.assertFalse(output_dir.exists())

    def test_preflight_checks_comparison_before_work(self):
        comparison = self.input_root / "comparison.mov"
        comparison.write_bytes(b"comparison")
        config = self.config()
        config["comparison_recording"] = str(comparison)
        output_dir = self.root / "comparison-output"
        config["output"] = {
            "artifact": str(output_dir / "artifact.mp4"),
            "manifest": str(output_dir / "manifest.json"),
        }
        with mock.patch.object(MODULE, "probe_duration", side_effect=[2.0, 61.0]) as probe:
            with self.assertRaises(MODULE.RenderError):
                MODULE.render(config)
        self.assertEqual(probe.call_count, 2)
        self.assertFalse(output_dir.exists())

    def test_source_probe_has_bounded_timeout(self):
        result = subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout=json.dumps({"format": {"duration": "2.0"}}),
            stderr="",
        )
        with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
            MODULE, "_run_external", return_value=result
        ) as run_external:
            self.assertEqual(MODULE.probe_duration(self.recording), 2.0)
        self.assertEqual(
            run_external.call_args.kwargs["timeout"],
            MODULE.INPUT_PROBE_TIMEOUT_SECONDS,
        )

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
    def test_raw_strips_input_metadata(self):
        marked = self.input_root / "marked.mp4"
        make_input = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x200:rate=15",
            "-t",
            "2",
            "-metadata",
            "comment=secret-marker",
            "-c:v",
            "libx264",
            str(marked),
        ]
        result = subprocess.run(make_input, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.skipTest("available ffmpeg lacks the test source encoder")
        config = self.config()
        config["recording"] = str(marked)
        config["output"]["artifact"] = str(self.output_root / "marked-normalized.mp4")
        config["output"]["manifest"] = str(self.output_root / "marked-normalized.json")
        MODULE.render(config)
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format_tags=comment",
                "-of",
                "json",
                config["output"]["artifact"],
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertNotIn("secret-marker", probe.stdout)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
    def test_raw_full_range_input_normalizes_to_limited_yuv420p(self):
        full_range = self.input_root / "full-range.mp4"
        make_input = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x200:rate=15",
            "-t",
            "2",
            "-vf",
            "format=yuvj420p",
            "-color_range",
            "pc",
            "-c:v",
            "libx264",
            str(full_range),
        ]
        result = subprocess.run(make_input, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.skipTest("available ffmpeg lacks full-range test encoding")
        config = self.config()
        config["recording"] = str(full_range)
        config["output"]["artifact"] = str(self.output_root / "full-range-normalized.mp4")
        config["output"]["manifest"] = str(self.output_root / "full-range-normalized.json")
        manifest = MODULE.render(config)
        self.assertEqual(manifest["artifact"]["pixel_format"], "yuv420p")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
    def test_raw_ffmpeg_smoke_and_manifest(self):
        generated = self.input_root / "generated.webm"
        make_input = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x200:rate=15",
            "-t",
            "2",
            "-c:v",
            "libvpx-vp9",
            str(generated),
        ]
        result = subprocess.run(make_input, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.skipTest("available ffmpeg lacks the test source encoder")
        config = self.config()
        config["recording"] = str(generated)
        config["output"]["artifact"] = str(self.output_root / "normalized.mp4")
        config["output"]["manifest"] = str(self.output_root / "normalized.json")
        manifest = MODULE.render(config)
        self.assertEqual(manifest["decision"]["mode"], "raw")
        self.assertEqual(manifest["artifact"]["mime"], "video/mp4")
        self.assertEqual(manifest["artifact"]["codec"], "h264")
        self.assertEqual(manifest["artifact"]["pixel_format"], "yuv420p")
        self.assertEqual(manifest["artifact"]["resolution"], {"width": 1280, "height": 720})
        self.assertFalse(manifest["artifact"]["audio"])
        artifact = Path(manifest["artifact"]["path"])
        self.assertEqual(manifest["artifact"]["sha256"], MODULE.sha256_file(artifact))
        self.assertEqual(json.loads((self.output_root / "normalized.json").read_text())["handoff"]["status"], "pending")

    def test_remotion_fails_closed_without_template(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        with self.assertRaises(MODULE.RenderError):
            MODULE.render(config)

    def test_dangling_artifact_symlink_rejected(self):
        dangling = self.output_root / "dangling.mp4"
        try:
            dangling.symlink_to(self.output_root / "missing-target.mp4")
        except OSError:
            self.skipTest("symlink creation unavailable")
        config = self.config()
        config["output"]["artifact"] = str(dangling)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_dangling_manifest_symlink_rejected(self):
        dangling = self.output_root / "dangling.json"
        try:
            dangling.symlink_to(self.output_root / "missing-manifest-target.json")
        except OSError:
            self.skipTest("symlink creation unavailable")
        config = self.config()
        config["output"]["manifest"] = str(dangling)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.validate_config(config)

    def test_manifest_writer_ignores_predictable_temp_symlink(self):
        manifest_path = self.output_root / "safe.json"
        victim = self.root / "victim.json"
        victim.write_text("keep-me\n", encoding="utf-8")
        predictable = manifest_path.with_name(manifest_path.name + ".tmp")
        try:
            predictable.symlink_to(victim)
        except OSError:
            self.skipTest("symlink creation unavailable")
        MODULE._write_manifest(manifest_path, {"status": "safe"})
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep-me\n")
        self.assertFalse(manifest_path.is_symlink())
        self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8")), {"status": "safe"})
        self.assertTrue(predictable.is_symlink())

    def test_manifest_writer_cleans_only_its_unique_temp_on_replace_failure(self):
        manifest_path = self.output_root / "replace-failure.json"
        predictable = manifest_path.with_name(manifest_path.name + ".tmp")
        predictable.write_text("pre-existing", encoding="utf-8")
        with mock.patch.object(MODULE.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(MODULE.RenderError):
                MODULE._write_manifest(manifest_path, {"status": "safe"})
        self.assertEqual(predictable.read_text(encoding="utf-8"), "pre-existing")
        self.assertEqual(list(self.output_root.iterdir()), [predictable])

    def test_artifact_persistence_uses_bound_parent_after_path_swap(self):
        normalized = self.root / "normalized.mp4"
        normalized.write_bytes(b"normalized-artifact")
        destination = self.output_root / "swapped-artifact.mp4"
        victim = self.root / "victim-artifact"
        victim.mkdir()
        original = self.root / "evidence-original"
        real_open = MODULE._open_bound_directory
        swapped = False

        def swap_after_bind(path, *, create=False, label="directory"):
            nonlocal swapped
            fd = real_open(path, create=create, label=label)
            if not swapped and path == self.output_root:
                swapped = True
                self.output_root.rename(original)
                self.output_root.symlink_to(victim, target_is_directory=True)
            return fd

        with mock.patch.object(MODULE, "_open_bound_directory", side_effect=swap_after_bind):
            MODULE._persist_artifact(normalized, destination)
        self.assertTrue((original / destination.name).is_file())
        self.assertFalse((victim / destination.name).exists())

    def test_manifest_writer_uses_bound_parent_after_path_swap(self):
        victim = self.root / "victim-manifest"
        victim.mkdir()
        original = self.root / "manifest-original"
        real_open = MODULE._open_bound_directory
        swapped = False

        def swap_after_bind(path, *, create=False, label="directory"):
            nonlocal swapped
            fd = real_open(path, create=create, label=label)
            if not swapped and path == self.output_root:
                swapped = True
                self.output_root.rename(original)
                self.output_root.symlink_to(victim, target_is_directory=True)
            return fd

        manifest_path = self.output_root / "swapped-manifest.json"
        with mock.patch.object(MODULE, "_open_bound_directory", side_effect=swap_after_bind):
            MODULE._write_manifest(manifest_path, {"status": "safe"})
        self.assertTrue((original / manifest_path.name).is_file())
        self.assertFalse((victim / manifest_path.name).exists())

    def test_npm_cache_rejects_swap_after_path_validation_without_touching_target(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-cache-swap-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            victim = Path(parent) / "victim"
            victim.mkdir()
            real_child_open = MODULE._open_bound_child_directory
            swapped = False

            def swap_cache(parent_fd, name, *, create=False, label="directory"):
                nonlocal swapped
                if not swapped and label == "Remotion npm cache":
                    swapped = True
                    plan.cache_dir.mkdir(exist_ok=True)
                    plan.cache_dir.rmdir()
                    plan.cache_dir.symlink_to(victim, target_is_directory=True)
                return real_child_open(parent_fd, name, create=create, label=label)

            with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_open_bound_child_directory", side_effect=swap_cache
            ), mock.patch.object(MODULE, "_run_external") as external:
                with self.assertRaises(MODULE.RenderError):
                    MODULE._ensure_remotion_dependencies(plan)
            external.assert_not_called()
            self.assertEqual(list(victim.iterdir()), [])

    def test_remotion_materialization_uses_prevalidated_descriptor_bundle_after_template_swap(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-materialize-swap-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            detached = Path(parent) / "detached-template"
            victim = Path(parent) / "victim-template"
            victim.mkdir()
            detached_recording = self.root / "detached-recording.mp4"
            victim_recording = self.root / "victim-recording.mp4"
            victim_recording.write_bytes(b"attacker-recording")
            descriptors = MODULE._open_remotion_descriptors(plan, input_paths=(validated.recording,))
            try:
                plan.template_dir.rename(detached)
                plan.template_dir.symlink_to(victim, target_is_directory=True)
                validated.recording.rename(detached_recording)
                validated.recording.symlink_to(victim_recording)
                MODULE.materialize_remotion_run(validated, plan, duration=2.0, descriptors=descriptors)
            finally:
                descriptors.close()
                if validated.recording.is_symlink():
                    validated.recording.unlink()
                detached_recording.rename(validated.recording)
            self.assertTrue((detached / "public" / "primary.mp4").is_file())
            self.assertFalse((victim / "public" / "primary.mp4").exists())
            self.assertEqual((detached / "public" / "primary.mp4").read_bytes(), b"not a media file")

    def test_linux_bubblewrap_binds_retained_home_and_tmp_descriptors(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-home-tmp-fds-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                with mock.patch.object(MODULE.sys, "platform", "linux"), mock.patch.object(
                    MODULE, "_bubblewrap_path", return_value=Path("/usr/bin/bwrap")
                ), mock.patch.object(MODULE, "_trusted_linux_binary", return_value=Path("/usr/bin/npm")):
                    command = MODULE._sandbox_npm_command(
                        plan,
                        ["npm", "ci"],
                        run_fd=descriptors.run_fd,
                        template_fd=descriptors.template_fd,
                        cache_fd=descriptors.cache_fd,
                        home_fd=descriptors.home_fd,
                        tmp_fd=descriptors.tmp_fd,
                    )
            finally:
                descriptors.close()
        bind_fd_indices = [index for index, value in enumerate(command) if value == "--bind-fd"]
        self.assertEqual(len(bind_fd_indices), 5)
        self.assertEqual(command[bind_fd_indices[3] + 2], "/var/tmp/home")
        self.assertEqual(command[bind_fd_indices[4] + 2], "/var/tmp/tmp")
        self.assertEqual(command[command.index("HOME") + 1], "/var/tmp/home")
        self.assertEqual(command[command.index("TMPDIR") + 1], "/var/tmp/tmp")

    def test_linux_home_and_tmp_descriptors_survive_post_validation_path_swap(self):
        config = self.config()
        config["decision"]["requires_zoom"] = True
        config["decision"]["mode"] = "remotion"
        config["zooms"] = [{"startMs": 0, "endMs": 500, "x": 0.5, "y": 0.5, "scale": 2}]
        validated = MODULE.validate_config(config)
        with tempfile.TemporaryDirectory(prefix="pr-evidence-home-tmp-swap-") as parent:
            plan = MODULE.prepare_remotion_run(validated, Path(parent) / "run", duration=2.0)
            home_detached = Path(parent) / "detached-home"
            tmp_detached = Path(parent) / "detached-tmp"
            victim = Path(parent) / "victim"
            victim.mkdir()
            descriptors = MODULE._open_remotion_descriptors(plan)
            try:
                (plan.run_dir / "home").rename(home_detached)
                (plan.run_dir / "home").symlink_to(victim, target_is_directory=True)
                (plan.run_dir / "tmp").rename(tmp_detached)
                (plan.run_dir / "tmp").symlink_to(victim, target_is_directory=True)
                for fd, name in ((descriptors.home_fd, "home-bound"), (descriptors.tmp_fd, "tmp-bound")):
                    marker_fd = os.open(
                        name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=fd,
                    )
                    MODULE._close_fd(marker_fd)
            finally:
                descriptors.close()
            self.assertTrue((home_detached / "home-bound").is_file())
            self.assertTrue((tmp_detached / "tmp-bound").is_file())
            self.assertFalse((victim / "home-bound").exists())
            self.assertFalse((victim / "tmp-bound").exists())

    def test_remotion_normalization_uses_retained_descriptors_after_run_path_swap(self):
        workspace = self.root / "normalization-workspace"
        workspace.mkdir()
        source = workspace / "remotion-output.mp4"
        source.write_bytes(b"rendered")
        destination = workspace / "normalized.mp4"
        destination_fd = os.open(
            destination,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        victim = self.root / "victim-normalized"
        victim.mkdir()
        detached = self.root / "detached-normalized"
        try:
            workspace.rename(detached)
            workspace.symlink_to(victim, target_is_directory=True)

            def fake_run(command, **kwargs):
                self.assertIn(str(MODULE._fd_path(source_fd)), command)
                self.assertIn(str(MODULE._fd_path(destination_fd)), command)
                self.assertIn(source_fd, kwargs["pass_fds"])
                self.assertIn(destination_fd, kwargs["pass_fds"])
                os.write(destination_fd, b"normalized")

            with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_run_external", side_effect=fake_run
            ), mock.patch.object(MODULE.sys, "platform", "linux"):
                MODULE._normalize(
                    source,
                    destination,
                    source_fd=source_fd,
                    destination_fd=destination_fd,
                )
        finally:
            MODULE._close_fd(source_fd)
            MODULE._close_fd(destination_fd)
            if workspace.is_symlink():
                workspace.unlink()
            detached.rename(workspace)
        self.assertEqual((workspace / "normalized.mp4").read_bytes(), b"normalized")
        self.assertFalse((victim / "normalized.mp4").exists())

if __name__ == "__main__":
    unittest.main()
