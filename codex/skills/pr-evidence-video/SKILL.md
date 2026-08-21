---
name: pr-evidence-video
description: Create a privacy-reviewed local PR evidence video from an MP4, MOV, or WebM recording. Use for user-visible PR changes that need a deterministic raw normalization or the fixed Remotion template, with manifest and GitHub handoff safety checks.
---

# PR Evidence Video

Generate one local, reviewable, muted MP4 for a user-visible PR change. This skill never uploads
anything and keeps evidence review separate from code completion review.

## Workflow

1. Read [config-schema.md](references/config-schema.md) and create a JSON config. It must name
   explicit allowed input roots and a local recording, bind the target to a 40-character head SHA
   and non-empty hexadecimal `patch_base_tree`/`patch_hash`, and pass the privacy review.
2. Run `scripts/render_pr_evidence.py --config <config.json>`. The three required decision booleans
   select `remotion` when any is true and `raw` otherwise. A supplied mismatching mode is rejected.
3. Inspect the artifact and manifest. Raw output is normalized with ffmpeg. Remotion copies the
   fixed template into an external temporary run directory, installs its pinned dependencies with
   `npm ci --ignore-scripts`, then copies validated local assets and deterministic props. It fails
   closed when the template,
   dependencies, browser binary, or renderer is unavailable.
4. Keep the generated `evidence_review.status` and `handoff.status` pending until an authorized
   reviewer and operator act. Read [github-handoff.md](references/github-handoff.md) before any
   separately authorized GitHub Conversation upload.

Read [decision-and-privacy.md](references/decision-and-privacy.md) for fail-closed checks and
[github-handoff.md](references/github-handoff.md) for the approval boundary.

Remotion dependencies are installed with `npm ci --ignore-scripts` into the copied temporary template,
using a private `.npm-cache` directory inside that disposable run. On Darwin,
`sandbox-exec` limits npm writes to that run. On Linux/WSL2, `bubblewrap >= 0.10.0` (`bwrap`, with
`--bind-fd`) exposes the host root read-only, shares the network, and bind-mounts only the disposable
run (plus descriptor-bound template/cache mounts at fixed namespace paths); `HOME`, `TMPDIR`, npm cache, and npm user config all
stay inside the run. Unsupported platforms, WSL1, or a missing/unusable sandbox fail closed rather
than using an unsafe pathname cache. The npm cache is never persistent and is removed with the run;
npm may require network/tool approval on each render. Before
any recording or props are materialized, the renderer resolves an already-installed local Chrome or
Chromium executable from `browser_executable`, `PR_EVIDENCE_BROWSER_EXECUTABLE`, or a conservative
OS allowlist. The render command receives `--browser-executable`; missing or unsafe executables fail
closed, so Remotion never downloads a browser while evidence is present. The renderer never uploads,
installs into an application checkout, creates an app-local Remotion project, or adds recordings,
`node_modules`, lockfiles, or generated evidence to a repository.

For WSL2, keep the repository under the Linux filesystem (for example `~/code`) rather than
`/mnt/c`; `setup.sh link-codex` warns for a `/mnt/*` checkout, and the renderer stops before evidence
materialization whenever the required safe descriptor/mount boundary cannot be established. WSL1 is
not supported. Install/verify `bubblewrap >= 0.10.0`, `node`/`npm`/`npx`, `ffmpeg`/`ffprobe`, and a local Linux
Chrome/Chromium before a real render. The deterministic contract smoke command is:

```bash
set -e
for tool in /usr/bin/bwrap /usr/bin/npm /usr/bin/npx; do test -x "$tool"; done
for tool in node ffmpeg ffprobe; do command -v "$tool" >/dev/null; done
/usr/bin/bwrap --help | grep -F -- --bind-fd >/dev/null
command -v google-chrome || command -v chromium || command -v chromium-browser
python3 -m unittest codex/skills/pr-evidence-video/tests/test_render_pr_evidence.py -v
```

The Linux security boundary uses the root-owned system executables at `/usr/bin/bwrap`,
`/usr/bin/npm`, and `/usr/bin/npx`, never a caller-controlled `PATH` replacement.

The command includes Linux-platform mocks and does not claim a real WSL2 render; perform the actual
browser/Remotion smoke only in an explicitly prepared WSL2 environment.
