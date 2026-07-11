---
name: git-workflow
description: "General Git and GitHub workflow guidance for Codex. Use for creating or triaging Issues, starting Issue work, branches, commits, pull requests, reviews, and review fixes. Shorthands: ic, is, cm, pr, prr, prf."
---

# Git Workflow

Handle Git and GitHub work using repository conventions discovered at runtime.

## Core Rules

- Treat existing changes as user work; never revert unrelated changes.
- Never commit, push, create a PR, post a review, or merge without explicit user authorization.
- Read repository `AGENTS.md`, `README.md`, contributing docs, and relevant local skills before acting.
- Detect the repository, default branch, conventions, labels, test commands, and current state instead of hardcoding them.
- Stop and ask one narrow question only when the next action could damage user work, publish externally, or target the wrong Issue/PR.
- Keep the configured global default unless the user changes it. For Issue work and independent review, follow the phase and risk-based model routing in the selected reference.
- Do not use subagents merely to save tokens. They duplicate setup context; use them only for genuinely independent parallel work when allowed.
- When a task is owned by an active `parallel-worktree` registry/context packet, keep read-only Git inspection here but route every mutating Git operation through that skill's `pw-helper`. Never bypass its operation ID, ownership, scope, lock, or cleanup checks.

## Route to One Reference

Read only the reference required for the current operation. Do not preload the others.

- Create or triage an Issue, or `ic`: read [references/issues.md](references/issues.md).
- Start Issue work, create its branch, plan it, or `is`: read [references/issue-start.md](references/issue-start.md).
- Commit, prepare/create a PR, or run the independent completion gate (`cm`, `pr`, explicit review, or completion): read [references/delivery.md](references/delivery.md).
- Review a PR/local diff or address review feedback (`prr`, `prf`): read [references/code-review.md](references/code-review.md).

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
