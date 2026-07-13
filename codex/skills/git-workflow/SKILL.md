---
name: git-workflow
description: "General Git and GitHub workflow guidance for Codex. Use for creating or triaging Issues, starting Issue work, branches/worktrees, commits, pull requests, reviews, and review fixes. Shorthands: ic, is, cm, pr, prr, prf."
---

# Git Workflow

Repository conventions and existing user work take priority over generic defaults.

## Core

- Read repository `AGENTS.md`, policy, README, and the selected repo-local Skill before acting.
- For risk, Plan/TDD, authorization, and review gates, read the repository's `.agent/policies/development-workflow.generated.md` when present. Otherwise read [references/development-workflow.md](references/development-workflow.md). When source hashes match, load only one copy.
- Detect repository, remote default, current branch/worktrees, state files, and dirty changes instead of hardcoding them.
- Never commit, push, create an Issue/PR, post a review, or merge beyond the authorization implied by the current shorthand.
- Do not use subagents only to reduce token use. Independent review requires a fresh Codex task.
- When an active `parallel-worktree` lifecycle owns the task, route every Git mutation through its helper and operation ID.

## Route

- `ic`, Issue create/triage: read [references/issues.md](references/issues.md).
- `is`, Issue start, branch/Worktree, Plan: read [references/issue-start.md](references/issue-start.md).
- `cm`, `pr`, completion, independent gate: read [references/delivery.md](references/delivery.md).
- `prr`, `prf`, local/PR review: read [references/code-review.md](references/code-review.md).

Load only the reference for the current operation. Stop after that operation; do not chain the next shorthand automatically.
