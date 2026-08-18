# Start Issue Work

## Model and operator boundaries

- Keep the global default model unchanged.

## Git workflow operator contract

- `is` Git/GitHub discovery, target resolution, and command preparation use the saved `git_operator_luna` (`fork_turns = "none"`, GPT-5.6 Luna `max`, workspace-write); keep this operator fixed and do not re-delegate it.
- When a prepared mutation needs runtime approval, require the operator to return the exact command and resolved targets, then have the coordinator execute that command against the user's direct authorization as specified in `SKILL.md`.
- Implementation planning/TDD uses the coordinator-owned saved `implementer_luna` (`fork_turns = "none"`, GPT-5.6 Luna `max`, workspace-write); keep it fixed and do not mutate or re-delegate the saved operator lifecycle.

## Workflow

1. Confirm there are no unrelated uncommitted changes before switching branches.
2. Have the saved `git_operator_luna` inspect and prepare Git/GitHub startup operations, then read the selected Issue and repository-specific Issue-start instructions. Let the operator execute authorized commands that do not need runtime approval; route approval-bound commands through the coordinator without changing their targets or effects.
3. Inspect relevant specifications, code, and tests before asking questions.
4. For investigation-heavy or recurring defects, inspect meaningful write/read paths, background paths, validation, state transitions, UI entry points, and boundaries such as null, dates, terminal states, multiple records, and association changes.
5. Suggest at most three related Issues only when the connection is strong; never include them without approval.
6. Use Plan as the default pre-implementation workflow:
   - establish the goal, users, scope, success criteria, acceptance scenarios, and test approach
   - confirm at least one concrete user scenario before finalizing user-visible behavior or workflow changes
   - invoke `dig` only for unresolved high-risk decisions whose answers materially change UI interaction, workflows, state transitions, authorization, or competing designs
   - ask one `dig` question at a time and return to Plan when those decisions are resolved
   - skip full `dig` for small bugs with clear reproduction and expected behavior, copy/comment changes, and straightforward internal changes
7. Convert confirmed scenarios into acceptance criteria. Hand implementation planning/TDD to the coordinator-owned saved `implementer_luna` (`fork_turns = "none"`, GPT-5.6 Luna `max`, workspace-write) without mutating or re-delegating the saved `git_operator_luna` lifecycle.
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
