#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY="$ROOT/policies/development-workflow.md"
DELIVERY="$ROOT/codex/skills/git-workflow/references/delivery.md"
AGENTS="$ROOT/codex/AGENTS.md"

for marker in review_lifecycle_key review_round_key review_context_key; do
  grep -q "$marker" "$POLICY"
  grep -q "$marker" "$DELIVERY"
done

grep -q 'Review <repository> #<issue-or-branch>' "$DELIVERY"
grep -q 'otherwise choose the earliest-created exact lifecycle match' "$DELIVERY"
grep -q 'never send them another request' "$DELIVERY"
grep -q 'both round and context keys are unchanged' "$DELIVERY"
grep -q 'no duplicate sends' "$POLICY"
grep -q 'Collect canonical result' "$POLICY"
grep -q 'result-uncollected' "$POLICY"
grep -q '完全一致する最古taskを正本' "$AGENTS"
grep -q '完了review taskと完了済み重複taskをarchive' "$AGENTS"
grep -q 'Report reused, duplicate, and archived task counts' "$DELIVERY"

# v1.1-lite applies only to new lifecycles and keeps review bounded and diff-focused.
grep -Fq 'v1.1-liteは適用開始後に作成する新規review lifecycleだけを対象' "$POLICY"
grep -Fq 'R0 / R1は独立AI reviewを不要' "$POLICY"
grep -Fq '| R1 | CSS、色、余白、behavioral bindingのない静的markup | Sol medium | Terra medium | 不要 |' "$POLICY"
grep -Fq 'Round 1はreview対象全体のfull review' "$POLICY"
grep -Fq 'Round 2は直前findingの修正差分と直接影響先だけ' "$POLICY"
grep -Fq '通常は最大2Round' "$POLICY"
grep -Fq 'Round 3はユーザーが明示承認した場合だけ' "$POLICY"
grep -Fq 'Round 3後もP0〜P2が残る場合は配送を停止し、自動で新規lifecycleを作らない。' "$POLICY"
grep -Fq '成功済みtestをreviewerが再実行しない' "$POLICY"
grep -Fq '不変仕様、過去会話、過去tool outputを再読しない' "$POLICY"
grep -Fq 'P0〜P2が残る間はcommit / PRを禁止' "$POLICY"
grep -Fq '既存のreview_fingerprint.pyだけを使用' "$POLICY"

grep -Fq 'Round 1 is a full review' "$DELIVERY"
grep -Fq 'Round 2 receives only the prior findings' "$DELIVERY"
grep -Fq '| R1 | CSS, colors, spacing, static markup with no behavioral bindings | Skip |' "$DELIVERY"
grep -Fq 'Round 3 requires explicit user approval' "$DELIVERY"
grep -Fq 'If P0-P2 remain after Round 3, stop delivery. Do not automatically create a new lifecycle.' "$DELIVERY"
grep -Fq 'If a higher-risk class is discovered during Round 2, stop and require explicit user approval before a full Round 3.' "$DELIVERY"
grep -Fq 'Do not rerun successful implementation-side tests' "$DELIVERY"
grep -Fq 'Do not reread unchanged specifications, prior conversation, or prior tool output' "$DELIVERY"
grep -Fq 'P0-P2 block commit and PR creation' "$DELIVERY"

grep -Fq 'R0 / R1は独立AI review不要' "$AGENTS"
grep -Fq 'Round 2は前回findingの修正差分と直接影響先だけ' "$AGENTS"
grep -Fq 'Round 3はユーザーの明示承認時だけ' "$AGENTS"

if grep -Fq 'require review of the full frozen diff again' "$DELIVERY"; then
  printf 'Unbounded full rereview conflicts with the v1.1-lite Round 2 contract.\n' >&2
  exit 1
fi

printf 'Workflow review lifecycle policy test passed.\n'
