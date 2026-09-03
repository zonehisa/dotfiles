#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$ROOT/codex/AGENTS.md"
POLICY="$ROOT/policies/development-workflow.md"
SKILL="$ROOT/codex/skills/git-workflow/SKILL.md"
DELIVERY="$ROOT/codex/skills/git-workflow/references/delivery.md"
ISSUE_START="$ROOT/codex/skills/git-workflow/references/issue-start.md"
PARALLEL="$ROOT/codex/skills/parallel-worktree/SKILL.md"
LIFECYCLE="$ROOT/codex/skills/parallel-worktree/references/lifecycle.md"
FINGERPRINT="$ROOT/codex/skills/git-workflow/scripts/review_fingerprint.py"
UI_EVIDENCE="$ROOT/codex/skills/git-workflow/scripts/ui_evidence.py"
CODE_REVIEW="$ROOT/codex/skills/git-workflow/references/code-review.md"
SNAPSHOT="$ROOT/codex/skills/git-workflow/scripts/external_pr_snapshot.py"
SNAPSHOT_TEST="$ROOT/codex/skills/git-workflow/tests/test_external_pr_snapshot.py"

fail() { printf 'workflow-policy: %s\n' "$1" >&2; exit 1; }
contains() { grep -Fq -- "$1" "$2" || fail "missing '$1' in $2"; }
contains_any() {
  local path="$2"
  grep -Fq -- "$1" "$path" || grep -Fq -- "$3" "$path" || fail "missing either '$1' or '$3' in $path"
}
absent() {
  if grep -Fq -- "$1" "$2"; then
    printf 'workflow-policy: obsolete marker in %s: %s\n' "$2" "$1" >&2
    exit 1
  fi
}

for path in "$AGENTS" "$POLICY" "$SKILL" "$DELIVERY" "$ISSUE_START" "$PARALLEL" "$LIFECYCLE" "$FINGERPRINT" "$UI_EVIDENCE" "$CODE_REVIEW" "$SNAPSHOT" "$SNAPSHOT_TEST"; do
  [[ -f "$path" ]] || fail "missing required file: $path"
done

agent_bytes=$(wc -c < "$AGENTS" | tr -d ' ')
(( agent_bytes >= 3000 && agent_bytes <= 6000 )) || fail "AGENTS.md must stay between 3KB and 6KB (got $agent_bytes)"

# Normal work is direct; delegation and Worktrees are opt-in conditions.
contains 'Coordinator/main が read-only の調査、Plan/TDD、' "$AGENTS"
contains 'source edit、targeted test を直接行う' "$AGENTS"
contains '読み取りのために `git_operator_luna` や `implementer_luna` を必須化しません' "$POLICY"
contains 'Do not spawn `git_operator_luna` merely for reads.' "$ISSUE_START"
contains 'Do not spawn `git_operator_luna` merely for reads.' "$SKILL"
contains 'implementer_luna` only for parallel, dirty-checkout, background/long-running' "$DELIVERY"
contains 'Worktree only for parallel, dirty-primary, background/long-running, or explicit isolation' "$SKILL"
contains 'Clean, single, foreground' "$PARALLEL"
contains 'clean single-foreground' "$LIFECYCLE"
contains 'task remains in the current checkout' "$LIFECYCLE"
absent 'Delegate Git/GitHub discovery, target resolution, command preparation, and non-approval-bound execution' "$SKILL"
absent 'git-workflow`のcompletion reviewを除くGit/GitHubの調査' "$AGENTS"
absent 'Implementation/TDD: `implementer_luna`, GPT-5.6 Luna `max`, workspace-write.' "$PARALLEL"

# The only mandatory delegated lane is fresh-context Luna/max completion review.
for path in "$AGENTS" "$POLICY" "$DELIVERY"; do
  contains 'reviewer_luna' "$path"
  contains 'Luna `max`' "$path"
done
contains 'fresh-context' "$SKILL"
contains '`reviewer_luna`' "$SKILL"
contains 'fresh-context' "$PARALLEL"
contains '`reviewer_luna`' "$PARALLEL"
contains 'R1-R4' "$DELIVERY"
contains 'fork_turns="none"' "$DELIVERY"
contains 'same immutable' "$DELIVERY"
contains 'review_context_key' "$DELIVERY"
contains 'threat_model_supported_use_declaration_hash' "$DELIVERY"
contains 'Round 1' "$DELIVERY"
contains 'Round 2' "$DELIVERY"
contains 'Round 3' "$DELIVERY"
contains 'P0-P2 findings block' "$DELIVERY"

# UI confirmation is explicit IAB and one final candidate, not a per-edit loop.
for path in "$AGENTS" "$POLICY" "$DELIVERY" "$SKILL"; do
  contains 'agent.browsers.get("iab")' "$path"
  contains_any 'automatic fallback' "$path" 'auto-fallback'
  contains_any 'once' "$path" '一度だけ'
done
contains 'do not start completion review or an IAB check after every' "$DELIVERY"
contains 'visual tweak' "$DELIVERY"
contains 'final IAB' "$DELIVERY"
contains 'primary behavior once on that same candidate' "$DELIVERY"
absent 'provisional' "$DELIVERY"
absent 'provisional Coordinator packet' "$ROOT/codex/agents/verifier-luna.toml"
contains 'Video/evidence is opt-in' "$DELIVERY"

# Preserve the non-local review and delivery safety contracts while keeping this sensor small.
contains 'external_pr_snapshot.py' "$CODE_REVIEW"
contains 'review_fingerprint.py' "$CODE_REVIEW"
contains 'browser_evidence_hash' "$DELIVERY"
contains 'checkpoint_scope' "$DELIVERY"
contains 'accepted_source_fingerprint' "$DELIVERY"
contains 'metadata sidecar' "$DELIVERY"
contains 'one long event wait' "$ROOT/codex/AGENTS.md"
contains 'explicit authorization' "$DELIVERY"
contains 'Required CI' "$DELIVERY"
contains 'two operator stages' "$CODE_REVIEW"
contains '最大3つ' "$AGENTS"
contains 'at most three delegated children' "$SKILL"
absent 'review_fingerprint.py' "$SNAPSHOT"
contains 'merge-base' "$SNAPSHOT"
contains 'external_pr_snapshot' "$SNAPSHOT_TEST"

# Changed-path fingerprint contract is documented and implemented.
contains 'fingerprint_scope=changed-paths-blob-mode' "$DELIVERY"
contains 'changed_paths' "$FINGERPRINT"
contains 'changed_path_fingerprint' "$FINGERPRINT"
contains '"blob"' "$FINGERPRINT"
contains '"mode"' "$FINGERPRINT"
contains 'HEAD/index/staging metadata, mtimes, untracked files, and unrelated paths' "$DELIVERY"
contains 'Git mode' "$POLICY"
contains 'Git mode' "$UI_EVIDENCE"
absent 'tracked-diff\\0' "$FINGERPRINT"
absent 'untracked\\0' "$FINGERPRINT"

# All bundled agent TOMLs keep the requested Luna/max and sandbox contracts.
TOML_PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tomllib' >/dev/null 2>&1; then
    TOML_PYTHON="$candidate"
    break
  fi
done
[[ -n "$TOML_PYTHON" ]] || fail "Python 3.11+ with tomllib is required for agent TOML validation"

"$TOML_PYTHON" - "$ROOT/codex/agents" <<'PY'
from pathlib import Path
import sys
import tomllib

root = Path(sys.argv[1])
expected = {
    "implementer-luna.toml": ("implementer_luna", "workspace-write"),
    "explorer-luna.toml": ("explorer_luna", "read-only"),
    "verifier-luna.toml": ("verifier_luna", "workspace-write"),
    "reviewer-luna.toml": ("reviewer_luna", "read-only"),
    "git-operator-luna.toml": ("git_operator_luna", "workspace-write"),
}
for filename, (name, sandbox) in expected.items():
    path = root / filename
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("name") != name or data.get("model") != "gpt-5.6-luna":
        raise SystemExit(f"{filename}: name/model contract failed")
    if data.get("model_reasoning_effort") != "max" or data.get("sandbox_mode") != sandbox:
        raise SystemExit(f"{filename}: max/sandbox contract failed")
print(f"agent TOML contract passed ({len(expected)} files)")
PY

# The fingerprint and UI helpers have focused regression suites; run them here so this policy
# sensor exercises the implementation rather than only checking prose.
(cd "$ROOT" && python3 -m unittest \
  codex/skills/git-workflow/tests/test_review_fingerprint.py \
  codex/skills/git-workflow/tests/test_ui_evidence.py \
  codex/skills/git-workflow/tests/test_external_pr_snapshot.py)

printf 'workflow-policy: passed\n'
