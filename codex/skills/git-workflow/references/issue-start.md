# Start Issue Work

1. Inspect status, branch, Worktrees, new/legacy local state, remote/default branch, Issue, specs, relevant code, and tests.
2. Assign R0-R4 using the shared policy. Switch Codex model/effort only when the selected risk requires it; do not block non-Codex agents on Codex model names.
3. Confirm goal, user, scope, success criteria, one concrete scenario, and test approach in Plan. Use `dig` only for unresolved decisions that materially change the implementation.
4. Suggest at most three strongly related Issues and never include them without approval.
5. Follow the repository Worktree policy. Prefer an Issue-dedicated Worktree when current work is dirty or another Issue owns it. Reuse only when Issue, branch, state, and Git Worktree evidence agree.
6. New branch names default to `<type>/<issue>-<slug>` without `#`; accept legacy names only when the repository says so.
7. Fetch the detected remote default and create from that ref. Do not switch/stash/reset the current dirty Worktree.
8. On failure, do not fall back to the current Worktree, write partial state, or auto-delete leftovers. Report paths and state.
9. Save Worktree-local state only after verifying the created Worktree and branch.
10. Report the Issue, risk, Plan, branch/Worktree, and state. Do not commit, push, or create a PR.

When the current mode prohibits mutations, finish investigation and Plan first, then provision in an execution-capable mode.
