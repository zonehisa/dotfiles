# Configuration contract

`render_pr_evidence.py` accepts one JSON object. Paths are resolved relative to the config file,
unless absolute. `repo_root` is mandatory and must be an existing application checkout directory;
artifact and manifest outputs must resolve outside it, even with `--force` or path overrides.
`allowed_input_roots` is mandatory: an input must be an existing regular file inside one of those
roots after symlink resolution. URL and `data:` values are never accepted.

```json
{
  "schema_version": 1,
  "repo_root": "/path/to/application-checkout",
  "allowed_input_roots": ["/private/tmp/pr-recordings"],
  "recording": "/private/tmp/pr-recordings/browser-recording.mov",
  "comparison_recording": "/private/tmp/pr-recordings/before.mov",
  "title": "Checkout flow",
  "labels": {
    "primary": "After",
    "secondary": "Before"
  },
  "captions": [
    {"text": "Submit succeeds", "startMs": 800, "endMs": 1800, "timestampMs": 1200, "confidence": 0.98}
  ],
  "zooms": [
    {"startMs": 700, "endMs": 1800, "x": 0.72, "y": 0.52, "scale": 1.6}
  ],
  "comparison": {
    "enabled": true,
    "layout": "side-by-side"
  },
  "target": {
    "repository": "owner/repository",
    "pr_number": 123,
    "branch": "feature/example",
    "head_sha": "0123456789012345678901234567890123456789",
    "review_fingerprint": {
      "patch_base_tree": "0123456789012345678901234567890123456789",
      "patch_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  },
  "decision": {
    "requires_captions": true,
    "requires_zoom": true,
    "requires_comparison": true,
    "mode": "remotion",
    "rationale": "The changed submit state is clearest with a caption, zoom, and before/after comparison."
  },
  "privacy": {
    "reviewed": true,
    "reviewer": "agent-or-human",
    "secrets": false,
    "personal_data": false,
    "customer_data": false
  },
  "output": {
    "artifact": "/private/tmp/pr-evidence/artifact.mp4",
    "manifest": "/private/tmp/pr-evidence/manifest.json"
  }
}
```

`target.pr_number` is an integer or JSON `null` while the PR is pending. `repository` must be
`OWNER/REPO`; `head_sha` is exactly 40 hexadecimal characters. Both fingerprint values must be
non-empty hexadecimal strings. A branch is retained when supplied but is not used as a substitute
for the head SHA.

The three decision booleans are required JSON booleans. Their OR selects the mode: any true means
`remotion`, all false means `raw`. If `decision.mode` (or the CLI `--mode`) is supplied, it must
match the selected mode. `decision.rationale` is optional and is generated when omitted.

The optional Remotion props are local-only and are copied into the disposable template's `public/`
directory: `comparison_recording` is a second MP4/MOV/WebM input; `title` is a short display title;
`labels.primary` and `labels.secondary` label the sources; `captions` contains non-empty objects with
`text`, positive `startMs < endMs`, and optional `timestampMs`/`confidence`; `zooms` contains objects
with `startMs < endMs`, normalized `x`/`y` coordinates, and a `scale` from 1 through 4; and
`comparison` must be `{ "enabled": true, "layout": "side-by-side" | "stacked" }` when comparison
is required. A required caption, zoom, or comparison decision must have its corresponding non-empty
props. Raw mode ignores these optional overlay props.

`browser_executable` is an optional local executable path used for Remotion. When omitted, the
renderer checks `PR_EVIDENCE_BROWSER_EXECUTABLE` and a conservative OS allowlist. It rejects symlink
components, non-executable files, and paths inside `repo_root`.

`privacy.reviewed` must be `true`; `secrets`, `personal_data`, and `customer_data` must each be
explicit `false`, and `reviewer` must be non-empty. The renderer always emits a standard muted
artifact (`audio: false`).

Before creating an output directory, temporary run, or normalized artifact, the renderer runs a
bounded `ffprobe` on every input (30-second timeout) and rejects durations outside 1–60 seconds.
Each local input is capped at 512 MiB, a conservative ceiling for a 60-second browser recording;
oversize, unreadable, or out-of-range primary or comparison inputs fail before ffmpeg/npm work.

The manifest contains `schema_version`, the complete target, decision/rationale, exact artifact
path and SHA-256 hash, bytes, MIME, codec, pixel format, duration, resolution, and `audio: false`.
`evidence_review.status` and `handoff.status` start at `pending` and are independent of one
another. The renderer never performs an upload.

Remotion installs dependencies into the copied temporary template with `npm ci --ignore-scripts`,
using only a private relative `.npm-cache` directory inside the disposable run. On macOS,
`sandbox-exec` limits npm writes to that run; unsupported platforms fail closed rather than using
an unsafe pathname cache. That cache is removed with the run and may require network/tool approval
on every render. Set optional
`browser_executable` to an already-installed local Chrome/Chromium executable, or use
`PR_EVIDENCE_BROWSER_EXECUTABLE`; otherwise the renderer checks a conservative OS allowlist. The
path must be executable, outside `repo_root`, and free of symlink components. The render command
passes `--browser-executable` and fails closed before evidence materialization if no safe browser is
available; Remotion is never allowed to download a browser after local evidence enters the run.
