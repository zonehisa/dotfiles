# Delivery Workflows

## Independent Diff Review Gate

Run this gate once after implementation and user-feedback iterations are verified, when the user explicitly requests review, or immediately before completion, commit, or PR preparation. Do not run it after every TDD or UI-adjustment loop. Skip only typo, copy, comment, or obvious formatting-only changes.

### Review Risk Rank

Classify the complete frozen diff before creating the review task. For mixed changes, use the highest applicable rank.

| Rank | Typical changes | Independent review |
|---|---|---|
| R0 | Copy, comments, obvious formatting only | Skip |
| R1 | CSS, colors, spacing, static markup with no behavioral bindings | GPT-5.6 Luna, `high` |
| R2 | Hover/focus/click behavior, JavaScript/Alpine, reactive bindings, display conditions | GPT-5.6 Terra, `high` |
| R3 | Persistence, queries, state transitions, authorization, public contracts/APIs | GPT-5.6 Sol, `high` |
| R4 | Security boundaries, credible data-loss/corruption risk, concurrency/locking, critical incidents | GPT-5.6 Sol, `xhigh` |

Do not rank a change as R1 merely because it is presented as UI work: events, bindings, conditions, navigation behavior, or data access make it R2 or higher. Record the selected rank and reason in the review evidence.

If the reviewer discovers a higher-risk class, continue the same review task with the higher rank's model and reasoning effort and require review of the full frozen diff again. Do not create another task solely for escalation. Never automatically downgrade a review rank.

1. Run `git status --short` and `scripts/review_fingerprint.py --base <base-ref>`. Freeze all staged, unstaged, and untracked changes plus the returned fingerprint. Review dirty submodules separately first.
2. Create a new independent Codex task in the same project using the selected review rank's model and reasoning effort. Do not fork the implementation task or substitute self-review/subagents.
3. Give it only acceptance criteria, repository/base/branch, the complete frozen-diff scope, exact fingerprint, and checks already run. Do not include implementation conclusions or suspected safe areas.
4. Require concise, read-only, findings-first P0-P3 output with file/line evidence. Prioritize correctness, regression, contracts, state transitions, locking/authorization, security/privacy, performance, maintainability, and missing tests. Do not restate satisfied requirements or unchanged code.
5. Require the final output to repeat the fingerprint. A no-findings result contains only fingerprint, severity counts, residual risks, and unverified areas.
6. Classify every finding as accepted, rejected with evidence, or requiring user input.
7. Batch accepted P0-P2 fixes, adding the smallest regression test/sensor first when feasible, then run the nearest verification. Treat P3 as advisory and defer it unless it violates acceptance criteria or the user explicitly includes it.
8. Freeze a new fingerprint once after the fix batch and ask the same review task to re-review. Repeat until no P0-P2 remains; do not re-review solely for deferred P3.
9. If independent task creation/reading is unavailable, stop the completion/commit/PR gate and ask the user to create it.
10. Immediately before commit, recompute the fingerprint. Any change requires re-review. After commit, run the fingerprint script with `--content-base <reviewed-head>` and require a clean tree and matching content hash before tying the commit SHA to review evidence.
11. Immediately before PR creation, require a clean tree, matching base, and either the reviewed clean-state HEAD or the commit SHA recorded directly after the reviewed working-tree commit. Additional/amended commits or base movement require re-review.
12. User feedback or code changes after review invalidate the reviewed state; finish the new batch and run one final review at the next review/completion/commit/PR boundary.

Report the review rank and reason, review task, model/reasoning effort, fingerprint, reviewed commit when applicable, rounds, unique findings, classification counts, promoted tests/sensors, verification, and unverified scope. Promote project-specific defect classes to tests or `HARNESS.md`; record escaped reviewed defects in `RETRO.md`.

## Commit

1. Require a passed independent gate with no unresolved P0-P2 for non-trivial changes.
2. Inspect status, staged/unstaged diffs, and recent commit conventions.
3. Stage only relevant files and split unrelated or formatting-only work. In an active `parallel-worktree` lifecycle, request `pw-helper stage-scope` instead of running `git add` directly.
4. Use repository commit conventions, falling back to `<type>(<scope>): <subject>`.
5. Commit only with explicit authorization; report SHA, message, verification, and review evidence. In an active `parallel-worktree` lifecycle, save the approved message in its private registry message directory and request `pw-helper commit`; never run `git commit` directly.

## Create a Pull Request

1. Require a passed independent gate with no unresolved P0-P2 and a clean working tree.
2. Verify repository, base, branch, Issue target, state file, commit log, diff, and existing PRs all identify the same work. Ignore stale state files whose saved branch differs.
3. Stop on target mismatch or an existing PR for the same head branch.
4. Run the nearest relevant tests. For user-visible workflow changes, run browser verification of the happy path and one or two likely edge paths.
5. Include only checks actually run. Add compact Mermaid diagrams or safe screenshots/video only when they materially aid review; durable behavior belongs in project specs too.
6. Push and create the PR only with explicit authorization. Use `Closes #...` only for the verified target Issue. In an active `parallel-worktree` lifecycle, request `pw-helper push` and use its registered repo/base/head evidence for PR creation; never push an arbitrary ref directly.
7. Report the PR URL and stop.

Suggested PR sections: Summary, Changes, Related Issues, Tests, Manual Verification, and Evidence. Never expose secrets or private customer data in evidence.
