# Start Issue Work

## Model Gates

- Keep the global default model unchanged.
- At `is` startup, ask the user to select GPT-5.6 Sol with `xhigh` reasoning for investigation, Plan, and `dig`. Pause planning until the switch is confirmed when the current model/effort cannot be verified.
- After the plan is approved, stop before editing and ask the user to switch the same task to GPT-5.6 Terra with `medium` reasoning. Continue implementation and TDD only after confirmation.
- Keep the same task for the phase switch so its history and cached context are preserved. Do not create a separate implementation task solely to change models.

## Workflow

1. Confirm there are no unrelated uncommitted changes before switching branches.
2. Apply the planning model gate, then read the selected Issue and repository-specific Issue-start instructions.
3. Inspect relevant specifications, code, and tests before asking questions.
4. For investigation-heavy or recurring defects, inspect meaningful write/read paths, background paths, validation, state transitions, UI entry points, and boundaries such as null, dates, terminal states, multiple records, and association changes.
5. Suggest at most three related Issues only when the connection is strong; never include them without approval.
6. Use Plan as the default pre-implementation workflow:
   - establish the goal, users, scope, success criteria, acceptance scenarios, and test approach
   - confirm at least one concrete user scenario before finalizing user-visible behavior or workflow changes
   - invoke `dig` only for unresolved high-risk decisions whose answers materially change UI interaction, workflows, state transitions, authorization, or competing designs
   - ask one `dig` question at a time and return to Plan when those decisions are resolved
   - skip full `dig` for small bugs with clear reproduction and expected behavior, copy/comment changes, and straightforward internal changes
7. Convert confirmed scenarios into acceptance criteria. After plan approval, apply the implementation model gate, then use TDD for non-trivial behavior changes.
8. Fetch origin and create a branch directly from the detected default branch using repository naming conventions. Fall back to `bugfix/#123-description`, `docs/#123-description`, `refactor/#123-description`, or `feature/#123-description` by change type. In an active `parallel-worktree` lifecycle, do not run these mutations directly: select the planned branch name, then request its `pw-helper` to fetch/create the registered branch with the current operation ID.
9. Save current Issue context when `.agent/state/` exists or repository docs require it.
10. Report the Issue, branch, state file, planning outcome, and unresolved decisions. Do not commit or create a PR.

If the current mode prohibits mutations, complete investigation and planning first, then create the branch after returning to an execution-capable mode.

Useful commands:

```bash
gh issue view <number> --repo <owner/repo>
git fetch origin
git checkout -b <branch-name> origin/<default-branch>
```
