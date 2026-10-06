# Start Issue Work

Use this reference only when starting or triaging work for a specific Issue. R0 stays small and direct;
R1-R4 implementation starts in an Issue-dedicated Worktree from the latest remote default branch.

## Defaults

- Keep the configured global model default unless the user explicitly changes it.
- Read the repository status, current branch, remotes, Issue, relevant specifications, and tests
  directly in the Coordinator/main context. Do not spawn `git_operator_luna` merely for reads.
- R0 copy/comment/obvious-formatting work may stay in the current clean checkout without a Worktree.
- R1-R4 work uses a dedicated Worktree by default. Run `git fetch origin` once, resolve the remote default
  branch, freeze `origin/<default-branch>` as the base, and keep the primary checkout read-only. Read
  [parallel-worktree](../../parallel-worktree/SKILL.md) for the provisioning lifecycle.
- Worktree selection does not create an independent Codex task or require `implementer_luna`; the Coordinator
  may implement directly in the selected Worktree. Reuse the same Worktree when resuming the Issue lifecycle.

## Freeze the request contract

Before any work begins—including Coordinator-only implementation, Worktree provisioning, source edits, or child dispatch—record this short contract:

```text
Issue / repository / base (freeze the base SHA after fetch):
Objective:
Writable paths:
Acceptance criteria (observable):
Out of scope:
Risk and reason:
Budget (tokens / tool calls / retries; set concrete limits before any work begins):
Output (changed paths / checks and results / unresolved items):
```

Use the same acceptance criteria for the Issue preflight and the completion review; do not create a
second divergent criteria list after implementation. Keep the normal Coordinator-only path single-agent.
If a child is justified by independent work, freeze its allowed tools, write scope, budget, success
criteria, and output format in its handoff before dispatch. Existing reviewer, risk, approval, and
Worktree rules still apply.

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
3. For an Issue-linked implementation, run the [Issue preflight](issue-preflight.md) collect/assessment flow:
   re-fetch the live origin target and Issue/related-PR context, bind each explicit requirement assessment to
   the current target SHA and Issue hash, and preserve the recorded creation base. `satisfied` stops edits/PR;
   `unknown` permits read-only investigation only; start implementation only for confirmed `needs_work`.
4. For R1-R4, provision or resume the Issue-dedicated Worktree from the frozen remote base and verify its
   realpath/branch before any source edit. For R0, use only a clean checkout. Never switch a dirty checkout
   or overwrite another lifecycle's files.
5. Use Plan/TDD for workflow changes: state scope, success criteria, acceptance scenarios, risks, and
   targeted tests. Use one-question dig only for an unresolved material decision.
6. Implement the smallest change in the selected writer context and run targeted tests. For UI, follow
   `delivery.md` in this order: tests and technical verification -> completion review -> Coordinator
   final IAB -> verifier read-only packet check -> human appearance/primary-behavior acceptance.
7. Save required Issue context only when repository conventions require it. A fix/change request alone
   does not authorize staging or publication; continue read-only investigation, diff organization,
   non-staging review preparation, and tests until the staging gate. Do not commit, push, merge, or
   create a PR from this reference; those are separate explicitly authorized delivery operations.
8. Report the Issue, branch or checkout, changed paths, tests, and unresolved decisions.

If the current mode prohibits a local mutation, complete investigation and planning first, then resume
in an execution-capable mode. Missing authorization is never inferred from the Issue or branch name.

Useful commands:

```bash
git status --short
git branch --show-current
gh issue view <number> --repo <owner/repo>
git fetch origin
git worktree add <worktree-path> -b <branch-name> origin/<default-branch>
```
