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
grep -Fq 'Never let `git_operator_luna` approve or review its own completion diff.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Do not use `reviewer_luna` for operator work.' "$ROOT/codex/skills/git-workflow/SKILL.md"
grep -Fq 'Completion review: use the existing `git-workflow` R0-R4 review mapping.' "$PARALLEL_SKILL"
grep -Fq '| R0 | Sol medium | Terra medium | Skip |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R1 | Sol medium | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R2 | Sol high | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq '| R3-R4 | Sol xhigh | Terra medium | Fresh-context `reviewer_luna`: Luna `max`, read-only |' "$PARALLEL_LIFECYCLE"
grep -Fq 'SCHEMA_VERSION = 2' "$PARALLEL_HELPER"
grep -Fq 'Legacy v1 registries remain readable for status, resume, and cleanup recovery' "$PARALLEL_LIFECYCLE"
grep -Fq 'New v2 registries require an empty `observer_tasks` compatibility field' "$PARALLEL_ADAPTERS"
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

printf 'Workflow review lifecycle policy test passed.\n'
