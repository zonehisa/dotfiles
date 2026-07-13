# Delivery And Independent Review

## Final review gate

Run once after implementation/user-feedback loops are verified, or at explicit review, completion, `cm`, or `pr`. R0 may use `not_required`; R1-R4 require a new independent Codex task with the shared policy's model/effort.

1. Inspect all staged, unstaged, untracked, and submodule changes.
2. Run `review_fingerprint.py --base <base-ref>` and freeze the complete diff and returned artifact hash.
3. Send only Issue/acceptance criteria, repository/base/head, changed paths, fingerprint, and tests to the reviewer. Do not pass the implementation conclusion.
4. Require findings-first P0-P3 review. Classify findings as accepted, rejected, or needs-user-decision.
5. Add the smallest regression test/sensor before accepted non-trivial fixes when feasible.
6. Batch fixes, verify, freeze once, and re-use the same review task. P0-P2 must be zero.
7. Any non-trivial post-review diff invalidates approval. For typo/comment/obvious formatting only, show the delta and obtain explicit user confirmation before re-freezing.
8. If a fresh review task cannot be created/read, stop the completion/commit/PR gate and ask the user to create it.

Record risk, reviewer task/model, fingerprint, rounds, unique findings, classifications, tests/sensors, verification, and unverified scope.

## Commit (`cm`)

1. Require `not_required` with confirmed R0, or `approved` with a reviewer task ID, review timestamp, and matching current artifact hash. Stop for missing evidence, `pending`, `stale`, or mismatch.
2. Inspect status/diffs and stage only relevant files.
3. Present changed files, verification, review evidence, and repository-style commit message.
4. Commit only after confirmation; do not push.
5. Capture the pre-commit content hash. After commit, recompute with the pre-commit HEAD as `--content-base`; require matching content hash and a clean tree before binding the clean commit artifact hash to review state.
6. If hooks changed content, mark review stale and stop without rewriting history.

## Pull request (`pr`)

1. Require a clean tree and valid `not_required` R0 or `approved` with reviewer task ID, review timestamp, and matching clean-commit artifact hash.
2. Verify repository, base, branch, Issue, state, commit log, diff, and existing PRs identify the same work.
3. Stop on mismatch or an existing PR for the same head.
4. Present title/body with Summary, Changes, Related Issue, Tests, Manual Verification, and unverified scope.
5. After confirmation, push the verified branch and create the PR. Never merge automatically.
6. Report the URL and stop.
