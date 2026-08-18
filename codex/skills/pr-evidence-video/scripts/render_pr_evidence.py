#!/usr/bin/env python3
"""Render a privacy-reviewed PR evidence video.

The Python code owns validation, deterministic props, manifest creation, and the boundary to
ffmpeg/ffprobe/npm/npx. It deliberately has no network or upload code. Remotion is a fixed skill
asset and is only run from an external temporary workspace when its dependencies are present.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse


SCHEMA_VERSION = 1
MAX_BYTES = 10 * 1024 * 1024
MAX_INPUT_BYTES = 512 * 1024 * 1024
MIN_DURATION = 1.0
MAX_DURATION = 60.0
FPS = 30
INPUT_PROBE_TIMEOUT_SECONDS = 30
REMOTION_INSTALL_TIMEOUT_SECONDS = 300
REMOTION_RENDER_TIMEOUT_SECONDS = 300
REMOTION_VIDEO_BITRATE = "2M"
REMOTION_CONCURRENCY = "1"
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm"}
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
REPOSITORY_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXED_TEMPLATE_SOURCE = SKILL_ROOT / "assets" / "remotion-template"


class ConfigError(ValueError):
    """Raised when the input contract is not satisfied."""


# Public alias for callers that prefer the more general name.
ValidationError = ConfigError


class RenderError(RuntimeError):
    """Raised when an external renderer or media inspection fails."""


@dataclass(frozen=True)
class ValidatedConfig:
    config: Dict[str, Any]
    base_dir: Path
    repo_root: Path
    allowed_input_roots: Tuple[Path, ...]
    recording: Path
    artifact_path: Path
    manifest_path: Path
    target: Dict[str, Any]
    decision: Dict[str, Any]
    privacy: Dict[str, Any]
    mode: str
    rationale: Any
    comparison_recording: Optional[Path]
    title: str
    labels: Dict[str, str]
    captions: List[Dict[str, Any]]
    zooms: List[Dict[str, Any]]
    comparison: Dict[str, Any]


@dataclass(frozen=True)
class MediaInfo:
    codec: str
    pixel_format: str
    width: int
    height: int
    duration: float
    audio: bool


@dataclass(frozen=True)
class RemotionPlan:
    run_dir: Path
    props_path: Path
    output_path: Path
    template_dir: Path
    entrypoint: Path
    command: Tuple[str, ...]
    install_command: Tuple[str, ...]
    cache_dir: Path
    browser_executable: Path
    public_dir: Path
    duration_in_frames: int
    repo_root: Optional[Path] = None


def is_within(path: Path, parent: Path) -> bool:
    """Return whether *path* is parent or a descendant of *parent*."""

    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _looks_like_url(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered.startswith(("http://", "https://", "data:")):
        return True
    try:
        parsed = urlparse(value)
    except ValueError:
        return True
    # A URI scheme is not a local filesystem path. This also closes ftp:, file:, and custom
    # schemes rather than relying on Path.exists() to produce an ambiguous error.
    return bool(parsed.scheme and not (len(parsed.scheme) == 1 and len(value) > 1 and value[1] == ":"))


def _local_path(value: Any, base_dir: Path, label: str) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ConfigError(f"{label} must be a non-empty local path")
    value = os.fspath(value)
    if not value.strip():
        raise ConfigError(f"{label} must be a non-empty local path")
    if "\x00" in value:
        raise ConfigError(f"{label} contains a NUL byte")
    if _looks_like_url(value):
        raise ConfigError(f"{label} must not be an URL or data URL")
    try:
        raw_path = Path(value)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{label} is not a valid local path: {exc}") from exc
    if not raw_path.is_absolute():
        raw_path = base_dir / raw_path
    try:
        return raw_path.resolve(strict=False)
    except OSError as exc:
        raise ConfigError(f"{label} cannot be resolved: {exc}") from exc


def _require_bool(mapping: Mapping[str, Any], key: str, label: str) -> bool:
    value = mapping.get(key)
    if type(value) is not bool:  # bool is intentionally not accepted through integer coercion.
        raise ConfigError(f"{label}.{key} must be a JSON boolean")
    return value


def _require_hex(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or not HEX_RE.fullmatch(value):
        raise ConfigError(f"{label} must be a non-empty hexadecimal string")
    return value


def _validate_target(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError("target must be an object")
    repository = value.get("repository")
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        raise ConfigError("target.repository must be OWNER/REPO")
    if "pr_number" not in value:
        raise ConfigError("target.pr_number is required; use null while pending")
    pr_number = value["pr_number"]
    if pr_number is not None and (type(pr_number) is not int or pr_number < 1):
        raise ConfigError("target.pr_number must be a positive integer or null")
    head_sha = value.get("head_sha")
    if not isinstance(head_sha, str) or not SHA1_RE.fullmatch(head_sha):
        raise ConfigError("target.head_sha must be exactly 40 hexadecimal characters")
    fingerprint = value.get("review_fingerprint")
    if not isinstance(fingerprint, dict):
        raise ConfigError("target.review_fingerprint must be an object")
    patch_base_tree = _require_hex(fingerprint.get("patch_base_tree"), "target.review_fingerprint.patch_base_tree")
    patch_hash = _require_hex(fingerprint.get("patch_hash"), "target.review_fingerprint.patch_hash")
    branch = value.get("branch")
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        raise ConfigError("target.branch must be a non-empty string when supplied")

    target = copy.deepcopy(value)
    target["review_fingerprint"] = {
        **copy.deepcopy(fingerprint),
        "patch_base_tree": patch_base_tree,
        "patch_hash": patch_hash,
    }
    return target


def decide_mode(decision: Mapping[str, Any], supplied_mode: Optional[str] = None) -> Tuple[str, Any]:
    """Apply the decision truth table and return ``(mode, rationale)``."""

    if not isinstance(decision, Mapping):
        raise ConfigError("decision must be an object")
    required = ("requires_captions", "requires_zoom", "requires_comparison")
    flags = {key: _require_bool(decision, key, "decision") for key in required}
    expected = "remotion" if any(flags.values()) else "raw"
    configured_modes: List[str] = []
    for label, candidate in (("decision.mode", decision.get("mode")), ("mode", supplied_mode)):
        if candidate is None:
            continue
        if not isinstance(candidate, str) or candidate not in {"raw", "remotion"}:
            raise ConfigError(f"{label} must be raw or remotion")
        configured_modes.append(candidate)
    if len(set(configured_modes)) > 1:
        raise ConfigError("supplied decision modes do not match")
    if configured_modes and configured_modes[0] != expected:
        raise ConfigError(f"supplied mode {configured_modes[0]!r} mismatches required mode {expected!r}")

    rationale = decision.get("rationale")
    if rationale is None:
        rationale = (
            "At least one of captions, zoom, or comparison is required; use the fixed Remotion template."
            if expected == "remotion"
            else "No captions, zoom, or comparison is required; normalize the recording as raw evidence."
        )
    elif isinstance(rationale, str):
        if not rationale.strip():
            raise ConfigError("decision.rationale must not be empty")
    elif isinstance(rationale, list):
        if not rationale or any(not isinstance(item, str) or not item.strip() for item in rationale):
            raise ConfigError("decision.rationale list must contain non-empty strings")
    else:
        raise ConfigError("decision.rationale must be a string or list of strings")
    return expected, rationale


def _validate_privacy(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError("privacy must be an object")
    if value.get("reviewed") is not True:
        raise ConfigError("privacy.reviewed must be true")
    reviewer = value.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ConfigError("privacy.reviewer must be a non-empty string")
    for key in ("secrets", "personal_data", "customer_data"):
        if _require_bool(value, key, "privacy") is not False:
            raise ConfigError(f"privacy.{key} must be false")
    for key in ("remote_urls", "data_urls"):
        if key in value and _require_bool(value, key, "privacy") is not False:
            raise ConfigError(f"privacy.{key} must be false when supplied")
    return copy.deepcopy(value)


def _validate_roots(value: Any, base_dir: Path) -> Tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError("allowed_input_roots must be a non-empty array of local directories")
    roots: List[Path] = []
    for index, item in enumerate(value):
        root = _local_path(item, base_dir, f"allowed_input_roots[{index}]")
        if not root.exists() or not root.is_dir():
            raise ConfigError(f"allowed_input_roots[{index}] is not an existing directory: {root}")
        roots.append(root)
    # Preserve order for diagnostics but avoid duplicate checks.
    return tuple(dict.fromkeys(roots))


def _validate_recording(value: Any, base_dir: Path, roots: Sequence[Path], repo_root: Path) -> Path:
    recording = _local_path(value, base_dir, "recording")
    if recording.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ConfigError("recording must have an .mp4, .mov, or .webm extension")
    if not recording.exists() or not recording.is_file():
        raise ConfigError(f"recording does not exist as a regular file: {recording}")
    if not any(is_within(recording, root) for root in roots):
        raise ConfigError("recording resolves outside the explicitly allowed input roots")
    if is_within(recording, repo_root):
        raise ConfigError("recording must be outside repo_root")
    return recording


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ConfigError(f"{label} must be a finite number")
    return number


def _validate_captions(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("captions must be an array")
    captions: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        label = f"captions[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{label} must be an object")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 300:
            raise ConfigError(f"{label}.text must be a non-empty string of at most 300 characters")
        start_ms = _finite_number(item.get("startMs"), f"{label}.startMs")
        end_ms = _finite_number(item.get("endMs"), f"{label}.endMs")
        if start_ms < 0 or end_ms <= start_ms or end_ms > MAX_DURATION * 1000:
            raise ConfigError(f"{label} must satisfy 0 <= startMs < endMs <= {int(MAX_DURATION * 1000)}")
        normalized: Dict[str, Any] = {"text": text.strip(), "startMs": start_ms, "endMs": end_ms}
        for key in ("timestampMs", "confidence"):
            if key not in item or item[key] is None:
                if key in item:
                    normalized[key] = None
                continue
            number = _finite_number(item[key], f"{label}.{key}")
            if key == "timestampMs" and number < 0:
                raise ConfigError(f"{label}.timestampMs must be non-negative")
            if key == "confidence" and not 0 <= number <= 1:
                raise ConfigError(f"{label}.confidence must be between 0 and 1")
            normalized[key] = number
        captions.append(normalized)
    return captions


def _validate_zooms(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("zooms must be an array")
    zooms: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        label = f"zooms[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{label} must be an object")
        start_ms = _finite_number(item.get("startMs"), f"{label}.startMs")
        end_ms = _finite_number(item.get("endMs"), f"{label}.endMs")
        x = _finite_number(item.get("x"), f"{label}.x")
        y = _finite_number(item.get("y"), f"{label}.y")
        scale = _finite_number(item.get("scale"), f"{label}.scale")
        if start_ms < 0 or end_ms <= start_ms or end_ms > MAX_DURATION * 1000:
            raise ConfigError(f"{label} must satisfy 0 <= startMs < endMs <= {int(MAX_DURATION * 1000)}")
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ConfigError(f"{label}.x and {label}.y must be between 0 and 1")
        if not 1 <= scale <= 4:
            raise ConfigError(f"{label}.scale must be between 1 and 4")
        zooms.append({"startMs": start_ms, "endMs": end_ms, "x": x, "y": y, "scale": scale})
    return zooms


def _validate_display_props(config: Mapping[str, Any], comparison_recording: Optional[Path], decision: Mapping[str, Any]) -> Tuple[str, Dict[str, str], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    title = config.get("title", "PR evidence")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ConfigError("title must be a non-empty string of at most 200 characters")
    labels_value = config.get("labels")
    if labels_value is None:
        labels_value = {}
    if not isinstance(labels_value, Mapping):
        raise ConfigError("labels must be an object")
    labels: Dict[str, str] = {}
    for key in ("primary", "secondary"):
        if key not in labels_value:
            continue
        label = labels_value[key]
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ConfigError(f"labels.{key} must be a non-empty string of at most 80 characters")
        labels[key] = label.strip()
    captions = _validate_captions(config.get("captions"))
    zooms = _validate_zooms(config.get("zooms"))
    comparison_value = config.get("comparison")
    if comparison_value is None:
        comparison_value = {}
    if not isinstance(comparison_value, Mapping):
        raise ConfigError("comparison must be an object")
    enabled = comparison_value.get("enabled", comparison_recording is not None)
    if type(enabled) is not bool:
        raise ConfigError("comparison.enabled must be a JSON boolean")
    layout = comparison_value.get("layout", "side-by-side")
    if layout not in {"side-by-side", "stacked"}:
        raise ConfigError("comparison.layout must be side-by-side or stacked")
    comparison = {"enabled": enabled, "layout": layout}
    if decision["requires_comparison"] and comparison_recording is None:
        raise ConfigError("decision.requires_comparison requires comparison_recording")
    if decision["requires_comparison"] and not enabled:
        raise ConfigError("decision.requires_comparison requires comparison.enabled=true")
    if decision["requires_captions"] and not captions:
        raise ConfigError("decision.requires_captions requires non-empty captions")
    if decision["requires_zoom"] and not zooms:
        raise ConfigError("decision.requires_zoom requires non-empty zooms")
    return title.strip(), labels, captions, zooms, comparison


def _validate_output_path(value: Any, base_dir: Path, label: str, repo_root: Path, suffix: str) -> Path:
    # Check the lexical path before resolving it: Path.resolve(strict=False) follows a dangling
    # symlink to its missing target, which would otherwise make the symlink invisible here.
    try:
        raw_value = os.fspath(value)
        raw_path = Path(raw_value)
        if not raw_path.is_absolute():
            raw_path = base_dir / raw_path
    except (OSError, TypeError, ValueError) as exc:
        raise ConfigError(f"{label} is not a valid local path: {exc}") from exc
    if raw_path.is_symlink():
        raise ConfigError(f"{label} must not be a symlink")
    path = _local_path(value, base_dir, label)
    if path.suffix.lower() != suffix:
        raise ConfigError(f"{label} must use the {suffix} extension")
    if is_within(path, repo_root):
        raise ConfigError(f"{label} must be outside repo_root")
    if path.is_symlink():
        raise ConfigError(f"{label} must not be a symlink")
    return path


def _default_output_paths(config: Mapping[str, Any], base_dir: Path, repo_root: Path) -> Tuple[Path, Path]:
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    parent = _safe_temp_parent(repo_root) / f"pr-evidence-video-{digest}"
    return parent / "artifact.mp4", parent / "manifest.json"


def validate_config(
    config: Mapping[str, Any],
    base_dir: Optional[Path] = None,
    mode_override: Optional[str] = None,
    output_override: Optional[Path] = None,
    manifest_override: Optional[Path] = None,
    input_root_overrides: Optional[Sequence[Path]] = None,
) -> ValidatedConfig:
    """Validate and normalize a JSON config without invoking external tools."""

    if not isinstance(config, Mapping):
        raise ConfigError("config must be a JSON object")
    base = (base_dir or Path.cwd()).resolve()
    repo_value = config.get("repo_root")
    if repo_value is None:
        raise ConfigError("repo_root is required and must be an existing application checkout directory")
    repo_root = _local_path(repo_value, base, "repo_root")
    if not repo_root.exists() or not repo_root.is_dir():
        raise ConfigError(f"repo_root is not an existing directory: {repo_root}")

    target = _validate_target(config.get("target"))
    decision_value = config.get("decision")
    if not isinstance(decision_value, Mapping):
        raise ConfigError("decision must be an object")
    mode, rationale = decide_mode(decision_value, supplied_mode=mode_override or config.get("mode"))
    decision = copy.deepcopy(dict(decision_value))
    decision["mode"] = mode
    decision["rationale"] = rationale
    privacy = _validate_privacy(config.get("privacy"))

    roots_value = input_root_overrides if input_root_overrides is not None else config.get("allowed_input_roots")
    if roots_value is None:
        roots_value = config.get("input_roots")
    roots = _validate_roots(list(roots_value) if input_root_overrides is not None else roots_value, base)
    recording_value = config.get("recording")
    if recording_value is None and isinstance(config.get("input"), Mapping):
        recording_value = config["input"].get("recording")
    recording = _validate_recording(recording_value, base, roots, repo_root)
    comparison_value = config.get("comparison_recording")
    comparison_recording = None
    if comparison_value is not None:
        comparison_recording = _validate_recording(comparison_value, base, roots, repo_root)
        if comparison_recording == recording:
            raise ConfigError("comparison_recording must be different from recording")
    title, labels, captions, zooms, comparison = _validate_display_props(config, comparison_recording, decision)

    output_value: Any = config.get("output")
    artifact_value: Any = None
    manifest_value: Any = None
    if isinstance(output_value, Mapping):
        artifact_value = output_value.get("artifact")
        manifest_value = output_value.get("manifest")
    elif isinstance(output_value, str):
        artifact_value = output_value
    artifact_value = output_override if output_override is not None else artifact_value
    manifest_value = manifest_override if manifest_override is not None else manifest_value
    if artifact_value is None:
        artifact_value, default_manifest = _default_output_paths(config, base, repo_root)
        if manifest_value is None:
            manifest_value = default_manifest
    elif manifest_value is None:
        manifest_value = Path(str(artifact_value)).with_suffix(".manifest.json")
    artifact_path = _validate_output_path(artifact_value, base, "output.artifact", repo_root, ".mp4")
    manifest_path = _validate_output_path(manifest_value, base, "output.manifest", repo_root, ".json")
    if artifact_path == manifest_path:
        raise ConfigError("output artifact and manifest must be different paths")
    input_paths = {recording}
    if comparison_recording is not None:
        input_paths.add(comparison_recording)
    if artifact_path in input_paths:
        raise ConfigError("output artifact must not overwrite an input recording")
    if manifest_path in input_paths:
        raise ConfigError("output manifest must not overwrite an input recording")

    return ValidatedConfig(
        config=copy.deepcopy(dict(config)),
        base_dir=base,
        repo_root=repo_root,
        allowed_input_roots=roots,
        recording=recording,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
        target=target,
        decision=decision,
        privacy=privacy,
        mode=mode,
        rationale=rationale,
        comparison_recording=comparison_recording,
        title=title,
        labels=labels,
        captions=captions,
        zooms=zooms,
        comparison=comparison,
    )


def _safe_temp_parent(repo_root: Optional[Path]) -> Path:
    candidates = [Path(tempfile.gettempdir()), Path("/tmp"), Path("/var/tmp")]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            continue
        if repo_root is not None and is_within(resolved, repo_root):
            continue
        if resolved.is_dir() and os.access(str(resolved), os.W_OK):
            return resolved
    raise RenderError("no writable temporary directory outside repo_root")


def _directory_open_flags() -> int:
    required = ("O_RDONLY", "O_DIRECTORY", "O_NOFOLLOW")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        raise RenderError(
            "safe no-follow directory operations require a POSIX platform with O_DIRECTORY and O_NOFOLLOW"
        )
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_bound_directory(path: Path, *, create: bool = False, label: str = "directory") -> int:
    """Open every directory component with dir_fd/O_NOFOLLOW and retain the final descriptor."""

    flags = _directory_open_flags()
    absolute = _canonical_system_alias(Path(os.path.abspath(os.fspath(path))))
    if not absolute.is_absolute():
        raise RenderError(f"{label} must be an absolute path")
    parts = absolute.parts
    try:
        current_fd = os.open(parts[0], flags)
    except OSError as exc:
        raise RenderError(f"could not open {label} root without following symlinks: {exc}") from exc
    try:
        for component in parts[1:]:
            if not component:
                continue
            try:
                child_fd = os.open(component, flags, dir_fd=current_fd)
            except FileNotFoundError:
                if not create:
                    raise RenderError(f"{label} does not exist: {absolute}")
                try:
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                    child_fd = os.open(component, flags, dir_fd=current_fd)
                except OSError as exc:
                    raise RenderError(f"could not create/open {label} without following symlinks: {exc}") from exc
            except OSError as exc:
                raise RenderError(f"could not open {label} component {component!r} without following symlinks: {exc}") from exc
            os.close(current_fd)
            current_fd = child_fd
        return current_fd
    except Exception:
        try:
            os.close(current_fd)
        except OSError:
            pass
        raise


def _canonical_system_alias(path: Path) -> Path:
    """Canonicalize only the OS-provided temporary aliases before no-follow walking."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    for alias in (Path("/var"), Path("/tmp"), Path("/var/tmp")):
        try:
            if is_within(absolute, alias) and alias.is_symlink():
                return alias.resolve(strict=False) / absolute.relative_to(alias)
        except OSError:
            continue
    return absolute


def _close_fd(fd: Optional[int]) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _unique_directory_filename(parent_fd: int, prefix: str, suffix: str = ".tmp") -> Tuple[str, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(32):
        name = f".{prefix}.{secrets.token_hex(12)}{suffix}"
        try:
            return name, os.open(name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            continue
        except OSError as exc:
            raise RenderError(f"could not create a private temporary file: {exc}") from exc
    raise RenderError("could not allocate a unique private temporary file")


def _sandbox_profile_literal(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


def _npm_sandbox_profile(run_dir: Path) -> str:
    """Allow npm writes only inside one disposable run on macOS."""

    allowed = _sandbox_profile_literal(run_dir.resolve(strict=False))
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny file-write*)\n"
        f'(allow file-write* (subpath "{allowed}"))\n'
    )


def _sandbox_npm_command(plan: RemotionPlan, command: Sequence[str]) -> List[str]:
    """Wrap npm with a write sandbox; other platforms fail closed rather than race a pathname."""

    if sys.platform != "darwin":
        raise RenderError(
            "safe private npm-cache writes require macOS sandbox-exec; this platform is unsupported"
        )
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file() or not os.access(str(sandbox), os.X_OK):
        raise RenderError("/usr/bin/sandbox-exec is required to protect the private npm cache")
    return [str(sandbox), "-p", _npm_sandbox_profile(plan.run_dir), *command]


def _detect_node_major() -> str:
    node = shutil.which("node")
    if node is None:
        return "unknown"
    try:
        result = subprocess.run(
            [node, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    match = re.search(r"(?:^|\s)v?(\d+)(?:\.|\s|$)", result.stdout or "")
    return match.group(1) if match else "unknown"


def _browser_candidates() -> Tuple[Path, ...]:
    if sys.platform == "darwin":
        return (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        )
    if sys.platform.startswith("linux"):
        return (
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/opt/google/chrome/google-chrome"),
        )
    if os.name == "nt":
        return (
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Chromium/Application/chrome.exe",
        )
    return ()


def _reject_symlink_components(path: Path, label: str) -> None:
    absolute = _canonical_system_alias(Path(os.path.abspath(os.fspath(path))))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            if current.is_symlink():
                raise RenderError(f"{label} contains a symlink component: {current}")
        except OSError as exc:
            raise RenderError(f"could not inspect {label}: {exc}") from exc


def _validate_browser_executable(value: Any, base_dir: Path, repo_root: Path) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not os.fspath(value).strip():
        raise RenderError("browser executable path must be a non-empty local path")
    raw = Path(os.fspath(value))
    if not raw.is_absolute():
        raw = base_dir / raw
    _reject_symlink_components(raw, "browser executable")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise RenderError(f"browser executable does not exist: {raw}") from exc
    if not resolved.is_file() or not os.access(str(resolved), os.X_OK):
        raise RenderError(f"browser executable is not an executable file: {resolved}")
    if is_within(resolved, repo_root.resolve(strict=False)):
        raise RenderError("browser executable must be outside repo_root")
    return resolved


def _resolve_browser_executable(config: ValidatedConfig) -> Path:
    configured = config.config.get("browser_executable")
    environmental = os.environ.get("PR_EVIDENCE_BROWSER_EXECUTABLE")
    if configured is not None and environmental is not None:
        raise RenderError("set browser_executable or PR_EVIDENCE_BROWSER_EXECUTABLE, not both")
    requested = configured if configured is not None else environmental
    if requested is not None:
        return _validate_browser_executable(requested, config.base_dir, config.repo_root)
    for candidate in _browser_candidates():
        try:
            return _validate_browser_executable(candidate, config.base_dir, config.repo_root)
        except RenderError:
            continue
    raise RenderError(
        "no approved local Chrome/Chromium executable found; set browser_executable or "
        "PR_EVIDENCE_BROWSER_EXECUTABLE before rendering"
    )


def build_ffmpeg_command(source: Path, destination: Path) -> List[str]:
    """Build the single normalization command used by raw and Remotion outputs."""

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-an",
        "-vf",
        "setparams=range=tv,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    return command


def build_ffprobe_command(path: Path) -> List[str]:
    return [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,pix_fmt,width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]


def _run_external(
    command: Sequence[str],
    cwd: Optional[Path] = None,
    timeout: Optional[float] = None,
    pass_fds: Sequence[int] = (),
    cwd_fd: Optional[int] = None,
) -> subprocess.CompletedProcess:
    if (pass_fds or cwd_fd is not None) and os.name != "posix":
        raise RenderError("safe descriptor-bound external execution requires POSIX pass_fds support")
    if cwd_fd is not None and cwd is not None:
        raise RenderError("cwd and cwd_fd are mutually exclusive")
    try:
        kwargs: Dict[str, Any] = {
            "cwd": str(cwd) if cwd is not None else None,
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
        }
        inherited_fds = tuple(pass_fds) + ((cwd_fd,) if cwd_fd is not None and cwd_fd not in pass_fds else ())
        if inherited_fds:
            kwargs["pass_fds"] = inherited_fds
        if cwd_fd is not None:
            def change_directory() -> None:
                os.fchdir(cwd_fd)
            kwargs["preexec_fn"] = change_directory
        result = subprocess.run(list(command), **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"command timed out after {timeout}s: {' '.join(command)}") from exc
    except (OSError, ValueError) as exc:
        raise RenderError(f"could not execute {command[0]}: {exc}") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RenderError(f"command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result


def _require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RenderError(f"required executable is unavailable: {name}")


def probe_media(path: Path) -> MediaInfo:
    """Inspect a normalized artifact with ffprobe."""

    _require_binary("ffprobe")
    result = _run_external(build_ffprobe_command(path))
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams") or []
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        duration_value = (payload.get("format") or {}).get("duration")
        duration = float(duration_value)
        info = MediaInfo(
            codec=str(video.get("codec_name") or ""),
            pixel_format=str(video.get("pix_fmt") or ""),
            width=int(video.get("width")),
            height=int(video.get("height")),
            duration=duration,
            audio=any(stream.get("codec_type") == "audio" for stream in streams),
        )
    except (ValueError, TypeError, StopIteration, KeyError, json.JSONDecodeError) as exc:
        raise RenderError(f"ffprobe returned unusable media metadata for {path}: {exc}") from exc
    if not math.isfinite(info.duration):
        raise RenderError("ffprobe duration is not finite")
    return info


def probe_duration(path: Path) -> float:
    """Read only the source duration needed to derive Remotion composition frames."""

    _require_binary("ffprobe")
    result = _run_external(build_ffprobe_command(path), timeout=INPUT_PROBE_TIMEOUT_SECONDS)
    try:
        payload = json.loads(result.stdout)
        duration = float((payload.get("format") or {}).get("duration"))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise RenderError(f"ffprobe returned no usable duration for {path}: {exc}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise RenderError(f"source duration must be finite and positive: {path}")
    if duration < MIN_DURATION or duration > MAX_DURATION:
        raise RenderError(f"source duration must be between 1 and 60 seconds: {duration}")
    return duration


def _preflight_inputs(config: ValidatedConfig) -> Dict[Path, float]:
    """Probe every validated input before creating outputs, runs, or materialized evidence."""

    durations: Dict[Path, float] = {}
    inputs = [config.recording]
    if config.comparison_recording is not None:
        inputs.append(config.comparison_recording)
    for path in inputs:
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise RenderError(f"cannot stat input recording {path}: {exc}") from exc
        if size > MAX_INPUT_BYTES:
            raise RenderError(
                f"input recording must be at most {MAX_INPUT_BYTES} bytes ({MAX_INPUT_BYTES // (1024 * 1024)} MiB): {path}"
            )
        duration = probe_duration(path)
        if not math.isfinite(duration) or not (MIN_DURATION <= duration <= MAX_DURATION):
            raise RenderError(f"source duration must be between 1 and 60 seconds: {duration}")
        durations[path] = duration
    return durations


def validate_media(path: Path, info: MediaInfo) -> None:
    if info.codec != "h264":
        raise RenderError(f"artifact codec must be h264, got {info.codec!r}")
    if info.pixel_format != "yuv420p":
        raise RenderError(f"artifact pixel format must be yuv420p, got {info.pixel_format!r}")
    if (info.width, info.height) != (1280, 720):
        raise RenderError(f"artifact resolution must be 1280x720, got {info.width}x{info.height}")
    if info.audio:
        raise RenderError("artifact must be standard muted output with no audio stream")
    if not (MIN_DURATION <= info.duration <= MAX_DURATION):
        raise RenderError(f"artifact duration must be between 1 and 60 seconds, got {info.duration}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RenderError(f"cannot stat artifact: {exc}") from exc
    if size < 1 or size > MAX_BYTES:
        raise RenderError(f"artifact must be between 1 byte and {MAX_BYTES} bytes, got {size}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RenderError(f"cannot hash artifact {path}: {exc}") from exc
    return digest.hexdigest()


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    except OSError as exc:
        raise RenderError(f"cannot hash persisted artifact descriptor: {exc}") from exc
    return digest.hexdigest()


def _persist_artifact(source: Path, destination: Path, parent_fd: Optional[int] = None) -> Tuple[int, str]:
    """Persist an artifact through a bound output directory and return stable size/hash."""

    owned_fd = parent_fd is None
    directory_fd = parent_fd if parent_fd is not None else _open_bound_directory(
        destination.parent,
        create=True,
        label="artifact output directory",
    )
    temporary_name: Optional[str] = None
    try:
        temporary_name, temporary_fd = _unique_directory_filename(directory_fd, destination.name)
        try:
            with source.open("rb") as source_stream, os.fdopen(temporary_fd, "wb") as output_stream:
                shutil.copyfileobj(source_stream, output_stream)
                output_stream.flush()
                os.fsync(output_stream.fileno())
            os.replace(
                temporary_name,
                destination.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            temporary_name = None
            os.fsync(directory_fd)
        except OSError as exc:
            raise RenderError(f"could not persist artifact {destination}: {exc}") from exc
        try:
            artifact_fd = os.open(destination.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        except OSError as exc:
            raise RenderError(f"could not reopen persisted artifact without following symlinks: {exc}") from exc
        try:
            stat_result = os.fstat(artifact_fd)
            return stat_result.st_size, _sha256_fd(artifact_fd)
        finally:
            _close_fd(artifact_fd)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except OSError:
                pass
        if owned_fd:
            _close_fd(directory_fd)


def _normalize(source: Path, destination: Path) -> None:
    _require_binary("ffmpeg")
    _run_external(build_ffmpeg_command(source, destination))
    if not destination.is_file():
        raise RenderError(f"ffmpeg completed without creating {destination}")


def _asset_name(path: Path, stem: str) -> str:
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise RenderError(f"unsupported evidence asset extension: {path}")
    return f"{stem}{suffix}"


def _duration_to_frames(duration: float) -> int:
    return max(30, min(int(MAX_DURATION * FPS), int(round(duration * FPS))))


def build_remotion_props(
    config: ValidatedConfig,
    *,
    primary_name: str = "primary.mp4",
    secondary_name: Optional[str] = None,
    duration_in_frames: int = 30,
) -> Dict[str, Any]:
    """Build the deterministic, local-only props object consumed by the fixed template."""

    props: Dict[str, Any] = {
        "title": config.title,
        "primary": {"src": primary_name, "label": config.labels.get("primary", "Primary")},
        "labels": {
            "primary": config.labels.get("primary", "Primary"),
            "secondary": config.labels.get("secondary", "Comparison"),
        },
        "captions": copy.deepcopy(config.captions),
        "zooms": copy.deepcopy(config.zooms),
        "comparison": copy.deepcopy(config.comparison),
        "durationInFrames": max(30, min(int(MAX_DURATION * FPS), int(duration_in_frames))),
    }
    if secondary_name is not None:
        props["secondary"] = {
            "src": secondary_name,
            "label": config.labels.get("secondary", "Comparison"),
        }
    return props


def build_remotion_command(
    entrypoint: Path,
    output: Path,
    props: Path,
    browser_executable: Path,
) -> List[str]:
    """Return the fixed-template command; it never includes an install or upload operation."""

    return [
        "npx",
        "--no-install",
        "remotion",
        "render",
        str(entrypoint),
        "PrEvidenceVideo",
        str(output),
        "--props",
        str(props),
        "--browser-executable",
        str(browser_executable),
        "--codec",
        "h264",
        "--pixel-format",
        "yuv420p",
        "--video-bitrate",
        REMOTION_VIDEO_BITRATE,
        "--concurrency",
        REMOTION_CONCURRENCY,
        "--timeout",
        str(REMOTION_RENDER_TIMEOUT_SECONDS * 1000),
        "--overwrite",
        "--muted",
    ]


def build_npm_ci_command(cache_dir: Path = Path(".npm-cache")) -> List[str]:
    return [
        "npm",
        "ci",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
        "--cache",
        str(cache_dir),
    ]


def prepare_remotion_run(
    config: ValidatedConfig,
    run_dir: Path,
    *,
    duration: Optional[float] = None,
) -> RemotionPlan:
    """Copy only the fixed template and prepare commands in an external run directory.

    Evidence files and props are deliberately materialized only after ``npm ci --ignore-scripts``
    has completed in ``_ensure_remotion_dependencies``.
    """

    run_dir = run_dir.resolve(strict=False)
    if config.repo_root is not None and is_within(run_dir, config.repo_root):
        raise RenderError("Remotion run directory must be outside repo_root")
    run_dir.mkdir(parents=True, exist_ok=True)
    props_path = run_dir / "props.json"
    output_path = run_dir / "remotion-output.mp4"
    template_dir = run_dir / "template"
    entrypoint = template_dir / "src" / "index.ts"
    public_dir = template_dir / "public"
    # Keep npm's cache in the copied template, next to node_modules, so one
    # disposable workspace contains every npm write.  The install command
    # refers to this as ``.npm-cache`` while its cwd is bound to template_fd.
    cache_dir = template_dir / ".npm-cache"
    browser_executable = _resolve_browser_executable(config)
    if not FIXED_TEMPLATE_SOURCE.is_dir():
        raise RenderError("fixed Remotion template is unavailable; add assets/remotion-template first")
    try:
        shutil.copytree(
            str(FIXED_TEMPLATE_SOURCE),
            str(template_dir),
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("node_modules", ".git"),
        )
    except OSError as exc:
        raise RenderError(f"could not prepare fixed Remotion workspace: {exc}") from exc
    duration_in_frames = _duration_to_frames(duration if duration is not None else probe_duration(config.recording))
    command = tuple(build_remotion_command(entrypoint, output_path, props_path, browser_executable))
    install_command = tuple(build_npm_ci_command(Path(".npm-cache")))
    return RemotionPlan(
        run_dir,
        props_path,
        output_path,
        template_dir,
        entrypoint,
        command,
        install_command,
        cache_dir,
        browser_executable,
        public_dir,
        duration_in_frames,
        config.repo_root,
    )


def materialize_remotion_run(
    config: ValidatedConfig,
    plan: RemotionPlan,
    *,
    duration: Optional[float] = None,
    events: Optional[List[str]] = None,
) -> None:
    """Copy only validated recordings and write deterministic props after dependency install."""

    try:
        plan.public_dir.mkdir(parents=True, exist_ok=True)
        primary_name = _asset_name(config.recording, "primary")
        shutil.copyfile(str(config.recording), str(plan.public_dir / primary_name))
        secondary_name = None
        if config.comparison_recording is not None:
            secondary_name = _asset_name(config.comparison_recording, "secondary")
            shutil.copyfile(str(config.comparison_recording), str(plan.public_dir / secondary_name))
        plan.props_path.write_text(
            json.dumps(
                build_remotion_props(
                    config,
                    primary_name=primary_name,
                    secondary_name=secondary_name,
                    duration_in_frames=plan.duration_in_frames
                    if duration is None
                    else _duration_to_frames(duration),
                ),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RenderError(f"could not materialize validated Remotion evidence: {exc}") from exc
    if events is not None:
        events.append("materialize")


def _ensure_remotion_dependencies(plan: RemotionPlan) -> None:
    # npm installs only into the copied temporary template. npx is invoked later with --no-install,
    # so rendering cannot silently download a different CLI or write into an application checkout.
    _require_binary("npm")
    _require_binary("npx")
    if not plan.template_dir.is_dir() or not plan.entrypoint.is_file():
        raise RenderError("fixed Remotion template is unavailable; complete the template step first")
    if not (plan.template_dir / "package.json").is_file():
        raise RenderError("fixed Remotion template package.json is unavailable; complete the template step first")
    if not (plan.template_dir / "package-lock.json").is_file():
        raise RenderError("fixed Remotion template package-lock.json is unavailable; generate the pinned lockfile first")
    # The cache is private to this disposable run. Bind npm's cwd to the copied template directory
    # descriptor and use a relative cache path. macOS sandbox-exec additionally denies npm writes
    # outside the run even if an attacker swaps .npm-cache after the no-follow bind; no persistent
    # cache survives cleanup.
    template_fd = _open_bound_directory(plan.template_dir, create=False, label="Remotion template directory")
    cache_fd = _open_bound_directory(plan.cache_dir, create=True, label="Remotion npm cache")
    try:
        install_command = tuple(build_npm_ci_command(Path(".npm-cache")))
        safe_install_command = _sandbox_npm_command(plan, install_command)
        _run_external(
            safe_install_command,
            cwd_fd=template_fd,
            timeout=REMOTION_INSTALL_TIMEOUT_SECONDS,
            pass_fds=(template_fd, cache_fd),
        )
        if not (plan.template_dir / "node_modules").is_dir():
            raise RenderError("fixed Remotion dependencies are unavailable; install them only in the temporary run directory")
    finally:
        _close_fd(template_fd)
        _close_fd(cache_fd)


def _build_manifest(
    config: ValidatedConfig,
    artifact: Path,
    info: MediaInfo,
    digest: str,
    size: Optional[int] = None,
) -> Dict[str, Any]:
    if size is None:
        size = artifact.stat().st_size
    return {
        "schema_version": SCHEMA_VERSION,
        "target": copy.deepcopy(config.target),
        "decision": {
            "mode": config.mode,
            "rationale": copy.deepcopy(config.rationale),
            "requires_captions": config.decision["requires_captions"],
            "requires_zoom": config.decision["requires_zoom"],
            "requires_comparison": config.decision["requires_comparison"],
        },
        "artifact": {
            "path": str(artifact),
            "hash": digest,
            "sha256": digest,
            "bytes": size,
            "mime": "video/mp4",
            "codec": info.codec,
            "pixel_format": info.pixel_format,
            "duration": info.duration,
            "duration_seconds": info.duration,
            "resolution": {"width": info.width, "height": info.height},
            "audio": False,
        },
        "privacy": copy.deepcopy(config.privacy),
        "reviewer": config.privacy["reviewer"],
        "evidence_review": {"status": "pending"},
        "handoff": {"status": "pending"},
    }


def _write_manifest(path: Path, manifest: Mapping[str, Any], parent_fd: Optional[int] = None) -> None:
    owned_fd = parent_fd is None
    directory_fd = parent_fd if parent_fd is not None else _open_bound_directory(
        path.parent,
        create=True,
        label="manifest output directory",
    )
    temporary_name: Optional[str] = None
    file_descriptor: Optional[int] = None
    try:
        temporary_name, file_descriptor = _unique_directory_filename(directory_fd, path.name)
        stream = os.fdopen(file_descriptor, "w", encoding="utf-8")
        file_descriptor = None
        with stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        temporary_name = None
        os.fsync(directory_fd)
    except OSError as exc:
        raise RenderError(f"could not write manifest {path}: {exc}") from exc
    finally:
        if file_descriptor is not None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=directory_fd)
            except OSError:
                pass
        if owned_fd:
            _close_fd(directory_fd)


def render(
    config: Mapping[str, Any],
    *,
    base_dir: Optional[Path] = None,
    mode_override: Optional[str] = None,
    output_override: Optional[Path] = None,
    manifest_override: Optional[Path] = None,
    input_root_overrides: Optional[Sequence[Path]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Validate, render, inspect, hash, and persist one artifact and manifest."""

    validated = validate_config(
        config,
        base_dir=base_dir,
        mode_override=mode_override,
        output_override=output_override,
        manifest_override=manifest_override,
        input_root_overrides=input_root_overrides,
    )
    input_durations = _preflight_inputs(validated)
    for path in (validated.artifact_path, validated.manifest_path):
        if path.exists() and not force:
            raise RenderError(f"refusing to overwrite existing output without --force: {path}")
    temporary_parent = _safe_temp_parent(validated.repo_root)
    with tempfile.TemporaryDirectory(prefix="pr-evidence-video-", dir=str(temporary_parent)) as temporary_name:
        run_dir = Path(temporary_name)
        normalized = run_dir / "normalized.mp4"
        if validated.mode == "raw":
            _normalize(validated.recording, normalized)
        else:
            plan = prepare_remotion_run(
                validated,
                run_dir / "remotion",
                duration=input_durations[validated.recording],
            )
            _ensure_remotion_dependencies(plan)
            materialize_remotion_run(
                validated,
                plan,
                duration=input_durations[validated.recording],
            )
            template_fd = _open_bound_directory(
                plan.template_dir,
                create=False,
                label="Remotion template directory",
            )
            try:
                _run_external(
                    plan.command,
                    cwd_fd=template_fd,
                    timeout=REMOTION_RENDER_TIMEOUT_SECONDS,
                    pass_fds=(template_fd,),
                )
                if not plan.output_path.is_file():
                    raise RenderError("Remotion completed without creating its output")
                _normalize(plan.output_path, normalized)
            finally:
                _close_fd(template_fd)

        info = probe_media(normalized)
        validate_media(normalized, info)
        artifact_parent_fd = _open_bound_directory(
            validated.artifact_path.parent,
            create=True,
            label="artifact output directory",
        )
        manifest_parent_fd = _open_bound_directory(
            validated.manifest_path.parent,
            create=True,
            label="manifest output directory",
        )
        try:
            artifact_size, digest = _persist_artifact(
                normalized,
                validated.artifact_path,
                parent_fd=artifact_parent_fd,
            )
            manifest = _build_manifest(validated, validated.artifact_path, info, digest, artifact_size)
            _write_manifest(validated.manifest_path, manifest, parent_fd=manifest_parent_fd)
        finally:
            _close_fd(artifact_parent_fd)
            _close_fd(manifest_parent_fd)
    return manifest


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not read JSON config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError("JSON config must be an object")
    return value


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render a local, privacy-reviewed PR evidence video")
    parser.add_argument("--config", required=True, help="JSON configuration path")
    parser.add_argument("--output", help="override output artifact path")
    parser.add_argument("--manifest", help="override output manifest path")
    parser.add_argument("--input-root", action="append", help="replace configured allowed input roots (repeatable)")
    parser.add_argument("--mode", choices=("raw", "remotion"), help="explicit mode assertion")
    parser.add_argument("--force", action="store_true", help="allow replacing the two exact output paths")
    args = parser.parse_args(argv)
    config_path = _local_path(args.config, Path.cwd(), "--config")
    config = _load_json(config_path)
    try:
        manifest = render(
            config,
            base_dir=config_path.parent,
            mode_override=args.mode,
            output_override=Path(args.output) if args.output else None,
            manifest_override=Path(args.manifest) if args.manifest else None,
            input_root_overrides=[Path(item) for item in args.input_root] if args.input_root else None,
            force=args.force,
        )
    except (ConfigError, RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    output_config = config.get("output")
    manifest_display: Any = args.manifest
    if manifest_display is None and isinstance(output_config, Mapping):
        manifest_display = output_config.get("manifest")
    if manifest_display is None:
        manifest_display = "<default>"
    print(json.dumps({"mode": manifest["decision"]["mode"], "artifact": manifest["artifact"], "manifest": str(manifest_display)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
