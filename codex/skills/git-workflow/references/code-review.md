# Code Review

## Review (`prr`)

- Read the exact PR/local diff, Issue/Plan, base/head, tests, and relevant repository rules.
- Stay read-only and report findings first, ordered P0 to P3, with file/line, impact, reproduction, and smallest useful fix.
- Prioritize correctness, regressions, contracts, state transitions, authorization, security/privacy, performance, maintainability, and missing tests.
- If there are no findings, say so briefly and list unverified scope.
- Present any GitHub review/comment body before posting. Post only after explicit confirmation.

## Address feedback (`prf`)

1. Fetch/read exact comments and current diff.
2. Classify each finding as accepted, rejected, or needs clarification.
3. Add a regression test/sensor first for accepted non-trivial defects when feasible.
4. Apply the smallest fix and run the nearest verification.
5. Any non-trivial change invalidates review approval and returns to the same independent task.
6. Report disposition and verification. Do not commit, push, reply, resolve, or request re-review without separate authorization.
