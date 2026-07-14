# Lifecycle

## Responsibility Boundary

This skill owns primary-checkout protection, base selection, registry/lease management, worktree ownership, resource reservations, task tracking, and cleanup. Delegate implementation, TDD, commit, review, and PR conventions to `git-workflow`. Delegate cross-repository or shared-contract work to `issue-orchestrator`.

## State Machine

Normal transitions:

```text
provisioning -> created -> planning -> approved -> implementing
implementing <-> reviewing
implementing|reviewing -> pr_open
pr_open -> implementing|reviewing|merged
merged -> cleanup_ready -> cleanup_pending -> archived
```

The three cleanup transitions are helper-owned: `cleanup-prepare`, `cleanup-authorize`, and `cleanup-finalize`. Generic `transition` must reject them.

Exceptional states are `blocked`, `drifted`, `orphaned`, `failed`, and `cleanup_failed`. Store `resume_state` before entering a recoverable exceptional state.

## Start

### Read-only preparation

1. Validate a positive decimal Issue and single trusted repository.
2. Reject cross-repository or contract-changing scope.
3. Inspect existing registry, worktrees, branches, tasks, and PRs. Never auto-adopt an unregistered PR.
4. Inspect `.worktreeinclude`, `.codex/**`, `AGENTS.md`, ignored `AGENTS.override.md`, repository skills, Local Environment, setup scripts, and resource conflicts.
5. Show all required approvals before acquiring locks.

### Durable preparation

1. Acquire the Issue lock, then the repository lock. Acquire the global resource lock last and only while allocating cross-repository ports/namespaces.
2. Detect the remote default branch; do not assume `main` when `origin/HEAD` is unavailable.
3. Fetch origin. On failure, create nothing.
4. Resolve and freeze `base_branch`, `base_remote_ref`, and `base_sha_at_start`.
5. Under the repository lock, reserve the planned branch, logical worktree slot, port, DB, Compose, and cache namespaces.
6. Write a `provisioning` registry record with a unique operation ID and renewable 30-minute lease.
7. Release the repository lock, then the Issue lock before any UI, task, or user wait.

An expired lease never authorizes automatic recreation or deletion. `resume` reconciles actual resources and offers adopt/retry/manual-repair choices. After an explicit choice, `pw-helper resume-operation` verifies the expected state and owned Git resources before issuing a new 30-minute operation ID; it never creates or deletes resources.

### External provisioning and adoption

1. Create the worktree/task without holding file locks. `codex_managed` reserves only a logical slot; `skill_managed` reserves an exact allowed path.
2. Reacquire Issue then repository lock.
3. Verify actual path, owner task ID, base HEAD, detached state, clean state, ignored-file manifest, ownership, and permission profile.
4. Reject symlinks, the primary root, repository root, paths outside the allowed worktree root, or paths missing from `git worktree list --porcelain`.
5. Create the planned branch through `pw-helper`; record it as `actual_branch`; transition to `created`.
6. Recompute the primary-checkout digest and require it to match the digest taken immediately before provisioning.

## Child Clean Contract

Before creating the branch require:

- `HEAD == base_sha_at_start` and detached HEAD.
- No staged or unstaged tracked diff.
- No untracked files.
- No ignored files outside the approved copy/setup manifest.
- No unapproved ignored `AGENTS.override.md`.

Any mismatch transitions to `drifted` without creating the branch.

## Status And Resume

`status` is read-only. Reconcile registry, Git worktrees, branch, HEAD, owner, observers, cwd task inventory, PR, lease, resources, pin/retention, and archive contract.

- Extra task at the child cwd: `drifted`.
- Missing expected task or worktree: `orphaned`.
- Expired provisioning lease: inspect actual resources; never automatically retry.
- Expired cleanup lease with an existing worktree: explicit `resume-operation` returns to `merged` and requires both cleanup phases again. If the worktree was already safely removed, it resumes `cleanup_pending` for branch cleanup and final task verification only.
- Matching ownership: `resume` may continue from `resume_state` or current normal state.
- Existing unregistered matching PR: show repo/head/base evidence and ask before adoption.

## Risk Routing

| Risk | Plan | Implementation/TDD | Review |
|---|---|---|---|
| R0-R1 | Sol medium | Terra medium | Existing R0-R1 policy |
| R2 | Sol high | Terra medium | Existing R2 policy |
| R3-R4 | Sol xhigh | Terra medium | Existing R3-R4 policy |
