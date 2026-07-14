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

printf 'Workflow review lifecycle policy test passed.\n'
