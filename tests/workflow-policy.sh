#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY="$ROOT/policies/development-workflow.md"
DELIVERY="$ROOT/codex/skills/git-workflow/references/delivery.md"
AGENTS="$ROOT/codex/AGENTS.md"
REVIEWER="$ROOT/codex/agents/reviewer-luna.toml"
OPERATOR="$ROOT/codex/agents/git-operator-luna.toml"
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
grep -Fq 'Require a passed risk-routed gate with `approved_subagent` and no unresolved P0-P2 for non-trivial changes.' "$DELIVERY"
grep -Fq 'Require a passed risk-routed gate with `not_required` or `approved_subagent`, no unresolved P0-P2, and a clean working tree.' "$DELIVERY"
grep -Fq 'run the risk-routed completion gate' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Delegate every `git-workflow` operation except the R1-R4 completion gate to one `git_operator_luna` subagent' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Spawn it with `fork_turns = "none"` and a minimal context packet' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'reuse the same saved operator agent for later approvals and follow-ups' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'If the operator is unavailable, stop the workflow instead of executing it in the coordinator or another model.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Never let `git_operator_luna` approve or review its own completion diff.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Do not use `reviewer_luna` for operator work.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Completion review: use the existing `git-workflow` R0-R4 review mapping.' "$PARALLEL_SKILL"
grep -Fq '| R0 | Sol medium | Terra medium | Skip |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R1 | Sol medium | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R2 | Sol high | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R3-R4 | Sol xhigh | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq 'SCHEMA_VERSION = 2' "$PARALLEL_HELPER"
grep -Fq 'Legacy v1 registries remain readable for status, resume, and cleanup recovery' "$PARALLEL_LIFECYCLE"
grep -Fq 'Schema v2 is owner-only' "$PARALLEL_ADAPTERS"
grep -q 'R1〜R4は、実装履歴を渡さないfresh-contextの`reviewer_luna`サブエージェント' "$AGENTS"
grep -Fq '`git-workflow`のcompletion review以外は`git_operator_luna`サブエージェント' "$AGENTS"
grep -q 'git_operator_luna.*Git workflowを止め' "$AGENTS"
grep -q 'Git workflow operator: agent_id per repository/Issue-or-branch lifecycle' "$POLICY"
grep -q 'operator自身のcompletion diffをreviewさせない' "$POLICY"
grep -q 'model = "gpt-5.6-luna"' "$REVIEWER"
grep -q 'model_reasoning_effort = "max"' "$REVIEWER"
assert_absent 'model_reasoning_effort = "high"' "$REVIEWER"
grep -q 'sandbox_mode = "read-only"' "$REVIEWER"
grep -q 'frozen R1-R4 staged diffs' "$REVIEWER"
grep -q 'Set review_valid to no' "$REVIEWER"
grep -q 'name = "git_operator_luna"' "$OPERATOR"
grep -q 'model = "gpt-5.6-luna"' "$OPERATOR"
grep -q 'model_reasoning_effort = "max"' "$OPERATOR"
grep -q 'sandbox_mode = "workspace-write"' "$OPERATOR"
grep -q 'Use the installed `git-workflow` skill' "$OPERATOR"
grep -q 'Treat any authorization omitted from the coordinator context packet as not granted' "$OPERATOR"
grep -q 'Never approve or review your own completion diff' "$OPERATOR"
grep -Fq 'If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.' "$OPERATOR"
assert_absent 'sandbox_mode = "read-only"' "$OPERATOR"
assert_absent 'sandbox_mode = "workspace-write"' "$REVIEWER"
assert_absent 'escalation_required' "$REVIEWER"
assert_absent 'R1以上は実装担当と別の新規Codex task' "$POLICY"
assert_absent 'substitute self-review/subagents' "$DELIVERY"
assert_absent 'passed independent gate' "$DELIVERY"
assert_absent 'independent completion gate' "$ROOT/codex/skills/git-workflow/SKILL.md"
assert_absent 'Independent review:' "$PARALLEL_SKILL"
assert_absent 'observer-add|Existing R[0-4].*policy' "$PARALLEL_HELPER" "$PARALLEL_SCHEMA" "$PARALLEL_LIFECYCLE" "$PARALLEL_CLEANUP" "$PARALLEL_ADAPTERS"
assert_absent 'independent (Codex )?(task|review)|独立(task|Codexタスク)|approved_independent|review\.task_id|Sol,? `(high|xhigh)`|GPT-5\.6 Sol|fall back to an independent task|fallbackする|escalat' "$POLICY" "$DELIVERY" "$AGENTS" "$REVIEWER" "$ROOT/codex/skills/git-workflow/SKILL.md"

grep -Fq 'These rules apply only to review lifecycles created after this policy' "$POLICY"
grep -Fq 'Round 1 is a full review of the complete frozen diff' "$POLICY"
grep -Fq 'Round 2 receives only prior findings' "$POLICY"
grep -Fq 'An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings' "$POLICY"
grep -Fq 'Review normally stops after two rounds' "$POLICY"
grep -Fq 'Round 3 requires explicit user approval; stop delivery after Round 3.' "$POLICY"
grep -Fq 'P0-P2 block commit and PR creation' "$POLICY"
grep -Fq '新規review lifecycleではRound 1を全差分のfull review' "$AGENTS"
grep -Fq 'Round 2を直前findingの修正差分と直接影響先に限定' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認時だけ、Round 2の未解決finding' "$AGENTS"
grep -Fq 'Round 1 is a full review' "$DELIVERY"
grep -Fq 'Round 2 receives only the prior findings' "$DELIVERY"
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
grep -Fq 'Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡だけ' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認後だけ、Round 2の未解決finding' "$AGENTS"
grep -Fq 'Round 1 packet is the complete frozen scope' "$POLICY"
grep -Fq 'Round 2 and an explicitly authorized Round 3 packets remain bounded' "$POLICY"
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
grep -Fq 'Implementation-agent/model selection belongs to the implementation workflow outside this Git operator role and must not mutate or re-delegate the saved operator lifecycle.' "$ISSUE_START"
grep -Fq '`is` Git/GitHub operations use the saved `git_operator_luna`' "$ISSUE_START"
grep -Fq 'Execute Git/GitHub startup operations directly through the saved `git_operator_luna`' "$ISSUE_START"
grep -Fq 'Hand implementation planning/TDD to the coordinator' "$ISSUE_START"
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

printf 'Workflow review lifecycle policy test passed.\n'
