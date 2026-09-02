# Code Review Workflows

## External remote PR review (`prr`) versus completion review

`prr` has two explicit lanes. Reviewing another remote PR is an external review; reviewing the
current implementation before completion, commit, or PR preparation is the local completion gate.
The lanes must not share the completion gate's staged-index evidence.

### External remote PR lane

For an external PR, keep the review read-only and bind it to the exact local Git objects for the
repository, positive PR number, full base SHA, full head SHA, one unique merge-base, sorted changed
paths, and a deterministic canonical patch hash. The commits must already exist in the local object
database; stop when an object is missing, abbreviated/ambiguous, not a commit, unrelated (no merge
base), or has an ambiguous merge-base. The base does not have to be an ancestor of the head: an
advanced target branch is represented by the computed merge-base and the exact supplied base SHA.

Use the read-only helper with an exact target:

```bash
python3 codex/skills/git-workflow/scripts/external_pr_snapshot.py \
  --repo <repository> \
  --pr-number <number> \
  --base-sha <40-character-base-sha> \
  --head-sha <40-character-head-sha>
```

The helper is authoritative: it resolves the unique merge-base, reads its immutable tree and the
head tree, and emits the raw Git-object records needed for sorted paths and the canonical patch hash.
Do not reproduce its result with a hand-written `git diff` command or a remote/truncated patch. Raw
tree records avoid worktree attributes, checkout state, and nested submodule worktrees, so the result
depends only on committed objects; the helper never reads or mutates the worktree/index. It must not
call `review_fingerprint.py`, stage files, create an isolated checkout/source bundle, or use a remote
API as the patch source. An expected snapshot may be supplied to the helper for fail-closed identity
validation; any field mismatch stops the review.

When resolving a GitHub PR target, use the exact `baseRefOid` and `headRefOid` values for the PR
number and repository, then validate that both commits are present locally before invoking the
helper. Branch names, moving refs, abbreviated SHAs, and a truncated `gh pr diff` are not substitutes
for the bound snapshot; if exact metadata or objects cannot be obtained, stop.

The external lane has no persisted review-state store. Keep the same PR in its owning coordinator
Codex task when possible. An unchanged head with a fully matching snapshot needs no new reviewer;
retain the prior valid result and findings. When the head changes, compare prior unresolved finding
target paths and direct-impact identities first. If those relevant contents are unchanged and no
credible mitigation path exists, preserve the blockers without re-detecting them; review the new
delta and affected code. Deletions and renames never auto-clear a blocker. Reuse the same saved
reviewer only for a bounded `Round N` when that reviewer identity is still available in the same
task/lifecycle. A fork or new root cannot inherit, persist, or invent the child reviewer identity;
if it is unavailable, start a fresh lifecycle only when a new full review is actually required.

### Local completion lane

Completion review behavior remains unchanged: stage the complete intended local scope and run
`scripts/review_fingerprint.py --base <base-ref>`; the staged tree and its fingerprint are the
review source of truth. The external helper is not a replacement for this completion check, and the
completion lane must not use an external PR snapshot as its staged-tree evidence.

### Authorized PR comment boundary

Posting a PR comment remains an explicit user-authorized external write. The normal path has exactly
two operator stages: first, one head-bound structured preparation containing the repository, PR
number, exact head SHA, comment-body file and SHA-256, exact command, expected effects, and
verification; then, after the Coordinator executes that exact approval-bound command, one read-only
verification. There is no zero-hop bypass, third correction round, automatic retry, duplicate
correction, or third operator stage. Revalidate the exact head immediately before the write; a repository, PR, head, body hash,
command, or effect mismatch stops the operation rather than silently correcting it.

## Review a PR or Local Diff

- Take a findings-first code-review stance.
- Prioritize bugs, regressions, security/privacy, authorization, data loss, state/contract mismatches, performance, and missing tests.
- Order findings P0-P3 and cite tight file/line evidence plus impact.
- Separate open questions from findings. If there are no findings, say so and state residual risks and unverified areas.
- Do not post a GitHub review or comment unless the user explicitly asks.

Useful discovery/triage commands (non-authoritative only; never use their output as completion or
external review evidence):

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
