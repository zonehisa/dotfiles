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
                self.assertEqual(tuple(pass_fds), (cwd_fd, mock.ANY))
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
            real_open = MODULE._open_bound_directory
            swapped = False

            def swap_cache(path, *, create=False, label="directory"):
                nonlocal swapped
                if not swapped and label == "Remotion npm cache":
                    swapped = True
                    if path.exists():
                        path.rmdir()
                    path.symlink_to(victim, target_is_directory=True)
                return real_open(path, create=create, label=label)

            with mock.patch.object(MODULE, "_require_binary"), mock.patch.object(
                MODULE, "_open_bound_directory", side_effect=swap_cache
            ), mock.patch.object(MODULE, "_run_external") as external:
                with self.assertRaises(MODULE.RenderError):
                    MODULE._ensure_remotion_dependencies(plan)
            external.assert_not_called()
            self.assertEqual(list(victim.iterdir()), [])

if __name__ == "__main__":
    unittest.main()
