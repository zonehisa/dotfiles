# Code Review Workflows

## Review a PR or Local Diff

- Take a findings-first code-review stance.
- Prioritize bugs, regressions, security/privacy, authorization, data loss, state/contract mismatches, performance, and missing tests.
- Order findings P0-P3 and cite tight file/line evidence plus impact.
- Separate open questions from findings. If there are no findings, say so and state residual risks and unverified areas.
- Do not post a GitHub review or comment unless the user explicitly asks.

Useful commands:

```bash
gh pr view <PR> --json number,title,body,baseRefName,headRefName,files,additions,deletions
gh pr diff <PR>
git diff <default-branch>...HEAD --stat
git diff <default-branch>...HEAD
```

## Address Review Feedback

1. Fetch or read the exact review comments.
2. Classify each as bug/security, correctness/regression, test gap, maintainability, question, or optional/nit.
3. Verify each claim against code and tests before editing.
4. Fix one coherent batch at a time and add a focused regression test/sensor for accepted defects when feasible.
5. Run the nearest tests and formatting checks from repository docs.
6. Do not commit, push, reply, resolve, or request re-review without explicit authorization.
7. Report accepted/rejected/questions, changes, verification, and remaining risks.
