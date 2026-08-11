# Delivery Workflows

## Risk-Routed Diff Review Gate

Run this gate once after implementation and user-feedback iterations are verified, when the user explicitly requests review, or immediately before completion, commit, or PR preparation. Do not run it after every TDD or UI-adjustment loop. Skip only typo, copy, comment, or obvious formatting-only changes.

### Review Risk Rank

Classify the complete frozen diff before spawning the review agent. For mixed changes, use the highest applicable rank.

| Rank | Typical changes | Review route |
|---|---|---|
| R0 | Copy, comments, obvious formatting only | Skip |
| R1 | CSS, colors, spacing, static markup with no behavioral bindings | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R2 | Hover/focus/click behavior, JavaScript/Alpine, reactive bindings, display conditions | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R3 | Persistence, queries, state transitions, authorization, public contracts/APIs | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R4 | Security boundaries, credible data-loss/corruption risk, concurrency/locking, critical incidents | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |

Do not rank a change as R1 merely because it is presented as UI work: events, bindings, conditions, navigation behavior, or data access make it R2 or higher. Record the selected rank and reason in the review evidence.

P0-P2 findings and a higher-risk classification do not change the review route. Incomplete full-diff coverage or a fingerprint mismatch invalidates the review instead of producing an approval. Never automatically downgrade a review rank.

### Bounded Review Rounds

- These rules apply only to review lifecycles created after this policy; do not rewrite an existing lifecycle.
- Round 1 is a full review of the complete frozen diff.
- Round 2 receives only the prior findings, their fix delta, directly affected paths, the new fingerprint, and existing successful test evidence.
- An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings, their fix delta, directly affected paths, the new full-scope fingerprint, and existing successful test evidence.
- Review normally stops after two rounds. Round 3 requires explicit user approval; stop delivery after Round 3. If P0-P2 remain, do not automatically create a new lifecycle.
- Use one `reviewer_luna` agent and the existing `review_fingerprint.py`; do not add another review-state mechanism.
- Do not rerun successful implementation-side tests. Do not reread unchanged specifications, prior conversation, or prior tool output.
- P0-P2 block commit and PR creation.

1. Run `git status --short`, stage the complete intended review scope only, then run `scripts/review_fingerprint.py --base <base-ref>`. The fingerprint represents the staged index; unstaged and untracked files are outside that review and must be reported and kept out of delivery. Freeze the staged paths plus `patch_base_tree` and `patch_hash`. Review dirty submodules separately first.
2. Build `review_lifecycle_key = repository + Issue/branch + base + reviewer_role`, `review_round_key = review_lifecycle_key + patch_base_tree + patch_hash`, and `review_context_key = acceptance_criteria + risk + target_files`. Skip submission only when both round and context keys are unchanged.
3. For every R1-R4 review, spawn the `reviewer_luna` role with `fork_turns = "none"`; never inherit the implementation conversation. Save its agent ID and send later `Round N` reviews to that same agent after a valid review. Create one new agent at the start of each lifecycle.
4. For Round 1 only, give the reviewer only acceptance criteria, repository/base/branch, the complete frozen-diff scope, exact fingerprint, and checks already run. For Round 2, send only the prior findings, fix delta, directly affected paths, new full-scope fingerprint, and existing successful test evidence; do not send another complete diff. For an explicitly approved Round 3, send only unresolved Round 2 findings, fix delta, directly affected paths, new full-scope fingerprint, and existing successful test evidence. Do not include implementation conclusions or suspected safe areas.
5. Require concise, read-only, findings-first P0-P3 output with file/line evidence. Prioritize correctness, regression, contracts, state transitions, locking/authorization, security/privacy, performance, maintainability, and missing tests. Do not restate satisfied requirements or unchanged code.
6. Require `review_valid = no` when the reviewer cannot access the complete frozen diff or cannot repeat the supplied fingerprint. Correct the review scope, restage and refreeze it, then discard the invalid review and replace it with a new fresh-context `reviewer_luna` agent for the lifecycle.
7. Ask the reviewer for a final-only response with no progress narration. Require the final output to repeat the fingerprint. A no-findings result contains only fingerprint, severity counts, `review_valid`, residual risks, and unverified areas. Wait once for the completion notification; do not repeatedly poll unchanged status.
8. Classify every finding as accepted, rejected with evidence, or requiring user input.
9. Batch accepted fixes, adding the smallest regression test/sensor first when feasible, then run the nearest verification. Treat P3 as advisory and defer it unless it violates acceptance criteria or the user explicitly includes it.
10. Restage the complete intended scope and freeze a new full-scope fingerprint once after the fix batch. For Round 2, send only the prior findings, fix delta, directly affected paths, full-scope fingerprint, and existing successful evidence to the same saved agent; do not send another complete diff. If Round 3 is explicitly approved, stop delivery after its final result; do not re-review solely for deferred P3.
11. If spawning, confirming, or reading the `reviewer_luna` subagent is unavailable, stop the completion/commit/PR gate. Do not fall back to another task, model, or self-review.
12. Immediately before commit, recompute the staged-tree fingerprint. Any staged-tree change requires re-review. After commit, run the fingerprint script with `--content-base <reviewed-head>` and require `index_matches_head`, a matching content hash, and no residual review-target changes before tying the commit SHA to review evidence.
13. Immediately before PR creation, require a clean tree, matching target, and either the reviewed clean-state HEAD or the commit SHA recorded directly after the reviewed working-tree commit. Additional or amended changes require re-review. A moved base does not require re-review only when the old reviewed and new fingerprints prove the same `patch_base_tree` and `patch_hash`, acceptance criteria and risk are unchanged, and both fingerprints are retained in the evidence; otherwise re-review.
14. User feedback or code changes after review invalidate the reviewed state; finish the new batch and run one final review at the next review/completion/commit/PR boundary.

Report the review rank and reason, route, reviewer agent ID, model/reasoning effort, fingerprint, reviewed commit when applicable, rounds, unique findings, classification counts, promoted tests/sensors, verification, and unverified scope. Promote project-specific defect classes to tests or `HARNESS.md`; record escaped reviewed defects in `RETRO.md`.

## Commit

1. Require a passed risk-routed gate with `approved_subagent` and no unresolved P0-P2 for non-trivial changes.
2. Inspect status, staged/unstaged diffs, and recent commit conventions.
3. Stage only relevant files and split unrelated or formatting-only work before freezing or verifying review evidence. In an active `parallel-worktree` lifecycle, request `pw-helper stage-scope` instead of running `git add` directly.
4. Use repository commit conventions, falling back to `<type>(<scope>): <subject>`.
5. Commit only with explicit authorization. A plain commit request stops after reporting SHA, message, verification, and review evidence. When the user explicitly authorized `PRまで`, continue through push and PR creation without another approval only while the reviewed fingerprint, target Issue, repository, base, and branch remain unchanged. In an active `parallel-worktree` lifecycle, save the approved message in its private registry message directory and request `pw-helper commit`; never run `git commit` directly.

## Create a Pull Request

1. Require a passed risk-routed gate with `not_required` or `approved_subagent`, no unresolved P0-P2, and a clean working tree.
2. Verify repository, base, branch, Issue target, state file, commit log, diff, and existing PRs all identify the same work. Ignore stale state files whose saved branch differs.
3. Stop on target mismatch or an existing PR for the same head branch.
4. Run the nearest relevant tests. For user-visible workflow changes, run browser verification of the happy path and one or two likely edge paths.
5. Include only checks actually run. Add compact Mermaid diagrams or safe screenshots/video only when they materially aid review; durable behavior belongs in project specs too.
6. Push and create the PR only with explicit authorization. `PRまで` is sufficient authorization for commit, push, and PR creation as one bundle for the exact reviewed scope; show concise progress but do not stop between steps. Use `Closes #...` only for the verified target Issue. In an active `parallel-worktree` lifecycle, request `pw-helper push` and use its registered repo/base/head evidence for PR creation; never push an arbitrary ref directly.
7. Report the PR URL and stop.

## Merge Readiness

- Do not recommend or perform merge until every required CI check reports success.
- Pending, missing, cancelled, or failing required checks keep the merge gate closed.

## Cleanup After Merge Or Deploy

An explicit cleanup request authorizes one batch after verifying the merge/deploy result:

1. Inspect all worktrees, branches, dedicated containers/volumes, and the primary checkout status.
2. Stop and remove only the task-dedicated runtime environment.
3. Remove only clean merged worktrees.
4. Delete branches whose commits are reachable from the target, or whose non-reachable commits are proven patch-equivalent to the merged commits. Preserve everything else and report why.
5. Re-list worktrees and remaining resources, then report the compact cleanup result.

Suggested PR sections: Summary, Changes, Related Issues, Tests, Manual Verification, and Evidence. Never expose secrets or private customer data in evidence.
