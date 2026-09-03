# Start Issue Work

Use this reference only when starting or triaging work for a specific Issue. Keep the normal path
small: the Coordinator/main owns local inspection, planning, implementation, and targeted tests.

## Defaults

- Keep the configured global model default unless the user explicitly changes it.
- Read the repository status, current branch, remotes, Issue, relevant specifications, and tests
  directly in the Coordinator/main context. Do not spawn `git_operator_luna` merely for reads.
- A clean, single, foreground task stays in the current checkout and does not require a Worktree or
  `implementer_luna` child.
- Use a Worktree only for parallel work, a dirty primary checkout, background/long-running work, or
  explicit isolation. Read [parallel-worktree](../../parallel-worktree/SKILL.md) when that condition applies.

## Conditional roles

- Use the saved `git_operator_luna` only for an explicitly authorized external Git/GitHub write such
  as Issue/PR creation, push, merge, or comment. Give it the exact repository, target, operation, and
  authorization; an unavailable operator stops that external-write operation.
- Use the saved `implementer_luna` only when the Coordinator explicitly selects parallel, dirty,
  background/long-running, isolated, or explicitly delegated high-risk implementation. It is then the
  sole source writer for that isolated lifecycle and must not delegate further.
- Use `explorer_luna` or `verifier_luna` only for their bounded read-only roles when the selected
  lifecycle needs them. Completion review remains the separate fresh-context `reviewer_luna` gate.

## Workflow

1. Run `git status --short`, identify staged/unstaged/untracked work, and preserve unrelated changes.
2. Resolve the Issue and repository target, then inspect the relevant code, policy, and tests before
   asking questions. Use at most three related Issues only when the relationship is strong and useful.
3. Select the current-checkout default or the conditional Worktree/role route above. Do not switch a
   dirty checkout or overwrite another lifecycle's files.
4. Use Plan/TDD for workflow changes: state scope, success criteria, acceptance scenarios, risks, and
   targeted tests. Use one-question dig only for an unresolved material decision.
5. Implement the smallest change in the selected writer context and run targeted tests. For UI, follow
   `delivery.md`: Coordinator-owned IAB evidence, verifier before human acceptance, review, then one
   final IAB plus human appearance/primary-behavior acceptance.
6. Save required Issue context only when repository conventions require it. Do not commit, push, merge,
   or create a PR from this reference; those are separate explicitly authorized delivery operations.
7. Report the Issue, branch or checkout, changed paths, tests, and unresolved decisions.

If the current mode prohibits a local mutation, complete investigation and planning first, then resume
in an execution-capable mode. Missing authorization is never inferred from the Issue or branch name.

Useful commands:

```bash
git status --short
git branch --show-current
gh issue view <number> --repo <owner/repo>
git fetch origin
git checkout -b <branch-name> origin/<default-branch>
```
