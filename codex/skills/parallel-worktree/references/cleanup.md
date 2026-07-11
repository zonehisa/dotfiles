# Two-Phase Cleanup

## Phase 1: Candidate Check

Read only. Require:

- Actual tasks at the child cwd exactly equal registered owner plus non-archived observers.
- Owner and every observer have no active turn.
- Allowed states: `idle`, `notLoaded`.
- Refused states: `active`, `active` with `waitingOnApproval`, `systemError`, unavailable, or unknown.
- Child has no tracked or untracked changes.
- PR repository, base, and head match the registry; PR state is merged.
- No unpushed commit. With upstream, HEAD is not ahead. Without upstream/remote head, local HEAD equals the recorded final PR head SHA.

Show the evidence and request cleanup approval.

Record PR evidence only through `pw-helper verify-pr`, which queries GitHub and validates repository/base/head. Record cwd task inventory through a private adapter evidence file, then pass a newly generated evidence file to `pw-helper cleanup-prepare` to create a short-lived candidate digest.

## Phase 2: Locked Revalidation

After approval, acquire Issue lock then repository lock. Re-read task inventory/statuses, PR, HEAD, worktree status, upstream, ownership, and adapter contract. Reject any change.

Write the approved candidate ID to a private 0600 approval file and run `pw-helper cleanup-authorize` with a newly generated task-inventory evidence file. The helper re-queries GitHub, reloads the exact-cwd task inventory, and recomputes the candidate under lock. It permits worktree removal for only two minutes; stale cleanup requires both phases again.

If supported, unpin every registered task. Archive/detach observers according to the adapter, then archive the owner last.

## Codex-Managed

Only automate when `archive_delete_contract` is `verified` for the exact adapter/version.

1. Archive registered tasks according to the verified contract.
2. Transition to `cleanup_pending`.
3. Confirm Codex removed the worktree and it disappeared from `git worktree list`.
4. Ask the helper to try non-force local branch deletion.
5. Transition to `archived`.

Never run `git worktree remove`. If removal is not confirmed, transition to `cleanup_failed`; never fall back automatically.

For `unverified` or `unsupported`, instruct the user to archive through the desktop UI and resume cleanup. For `failed`, stop without automatic retry.

## Skill-Managed

1. Reconfirm all tasks are non-active, then archive them.
2. Ask the helper to remove the exact registered worktree without force.
3. Confirm disappearance from the worktree list.
4. Ask the helper to try `git branch -d`.
5. Archive/detach the registered tasks and generate a final exact-cwd task inventory.
6. Run `pw-helper cleanup-finalize`; only this command may transition to `archived` after confirming the worktree is gone, branch cleanup was attempted, and no task remains at that cwd.

Never use `-D`, delete the remote branch, or run `git worktree prune`. `prune --dry-run` may be reported separately.
