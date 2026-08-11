# Adapter Contracts

## Valid Pairings

| management_mode | adapter_kind | Meaning |
|---|---|---|
| `skill_managed` | `git_worktree_app_server` | Helper owns Git worktree lifecycle; App Server owns task lifecycle at the registered cwd. |
| `codex_managed` | `codex_desktop_managed` | ChatGPT desktop owns managed worktree and task lifecycle. |

Reject every other pairing.

## Required Capability Report

An adapter must report whether it can:

- Create/start a task at the requested base or cwd.
- Return actual worktree path and stable owner task ID.
- Read, resume, and archive tasks.
- Enumerate all tasks by exact cwd with runtime status.
- Enforce the child permission profile.
- Control Local Environment/setup behavior.
- Report `archive_delete_contract` as `verified`, `unverified`, `failed`, or `unsupported`.

Pin/unpin, retention-limit reads, and deletion-schedule queries are optional. Record `unsupported` or `unknown` rather than treating them as required.

## Version Enablement

- v1 enables `skill_managed/git_worktree_app_server` only when task-at-cwd capability exists; otherwise provide manual task-start instructions after creating the approved worktree.
- `codex_managed/codex_desktop_managed` is disabled with `contract_not_verified` until the exact desktop adapter version passes contract tests for base, detached HEAD, clean state, cwd inventory, permissions, setup, archive deletion, and retention.
- `archive_delete_contract=verified` enables automatic managed cleanup.
- `unverified` or `unsupported` permits work but requires manual desktop archive.
- `failed` blocks cleanup without retry.

## Task Inventory

At status and cleanup, list every task whose exact cwd equals the registered worktree realpath. Completion-review subagents are not inventory entries. Extra tasks cause `drifted`; a missing owner causes `orphaned`. cleanup preparation/authorization/removal requires a registered owner; an ownerless registry remains read-only for diagnosis/recovery.

Schema v2 is owner-only and requires an empty `observer_tasks` compatibility field. For legacy schema-v1 recovery, schema v1 is owner plus exactly the already-registered observer desktop tasks; report those tasks until cleanup and require every expected task to be cleanup-safe before archiving. No adapter may create, replace, or register a new observer.
