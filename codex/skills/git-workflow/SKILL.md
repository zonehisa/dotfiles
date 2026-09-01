---
name: git-workflow
description: "General Git and GitHub workflow guidance for Codex. Use for creating or triaging Issues, starting Issue work, branches, commits, pull requests, reviews, and review fixes. Shorthands: ic, is, cm, pr, prr, prf."
---

# Git Workflow

Handle Git and GitHub work using repository conventions discovered at runtime.

## Core Rules

- Treat existing changes as user work; never revert unrelated changes.
- Never commit, push, create a PR, post a review, merge, or clean up resources without explicit user authorization.
- Authorization may be scoped to a delivery bundle. `PRまで` or an equivalent explicit request authorizes commit, push, and PR creation for the same reviewed fingerprint and verified target without another pause between those steps. It never authorizes merge.
- `cleanup` after merge/deploy authorizes one safety-checked batch for dedicated environments, merged worktrees, and branches. Preserve dirty worktrees and commits that are neither reachable nor patch-equivalent to the merged target.
- Keep one fresh-context `reviewer_luna` agent per repository/Issue-or-branch/base/reviewer-role lifecycle for every R1-R4 review. Skip a round only when its patch, acceptance criteria, risk, and target files are unchanged; otherwise reuse the saved agent for the next numbered round.
- Read repository `AGENTS.md`, `README.md`, contributing docs, and relevant local skills before acting.
- Detect the repository, default branch, conventions, labels, test commands, and current state instead of hardcoding them.
- Stop and ask one narrow question only when the next action could damage user work, publish externally, or target the wrong Issue/PR.
- Batch low-risk, reversible, and repository-pattern decisions with concrete acceptance criteria into one recommended plan. Use one-question dig only for unresolved material decisions; still require direction for external, destructive, new-repository, authorization, material product, or scope decisions.
- Coordinator wait contract: perform one long event wait per delegated stage; after a timeout or attention signal, take at most one timeout/attention snapshot. Never poll unchanged state periodically; report only stage changes or a required sparse ongoing update.
- Delegate Git/GitHub discovery, target resolution, command preparation, and non-approval-bound execution (except the R1-R4 completion gate) to one `git_operator_luna` subagent per repository/Issue-or-branch lifecycle. Spawn it with `fork_turns = "none"` and a minimal context packet containing the requested operation, repository, Issue/branch/base, current state, and authorization scope; reuse the same saved operator agent for later approvals and follow-ups.
- If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.
- Keep user communication and authorization decisions in the coordinator. Treat permissions omitted from the operator context packet as not granted.
- When a mutating command needs runtime escalation tied to explicit user authorization, the operator must stop before requesting escalation and return the exact command, resolved targets, expected effects, and verification steps. After checking that this matches the user's direct authorization, the coordinator executes that exact approval-bound command so the approval layer receives the original user message. Do not relay quoted approval text to an isolated operator or ask it to request escalation; relayed agent text is not trusted user authorization.
- The coordinator must not broaden, rewrite, or improvise the returned mutation. If the exact command is unsafe, stale, incomplete, or exceeds authorization, send it back to the saved operator for correction. If the operator itself is unavailable, stop the workflow instead of substituting another model.
- Never let `git_operator_luna` approve or review its own completion diff. Use a separate fresh-context `reviewer_luna` agent for the completion gate and keep its evidence distinct from the operator lifecycle.
- Keep the configured global default unless the user changes it. For Issue work, Git/GitHub operations, and completion review, follow the phase and risk-based model routing in the selected reference.
- Use the scoped `reviewer_luna` subagent for every R1-R4 completion gate, with no inherited implementation turns. Do not use `reviewer_luna` for operator work.
- Do not recommend or perform merge while required CI checks are pending or failing. This gate has no conversational override.
- When a task is owned by an active `parallel-worktree` registry/context packet, keep read-only Git inspection here but route every mutating Git operation through that skill's `pw-helper`. Never bypass its operation ID, ownership, scope, lock, or cleanup checks.

## Route to One Reference

Read only the reference required for the current operation. Do not preload the others.

- Create or triage an Issue, or `ic`: read [references/issues.md](references/issues.md).
- Start Issue work, create its branch, plan it, or `is`: read [references/issue-start.md](references/issue-start.md).
- Commit, prepare/create a PR, or run the risk-routed completion gate (`cm`, `pr`, explicit review, or completion): read [references/delivery.md](references/delivery.md).
- Review a PR/local diff or address review feedback (`prr`, `prf`): read [references/code-review.md](references/code-review.md).

For user-visible UI delivery, also apply the PR Evidence Lifecycle in
[references/delivery.md](references/delivery.md). Keep evidence review separate from completion
diff review and do not upload through an API or `gh`.

When a request spans operations, read the references in execution order, loading each only when that operation begins. For example, `is` followed later by `cm` starts with `issue-start.md` and defers `delivery.md` until commit is requested.

## Minimal Context Detection

Run only the checks needed for the selected operation:

```bash
git status --short
git branch --show-current
git remote get-url origin
gh repo view --json nameWithOwner,defaultBranchRef,url
```

Prefer `rg` when searching repository conventions. If browser verification is needed, read the available browser-control skill before controlling a browser.
