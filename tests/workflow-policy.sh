#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY="$ROOT/policies/development-workflow.md"
DELIVERY="$ROOT/codex/skills/git-workflow/references/delivery.md"
AGENTS="$ROOT/codex/AGENTS.md"
REVIEWER="$ROOT/codex/agents/reviewer-luna.toml"
OPERATOR="$ROOT/codex/agents/git-operator-luna.toml"
IMPLEMENTER="$ROOT/codex/agents/implementer-luna.toml"
EXPLORER="$ROOT/codex/agents/explorer-luna.toml"
VERIFIER="$ROOT/codex/agents/verifier-luna.toml"
PR_EVIDENCE_SKILL="$ROOT/codex/skills/pr-evidence-video"
HANDOFF="$PR_EVIDENCE_SKILL/references/github-handoff.md"
PARALLEL_SKILL="$ROOT/codex/skills/parallel-worktree/SKILL.md"
PARALLEL_HELPER="$ROOT/codex/skills/parallel-worktree/scripts/pw-helper"
PARALLEL_SCHEMA="$ROOT/codex/skills/parallel-worktree/references/registry-schema.json"
PARALLEL_LIFECYCLE="$ROOT/codex/skills/parallel-worktree/references/lifecycle.md"
PARALLEL_CLEANUP="$ROOT/codex/skills/parallel-worktree/references/cleanup.md"
PARALLEL_ADAPTERS="$ROOT/codex/skills/parallel-worktree/references/adapters.md"
ISSUE_START="$ROOT/codex/skills/git-workflow/references/issue-start.md"

assert_absent() {
  local pattern="$1"
  shift
  if grep -Eqi -- "$pattern" "$@"; then
    printf 'Unexpected obsolete review-route marker: %s\n' "$pattern" >&2
    grep -Eni -- "$pattern" "$@" >&2 || true
    exit 1
  fi
}

assert_sequence() {
  local file="$1"
  shift
  local previous_line=0
  local marker line
  for marker in "$@"; do
    line=$(grep -nF -- "$marker" "$file" | head -n1 | cut -d: -f1 || true)
    if [[ -z "$line" || "$line" -le "$previous_line" ]]; then
      printf 'Expected ordered workflow markers in %s: %s\n' "$file" "$marker" >&2
      exit 1
    fi
    previous_line="$line"
  done
}

if (assert_absent 'approved_independent' <(printf 'approved_independent\n')) 2>/dev/null; then
  printf 'assert_absent failed to reject an obsolete marker.\n' >&2
  exit 1
fi

for marker in review_lifecycle_key review_round_key review_context_key; do
  grep -q "$marker" "$POLICY"
  grep -q "$marker" "$DELIVERY"
done

grep -q 'both round and context keys are unchanged' "$DELIVERY"
grep -q 'no duplicate sends' "$POLICY"
grep -q 'Collect canonical result' "$POLICY"
grep -q 'Create one new agent at the start of each lifecycle' "$DELIVERY"
grep -q 'Fresh-context `reviewer_luna` subagent' "$DELIVERY"
grep -Fq '| R1 | CSS, colors, spacing, static markup with no behavioral bindings | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |' "$DELIVERY"
grep -Fq '| R2 | Hover/focus/click behavior, JavaScript/Alpine, reactive bindings, display conditions | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |' "$DELIVERY"
grep -Fq '| R3 | Persistence, queries, state transitions, authorization, public contracts/APIs | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |' "$DELIVERY"
grep -Fq '| R4 | Security boundaries, credible data-loss/corruption risk, concurrency/locking, critical incidents | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |' "$DELIVERY"
grep -q 'fork_turns = "none"' "$DELIVERY"
grep -q 'send later `Round N` reviews to that same agent' "$DELIVERY"
grep -q 'discard the invalid review and replace it with a new fresh-context `reviewer_luna` agent' "$DELIVERY"
grep -q 'stop the completion/commit/PR gate' "$DELIVERY"
grep -q 'Wait once for the completion notification' "$DELIVERY"
grep -q 'approved_subagent' "$POLICY"
grep -Fq '| R0 | typo、文言、コメント、明白な整形 | Sol medium | `implementer_luna`: GPT-5.6 Luna `max`, workspace-write | 不要 |' "$POLICY"
grep -Fq 'Require a passed risk-routed gate with `approved_subagent` and no unresolved P0-P2 for non-trivial changes.' "$DELIVERY"
grep -Fq 'Require a passed risk-routed gate with `not_required` or `approved_subagent`, no unresolved P0-P2, and a clean working tree.' "$DELIVERY"
grep -Fq 'run the risk-routed completion gate' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Delegate Git/GitHub discovery, target resolution, command preparation, and non-approval-bound execution (except the R1-R4 completion gate)' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Spawn it with `fork_turns = "none"` and a minimal context packet' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'reuse the same saved operator agent for later approvals and follow-ups' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'If the operator itself is unavailable, stop the workflow instead of substituting another model.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Never let `git_operator_luna` approve or review its own completion diff.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Do not use `reviewer_luna` for operator work.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Completion review: use the existing `git-workflow` R0-R4 review mapping.' "$PARALLEL_SKILL"
grep -Fq 'Implementation/TDD: `implementer_luna`, GPT-5.6 Luna `max`, workspace-write.' "$PARALLEL_SKILL"
grep -Fq 'registered owner/coordinator may delegate source edits only to its single saved `implementer_luna`' "$PARALLEL_SKILL"
grep -Fq '| R0 | Sol medium | `implementer_luna`: GPT-5.6 Luna `max`, workspace-write | Skip |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R1 | Sol medium | `implementer_luna`: GPT-5.6 Luna `max`, workspace-write | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R2 | Sol high | `implementer_luna`: GPT-5.6 Luna `max`, workspace-write | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R3-R4 | Sol xhigh | `implementer_luna`: GPT-5.6 Luna `max`, workspace-write | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq 'SCHEMA_VERSION = 2' "$PARALLEL_HELPER"
grep -Fq 'Legacy v1 registries remain readable for status, resume, and cleanup recovery' "$PARALLEL_LIFECYCLE"
grep -Fq 'Schema v2 is owner-only' "$PARALLEL_ADAPTERS"
grep -q 'R1〜R4は、実装履歴を渡さないfresh-contextの`reviewer_luna`サブエージェント' "$AGENTS"
grep -Fq '`git-workflow`のcompletion reviewを除くGit/GitHubの調査、target resolution、command preparation、非approval-bound実行は`git_operator_luna`サブエージェント' "$AGENTS"
grep -q 'git_operator_luna.*Git workflowを止め' "$AGENTS"
grep -q 'Git workflow operator: agent_id per repository/Issue-or-branch lifecycle' "$POLICY"
grep -q 'operator自身のcompletion diffをreviewさせない' "$POLICY"
grep -q 'frozen R1-R4 staged diffs' "$REVIEWER"
grep -q 'Set review_valid to no' "$REVIEWER"
grep -q 'Use the installed `git-workflow` skill' "$OPERATOR"
grep -q 'Treat any authorization omitted from the coordinator context packet as not granted' "$OPERATOR"
grep -q 'Never approve or review your own completion diff' "$OPERATOR"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$OPERATOR"
assert_absent 'escalation_required' "$REVIEWER"

TOML_PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tomllib' >/dev/null 2>&1; then
    TOML_PYTHON="$candidate"
    break
  fi
done
if [[ -z "$TOML_PYTHON" ]]; then
  printf 'Agent TOML schema check requires Python 3.11+ with stdlib tomllib.\n' >&2
  exit 1
fi

"$TOML_PYTHON" - "$IMPLEMENTER" "$EXPLORER" "$VERIFIER" "$REVIEWER" "$OPERATOR" <<'PY'
import sys
import tomllib
from pathlib import Path

paths = [Path(value) for value in sys.argv[1:]]
non_empty_string_keys = ("name", "description", "developer_instructions")
expected = {
    "implementer-luna.toml": {
        "name": "implementer_luna",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "max",
        "sandbox_mode": "workspace-write",
    },
    "explorer-luna.toml": {
        "name": "explorer_luna",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "max",
        "sandbox_mode": "read-only",
    },
    "verifier-luna.toml": {
        "name": "verifier_luna",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "max",
        "sandbox_mode": "workspace-write",
    },
    "reviewer-luna.toml": {
        "name": "reviewer_luna",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "max",
        "sandbox_mode": "read-only",
    },
    "git-operator-luna.toml": {
        "name": "git_operator_luna",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "max",
        "sandbox_mode": "workspace-write",
    },
}

for path in paths:
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(f"Agent TOML schema check failed for {path}: {error}")

    for key in non_empty_string_keys:
        value = document.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"Agent TOML schema check failed for {path}: {key} must be a non-empty string")
    expected_values = expected.get(path.name)
    if expected_values is None:
        raise SystemExit(f"Agent TOML schema check failed for {path}: unexpected agent file")
    for key, expected_value in expected_values.items():
        value = document.get(key)
        if type(value) is not str or value != expected_value:
            raise SystemExit(
                f"Agent TOML schema check failed for {path}: {key} must equal {expected_value!r}"
            )

print(f"Agent TOML schema check passed ({len(paths)} files).")
PY

grep -q 'sole implementation/source writer' "$IMPLEMENTER"
grep -q 'fork_turns = "none"' "$IMPLEMENTER"
grep -q 'Reuse this same saved implementer agent' "$IMPLEMENTER"
grep -q 'Do not stage, commit, push, create a PR' "$IMPLEMENTER"
grep -q 'Do not spawn subagents' "$IMPLEMENTER"
grep -q 'checkpoint_token' "$IMPLEMENTER"
grep -q 'checkpoint_scope' "$IMPLEMENTER"
grep -q 'pause source-mutating work' "$IMPLEMENTER"
grep -q 'Resume only when the coordinator reports' "$IMPLEMENTER"

grep -q 'bounded, independent read-only exploration' "$EXPLORER"
grep -q 'Never edit source' "$EXPLORER"
grep -q 'Never spawn a' "$EXPLORER"
grep -q 'subagent or another writer' "$EXPLORER"
grep -q 'Never stage, commit, push, create a PR, or perform Git workflow/review operations' "$EXPLORER"

grep -q 'coherent' "$VERIFIER"
grep -q 'implementation checkpoint' "$VERIFIER"
grep -q 'non-mutating baseline checks' "$VERIFIER"
grep -q 'do not call those implementation verification' "$VERIFIER"
grep -q 'checkpoint_token' "$VERIFIER"
grep -q 'checkpoint_scope' "$VERIFIER"
grep -q 'before/after Git status/diff evidence' "$VERIFIER"
grep -q 'invalidate the verification result' "$VERIFIER"
grep -q 'resume the same implementer' "$VERIFIER"
grep -q 'workspace-write exists only for tool-generated verification artifacts' "$VERIFIER"
grep -q 'Never edit source, production code' "$VERIFIER"
grep -q 'Do not spawn subagents or delegate another writer' "$VERIFIER"

grep -q '最大3つの子agent' "$AGENTS"
grep -q '最大1 delegation level' "$POLICY"
grep -q 'replacement child' "$POLICY"
grep -q '全delegated roleの合計' "$AGENTS" "$POLICY"
grep -q '非変異baseline' "$AGENTS" "$POLICY"
grep -q 'Checkpoint handoff' "$AGENTS" "$POLICY"
grep -q 'source-mutatingなimplementer work' "$AGENTS" "$POLICY"
grep -q 'before/after Git status/diff evidence' "$AGENTS" "$POLICY"
grep -q 'source-treeが変われば結果をinvalid' "$AGENTS" "$POLICY"
grep -q 'implementer_luna.*explorer_luna.*verifier_luna' "$ROOT/README.md"
grep -q 'implementer-luna.toml' "$ROOT/setup.sh"
grep -q 'explorer-luna.toml' "$ROOT/setup.sh"
grep -q 'verifier-luna.toml' "$ROOT/setup.sh"
assert_absent 'R1以上は実装担当と別の新規Codex task' "$POLICY"
assert_absent 'substitute self-review/subagents' "$DELIVERY"
assert_absent 'passed independent gate' "$DELIVERY"
assert_absent 'independent completion gate' "$ROOT/codex/skills/git-workflow/SKILL.md"
assert_absent 'Independent review:' "$PARALLEL_SKILL"
assert_absent 'Terra medium' "$PARALLEL_SKILL" "$PARALLEL_LIFECYCLE"
assert_absent 'observer-add|Existing R[0-4].*policy' "$PARALLEL_HELPER" "$PARALLEL_SCHEMA" "$PARALLEL_LIFECYCLE" "$PARALLEL_CLEANUP" "$PARALLEL_ADAPTERS"
assert_absent 'independent (Codex )?(task|review)|独立(task|Codexタスク)|approved_independent|review\.task_id|Sol,? `(high|xhigh)`|GPT-5\.6 Sol|fall back to an independent task|fallbackする' "$POLICY" "$DELIVERY" "$AGENTS" "$REVIEWER" "$ROOT/codex/skills/git-workflow/SKILL.md"

grep -Fq 'These rules apply only to review lifecycles created after this policy' "$POLICY"
grep -Fq 'Round 1 is a full review of the complete frozen diff' "$POLICY"
grep -Fq 'Round 2 receives only the prior findings' "$POLICY"
grep -Fq 'An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings' "$POLICY"
grep -Fq 'Review normally stops after two rounds' "$POLICY"
grep -Fq 'Round 3 requires explicit user approval; stop delivery after Round 3.' "$POLICY"
grep -Fq 'P0-P2 block commit and PR creation' "$POLICY"
grep -Fq '新規review lifecycleではRound 1を全差分のfull review' "$AGENTS"
grep -Fq 'Round 2を直前findingの修正差分と直接影響先に限定' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認時だけ、Round 2の未解決finding' "$AGENTS"
grep -Fq 'Round 1 is a full review' "$DELIVERY"
grep -Fq 'Round 2 receives only the prior findings' "$DELIVERY"
grep -Fq 'Round 2 receives only the prior findings, their fix delta, directly affected paths, the new fingerprint, the immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.' "$DELIVERY"
grep -Fq 'An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings, their fix delta, directly affected paths, the new full-scope fingerprint, the same immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.' "$DELIVERY"
grep -Fq 'do not send another complete diff' "$DELIVERY"
grep -Fq 'For Round 1 only, give the reviewer' "$DELIVERY"
grep -Fq 'For Round 2, send only the prior findings' "$DELIVERY"
grep -Fq 'For an explicitly approved Round 3, send only unresolved Round 2 findings' "$DELIVERY"
grep -Fq 'Round 3 requires explicit user approval; stop delivery after Round 3.' "$DELIVERY"
grep -Fq 'If P0-P2 remain, do not automatically create a new lifecycle.' "$DELIVERY"
grep -Fq 'Do not rerun successful implementation-side tests' "$DELIVERY"
grep -Fq 'Do not reread unchanged specifications, prior conversation, or prior tool output' "$DELIVERY"
grep -Fq 'P0-P2 block commit and PR creation' "$DELIVERY"
assert_absent 'Send the complete diff to the same saved agent as `Round N`' "$DELIVERY"
assert_absent '同じagentで修正後の全差分を再reviewする' "$AGENTS" "$POLICY"
assert_absent '4\. Give the reviewer only acceptance criteria' "$DELIVERY"
grep -Fq 'Round 1ではレビュアーにIssue/仕様、base、branch、完全なstaged対象、指紋、実行済みtestを渡す' "$AGENTS"
grep -Fq 'Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡だけ' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認後だけ、未解決finding' "$AGENTS"
grep -Fq 'Round 1 packet is the complete frozen scope' "$POLICY"
grep -Fq 'Round 2 and an explicitly authorized Round 3 packets remain bounded' "$POLICY"
grep -Fq 'Round 2 receives only the prior findings, the fix delta, directly affected paths, the new fingerprint, the immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.' "$POLICY"
grep -Fq 'An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings, the fix delta, directly affected paths, the new full-scope fingerprint, the same immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.' "$POLICY"
grep -Fq 'Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認後だけ、未解決finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡' "$AGENTS"
assert_absent 'Round 2 receives only the prior findings, (their )?fix delta, directly affected paths, the new fingerprint, and existing successful test evidence\.' "$DELIVERY" "$POLICY"
assert_absent 'An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings, (their )?fix delta, directly affected paths, the new full-scope fingerprint, and existing successful test evidence\.' "$DELIVERY" "$POLICY"
assert_absent 'For Round 2, send only the prior findings, fix delta, directly affected paths, new full-scope fingerprint, and existing successful test evidence;' "$DELIVERY"
assert_absent 'For an explicitly approved Round 3, send only unresolved Round 2 findings, fix delta, directly affected paths, new full-scope fingerprint, and existing successful test evidence\.' "$DELIVERY"
assert_absent 'Round 2 and an explicitly authorized Round 3 packets remain bounded: prior findings or unresolved Round 2 findings, the fix delta, directly affected paths, the new full-scope fingerprint, and existing successful test evidence only\.' "$POLICY"
assert_absent 'Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡だけを同じagentへ再提出する。' "$AGENTS" "$POLICY"
assert_absent 'Round 3はユーザーの明示承認後だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡に限定する。' "$AGENTS"
assert_absent 'Round 3はユーザーの明示承認時だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡に限定して実行する。' "$AGENTS"
for surface in "$POLICY" "$DELIVERY" "$AGENTS" "$REVIEWER"; do
  grep -Fq 'A new review lifecycle must not be started automatically after two completed review lifecycles in one unchanged delivery scope.' "$surface"
  grep -Fq 'Stop additional patch layering and require architecture/scope simplification plus an explicit user decision before any new lifecycle.' "$surface"
  grep -Fq 'An explicitly authorized Round 3 remains bounded and terminal; it must never trigger a fresh lifecycle.' "$surface"
  grep -Fq 'P0-P2 blockers must be grounded in a credible supported-use reproduction or a bounded code-path proof under the declared threat model and acceptance criteria.' "$surface"
  grep -Fq 'A runnable reproduction is not required when bounded proof exists.' "$surface"
  grep -Fq 'Purely theoretical or adversarial-local hardening outside supported use or the declared threat model is P3/residual risk unless the product explicitly supports hostile/multi-tenant conditions.' "$surface"
  grep -Fq 'Credible security/correctness risk remains blocking.' "$surface"
  grep -Fq 'Repeated P0-P2 findings in the same scope trigger architecture/acceptance-scope reconsideration, not additional defensive patches.' "$surface"
done
assert_absent 'automatically start a new review lifecycle after Round 3|automatically create a new lifecycle after two rounds|runnable reproduction is required for every P0-P2|theoretical or adversarial-local hardening is P0-P2' "$POLICY" "$DELIVERY" "$AGENTS" "$REVIEWER"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$AGENTS"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$POLICY"
grep -Fq 'Schema v2: expected task inventory is owner-only; `observer_tasks` is empty.' "$PARALLEL_CLEANUP"
grep -Fq 'Schema v1: expected task inventory is the owner plus exactly the already-registered observers.' "$PARALLEL_CLEANUP"
grep -Fq 'Every expected task must be cleanup-safe before Phase 1 candidate creation.' "$PARALLEL_CLEANUP"
grep -Fq 'Cleanup requires a registered owner task before candidate preparation or authorization.' "$PARALLEL_CLEANUP"
grep -Fq 'Cleanup operations require a registered owner task' "$PARALLEL_HELPER"
grep -Fq 'cleanup operations require a non-null owner_task_id' "$PARALLEL_SCHEMA"
grep -Fq 'ownerless cleanup is orphaned and read-only' "$PARALLEL_LIFECYCLE"
grep -Fq 'cleanup preparation/authorization/removal requires a registered owner' "$PARALLEL_ADAPTERS"
grep -Fq 'Schema v2 is owner-only' "$PARALLEL_LIFECYCLE"
grep -Fq 'schema v1 is owner plus exactly the already-registered observer desktop tasks' "$PARALLEL_ADAPTERS"
grep -Fq 'Implementation planning/TDD uses the coordinator-owned saved `implementer_luna`' "$ISSUE_START"
grep -Fq '`is` Git/GitHub discovery, target resolution, and command preparation use the saved `git_operator_luna`' "$ISSUE_START"
grep -Fq 'Have the saved `git_operator_luna` inspect and prepare Git/GitHub startup operations' "$ISSUE_START"
grep -Fq 'Hand implementation planning/TDD to the coordinator' "$ISSUE_START"
grep -Fq 'Hand implementation planning/TDD to the coordinator-owned saved `implementer_luna`' "$ISSUE_START"
assert_absent 'selected implementation agent' "$ISSUE_START"
grep -Fq 'type(schema_version) is not int' "$PARALLEL_HELPER"
grep -Fq 'validate_legacy_task_value' "$PARALLEL_HELPER"
assert_absent 'At `is` startup, ask the user to select GPT-5.6 Sol' "$ISSUE_START"
assert_absent 'switch the same task to GPT-5.6 Terra' "$ISSUE_START"
assert_absent 'Apply the planning model gate|apply the implementation model gate|## Model Gates' "$ISSUE_START"
cleanup_phase1=$(sed -n '/## Phase 1: Candidate Check/,/## Phase 2: Locked Revalidation/p' "$PARALLEL_CLEANUP")
if grep -Fq 'unpin/archive or detach observers before the owner' <<<"$cleanup_phase1"; then
  printf 'Phase 1 cleanup must remain read-only; observer mutation ordering leaked before approval.\n' >&2
  exit 1
fi
cleanup_phase2=$(sed -n '/## Phase 2: Locked Revalidation/,/## Codex-Managed/p' "$PARALLEL_CLEANUP")
grep -Fq 'For schema v1, only after `cleanup-authorize` succeeds, safely unpin/archive or detach observers before the owner' <<<"$cleanup_phase2"
grep -Fq 'unpin/archive the registered owner task last' <<<"$cleanup_phase2"
assert_absent '^2\. Transition to `cleanup_pending`|^5\. Transition to `archived`' "$PARALLEL_CLEANUP"
cleanup_authorize_line=$(grep -n 'Write the approved candidate ID' <<<"$cleanup_phase2" | cut -d: -f1)
observer_mutation_line=$(grep -n 'For schema v1, only after `cleanup-authorize` succeeds' <<<"$cleanup_phase2" | cut -d: -f1)
remove_line=$(grep -n 'Then remove the worktree\.' <<<"$cleanup_phase2" | cut -d: -f1)
branch_evidence_line=$(grep -n 'branch deletion/attempt evidence' <<<"$cleanup_phase2" | cut -d: -f1)
owner_mutation_line=$(grep -n 'unpin/archive the registered owner task last' <<<"$cleanup_phase2" | cut -d: -f1)
final_inventory_line=$(grep -n 'Generate the final exact-cwd inventory' <<<"$cleanup_phase2" | cut -d: -f1)
if (( observer_mutation_line <= cleanup_authorize_line || remove_line <= observer_mutation_line || branch_evidence_line <= remove_line || owner_mutation_line <= branch_evidence_line || final_inventory_line <= owner_mutation_line )); then
  printf 'Cleanup ordering must be authorize -> observers -> remove -> branch evidence -> owner -> final inventory.\n' >&2
  exit 1
fi
if grep -Fq '| R1 | CSS, colors, spacing, static markup with no behavioral bindings | Skip |' "$DELIVERY"; then
  printf 'Unexpected legacy R1 skip route in delivery policy.\n' >&2
  exit 1
fi
assert_absent 'R0 / R1は独立AI review不要' "$POLICY" "$AGENTS"

# PR evidence lifecycle and UI distribution contract.
grep -Fq 'User-visible UI changes require PR video evidence' "$POLICY"
grep -Fq 'Screenshots are optional supplements' "$POLICY"
grep -Fq 'Backend, configuration, and documentation-only changes are excluded' "$POLICY"
grep -Fq 'If the privacy or' "$POLICY"
grep -Fq 'The `implementer_luna` coordinates browser-verification readiness' "$POLICY"
grep -Fq 'makes the final presentation, privacy, or upload decision' "$POLICY"
grep -Fq '`verifier_luna` performs the browser behavior check and captures a local raw recording only after' "$POLICY"
grep -Fq '`verifier_luna` captures local evidence at a coherent checkpoint only' "$AGENTS"
assert_absent '`verifier_luna` performs the coherent-checkpoint browser behavior check and captures a local raw recording.' "$POLICY" "$AGENTS"
grep -Fq 'Unreadable at PR width selects zoom' "$POLICY"
grep -Fq 'Before/after switching selects comparison' "$POLICY"
grep -Fq 'Purpose or result unclear selects captions' "$POLICY"
grep -Fq 'OR selects remotion; all false selects raw' "$POLICY"
grep -Fq 'calls `$pr-evidence-video`' "$POLICY"
grep -Fq 'visually privacy-reviews notification, URL, user, token' "$POLICY"
grep -Fq 'The Coordinator owns the final' "$POLICY"
grep -Fq 'explicit user override wins only within the safety contract' "$POLICY"
grep -Fq 'The `reviewer_luna` evidence-only lifecycle' "$DELIVERY"
grep -Fq 'exact artifact, SHA-256 hash, manifest, and contact frame' "$DELIVERY"
grep -Fq 'plus behavior coverage, target' "$DELIVERY"
grep -Fq 'must not judge styling, rerender, inspect' "$DELIVERY"
grep -Fq 'does not replace or contaminate completion review' "$DELIVERY"
grep -Fq 'final PR evidence is revalidated after commit' "$POLICY"
grep -Fq 'fingerprint change invalidates evidence and stops upload' "$POLICY"
grep -Fq '`pr_number` may remain null until the PR' "$POLICY"
grep -Fq '`git_operator_luna` prepares the exact Git target' "$POLICY"
grep -Fq 'Conversation upload is browser/UI-only' "$POLICY"
grep -Fq 'No API or gh pretend upload is allowed' "$POLICY"
grep -Fq 'Coordinator performs the browser/UI upload' "$HANDOFF"
grep -Fq 'operator prepares only the target and hash' "$HANDOFF"
assert_absent 'GitHub UI upload is prohibited' "$HANDOFF"
assert_absent 'approved GitHub/API or CLI route' "$HANDOFF"
assert_absent 'use the approved GitHub/API or CLI' "$HANDOFF"
grep -Fq '`PRまで` authorizes only the exact' "$DELIVERY"
grep -Fq 'Different, reencoded, replacement,' "$DELIVERY"
grep -Fq 'external-storage, or other-PR artifacts require new authorization' "$DELIVERY"
grep -Fq 'If upload is impossible, stop' "$DELIVERY"
grep -Fq 'update handoff status and URL only after exact upload' "$DELIVERY"
grep -Fq '## Visual Evidence' "$DELIVERY"
grep -Fq 'Not required (non-user-visible change)' "$DELIVERY"
grep -Fq 'browser verification of the happy path and one or two likely edge paths only after explicit human UI/behavior acceptance evidence' "$DELIVERY"
grep -Fq 'may require network and browser-launch approval' "$POLICY"
grep -Fq '`verifier_luna` remains GPT-5.6 Luna max' "$POLICY"
grep -Fq 'dotfiles/configuration change itself is non-user-visible and needs no video' "$POLICY"
grep -Fq 'pr-evidence-video' "$ROOT/setup.sh" "$ROOT/README.md"
grep -Fq 'installed at ~/.codex/skills/pr-evidence-video' "$ROOT/README.md"
grep -Fq 'Never install Remotion globally' "$ROOT/README.md"
grep -q 'evidence-only lifecycle' "$REVIEWER"
grep -q 'contact frame' "$REVIEWER"
grep -q 'must not judge styling, rerender, inspect' "$REVIEWER"
grep -q 'Never make the final presentation, privacy, or upload decision' "$IMPLEMENTER"
grep -q 'Call `\$pr-evidence-video`' "$VERIFIER"
grep -q 'visually privacy-review notification' "$VERIFIER"
grep -q 'browser-launch approval' "$VERIFIER"
grep -q 'never upload evidence through an API or gh' "$OPERATOR"
grep -q 'PRまで' "$OPERATOR"

# User-visible UI workflow order: implementation/IAB loops, explicit human
# acceptance, independent technical verification, then completion review.
UI_GATE_SURFACES=("$POLICY" "$DELIVERY" "$AGENTS" "$ROOT/README.md")
for surface in "${UI_GATE_SURFACES[@]}"; do
  grep -Fq 'User-visible UI workflow order' "$surface"
  grep -Fq '1. Implementation/IAB loop' "$surface"
  grep -Fq '2. Human UI/behavior acceptance' "$surface"
  grep -Fq '3. Verifier technical verification' "$surface"
  grep -Fq '4. Completion review' "$surface"
  grep -Fq 'Use explicit checkpoint/evidence wording; do not add a complex persisted state mechanism.' "$surface"
  grep -Fq 'Only a real human/user may provide explicit combined UI acceptance for appearance and primary behavior.' "$surface"
  grep -Fq 'The Coordinator records explicit human UI/behavior acceptance evidence tied to' "$surface"
  grep -Fq 'checkpoint_scope`.' "$surface"
  grep -Fq 'AI agents may not proxy or assume this acceptance.' "$surface"
  grep -Fq 'Do not start completion review during the implementation/IAB loop.' "$surface"
  grep -Fq 'Luna/max' "$surface"
  grep -Fq 'source before/after integrity' "$surface"
  grep -Fq 'Non-UI changes keep the existing flow.' "$surface"
  grep -Fq 'Purely non-user-visible verification artifact changes do not invalidate human acceptance.' "$surface"
  grep -Fq 'If verifier finds a problem or later source changes affect user-visible appearance or behavior, return to the same implementer/IAB loop and require combined human acceptance again before verifier.' "$surface"
  grep -Fq 'The Coordinator records an ephemeral `accepted_source_fingerprint` at acceptance time for the exact `checkpoint_scope`.' "$surface"
  grep -Fq 'The fingerprint covers source content plus staged/unstaged/untracked inventory.' "$surface"
  grep -Fq 'The acceptance-time accepted_source_fingerprint is read-only evidence.' "$surface"
  grep -Fq 'A mismatch invalidates the acceptance and returns to the same implementer/IAB loop and human gate.' "$surface"
  assert_absent 'completion review runs during the implementation/IAB loop' "$surface"
  assert_absent 'verifier_luna runs before human UI/behavior acceptance' "$surface"
  assert_absent 'accepted_source_fingerprint is optional' "$surface"
done

for surface in "${UI_GATE_SURFACES[@]}"; do
  assert_sequence "$surface" \
    '1. Implementation/IAB loop' \
    '2. Human UI/behavior acceptance' \
    '3. Verifier technical verification' \
    '4. Completion review'
done

grep -Fq 'keep iterating implementation, in-app browser (IAB) checks' "$IMPLEMENTER"
grep -Fq 'micro-adjustments in this same saved implementer loop' "$IMPLEMENTER"
grep -Fq 'present the exact candidate to a real human/user' "$IMPLEMENTER"
grep -Fq 'Do not start verifier_luna or' "$IMPLEMENTER"
grep -Fq 'reviewer_luna before explicit human UI/behavior acceptance' "$IMPLEMENTER"
grep -Fq 'Resume this same saved implementer agent for human feedback' "$IMPLEMENTER"
grep -Fq 'require explicit human UI/behavior acceptance tied to checkpoint_token' "$VERIFIER"
grep -Fq 'and checkpoint_scope before running final technical verification' "$VERIFIER"
grep -Fq 'For that UI path, do not run final' "$VERIFIER"
grep -Fq 'technical verification before explicit human UI/behavior acceptance.' "$VERIFIER"
grep -Fq 'Do not decide subjective' "$VERIFIER"
grep -Fq 'appearance or usability acceptance' "$VERIFIER"
grep -Fq 'Source changes that affect user-visible appearance' "$VERIFIER"
grep -Fq 'behavior invalidate the acceptance' "$VERIFIER"
grep -Fq 'verification artifacts alone do not' "$VERIFIER"
grep -Fq 'invalidate human acceptance.' "$VERIFIER"
grep -Fq 'verification before explicit human' "$VERIFIER"
assert_absent 'verifier_luna may accept UI/behavior on behalf of a human' "$VERIFIER"

# UI browser behavior and recording are post-acceptance verifier work only.
grep -Fq 'Before human acceptance for a user-visible UI change, verifier may only run non-mutating baseline, test-map, log-shape, or browser-plan checks.' "$VERIFIER"
grep -Fq 'Do not perform final browser behavior verification or capture a recording before human acceptance.' "$VERIFIER"
grep -Fq 'Only after the Coordinator records human UI/behavior acceptance evidence tied to checkpoint_token and checkpoint_scope may verifier perform final browser behavior verification or capture a recording.' "$VERIFIER"
grep -Fq 'For non-UI coherent checkpoints, no human UI/behavior acceptance or accepted_source_fingerprint is required; after checkpoint_token and checkpoint_scope are present and the implementer is paused, continue the existing targeted tests, log analysis, and objective verification flow.' "$VERIFIER"
grep -Fq 'For user-visible UI changes only, before starting final technical or browser verification, compare the acceptance-time `accepted_source_fingerprint`' "$VERIFIER"
grep -Fq 'For non-UI checkpoints, do not require human UI/behavior acceptance or accepted_source_fingerprint; use the existing targeted verification flow.' "$VERIFIER"
assert_absent 'Before human acceptance, verifier may only run non-mutating baseline, test-map, log-shape, or browser-plan checks\.' "$VERIFIER"
assert_absent '^Before starting final technical or browser verification, compare the acceptance-time `accepted_source_fingerprint` for the exact' "$VERIFIER"
assert_absent 'At a coherent checkpoint for a user-visible UI change, perform the browser behavior check and capture the local raw recording.' "$VERIFIER"

# Threat-model/supported-use declaration is immutable review-context evidence.
for surface in "$POLICY" "$DELIVERY" "$AGENTS"; do
  grep -Fq 'review_context_key includes the immutable `threat_model_supported_use_declaration_hash`.' "$surface"
  grep -Fq 'Round 1, Round 2, and an authorized Round 3 packet carry that same declaration/hash.' "$surface"
  grep -Fq 'A changed declaration/hash invalidates the current review context and requires a new context before submission; do not reuse stale bounded review evidence.' "$surface"
done
grep -Fq 'threat_model_supported_use_declaration_hash' "$DELIVERY"
grep -Fq 'threat_model_supported_use_declaration_hash' "$POLICY"
grep -Fq 'threat_model_supported_use_declaration_hash' "$AGENTS"
assert_absent 'review_context_key = acceptance_criteria + risk + target_files' "$DELIVERY"
assert_absent 'packets omit the threat model' "$POLICY" "$DELIVERY" "$AGENTS"

assert_sequence "$VERIFIER" \
  'Before human acceptance for a user-visible UI change, verifier may only run non-mutating baseline, test-map, log-shape, or browser-plan checks.' \
  'Only after the Coordinator records human UI/behavior acceptance evidence tied to checkpoint_token and checkpoint_scope may verifier perform final browser behavior verification or capture a recording.' \
  'Repeat the accepted_source_fingerprint comparison in before/after evidence.'

grep -Fq 'PR evidence skill link/unlink test passed.' <(bash "$ROOT/tests/setup-skills.sh")
[[ -d "$PR_EVIDENCE_SKILL" ]] || { printf 'PR evidence skill directory missing.\n' >&2; exit 1; }

printf 'Workflow review lifecycle policy test passed.\n'
