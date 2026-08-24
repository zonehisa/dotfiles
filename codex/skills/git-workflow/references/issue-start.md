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
3. Have the saved `git_operator_luna` resolve the target, fetch origin, and create the dedicated branch/Worktree using repository naming conventions. Fall back to `bugfix/#123-description`, `docs/#123-description`, `refactor/#123-description`, or `feature/#123-description` by change type. In an active `parallel-worktree` lifecycle, do not run these mutations directly: select the planned branch name, then request its `pw-helper` to fetch/create the registered branch with the current operation ID.
4. Have the saved `git_operator_luna` save current Issue context when `.agent/state/` exists or repository docs require it.
5. Confirm HEAD, branch, clean, and the saved Issue context; verify that the dedicated branch/Worktree and state file belong to the selected Issue before implementation handoff.
6. Hand the checked-out relevant specifications, code, tests, and boundary analysis to the one saved `implementer_luna`; it owns relevant spec/code/test investigation, Plan/TDD, and implementation through the coherent checkpoint.
7. Have that saved `implementer_luna` use Plan as the default implementation entry point:
   - establish the goal, users, scope, success criteria, acceptance scenarios, and test approach
   - confirm at least one concrete user scenario before finalizing user-visible behavior or workflow changes
   - keep the Coordinator responsible for user questions and authority; invoke `dig` only for material unresolved decisions whose answers change UI interaction, workflows, state transitions, authorization, or competing designs
   - ask one `dig` question at a time and return to Plan when those decisions are resolved
   - skip full `dig` for small bugs with clear reproduction and expected behavior, copy/comment changes, and straightforward internal changes
8. Convert confirmed scenarios into acceptance criteria.
9. When the bounded `is` fast path below passes, continue without a second implementation-permission pause; otherwise stop at Plan for the missing decision or authority.
10. Hand implementation planning/TDD to that same saved `implementer_luna` (`fork_turns = "none"`, GPT-5.6 Luna `max`, workspace-write) without mutating or re-delegating the saved `git_operator_luna` lifecycle.
11. Report the Issue, branch, state file, planning outcome, and unresolved decisions. Do not commit or create a PR.

If the current mode prohibits mutations, complete investigation and planning first, then create the branch after returning to an execution-capable mode.

## Bounded `is` fast path

Issue selection and dedicated branch/worktree setup are always authorized by `is`, independently of bounded fast-path gates. Continue from Issue/worktree/Plan through a coherent implementation checkpoint only for small bounded R1/R2 when all gates are true: concrete acceptance criteria (including a testable scenario), existing repository pattern reuse, no persistence, authorization, API/data-contract, or state-transition change, at most three source/test paths (or one similarly bounded policy/documentation change), and no material unresolved decision, scope expansion, destructive/external authorization requirement, or other authority gap. This path does not pause merely to ask permission to implement and falls back to the normal split flow when any gate fails or risk/scope grows. It does not authorize stage, commit, push, PR, or merge.

For a passing bounded R1/R2 path, one saved `implementer_luna` owns investigation, Plan/TDD, and implementation. Do not spawn `explorer_luna` merely to rediscover the same paths; use explorer_luna only for a specifically named independent uncertainty. Use verifier pre-checkpoint only when an explicit setup/start/test-map/browser-plan uncertainty exists; otherwise wait for the coherent implementation checkpoint. final checkpoint verification and review remain mandatory. UI still requires the Coordinator-owned IAB and explicit human UI/behavior acceptance; non-UI still requires verifier/reviewer gates.

Useful commands:

```bash
gh issue view <number> --repo <owner/repo>
git fetch origin
git checkout -b <branch-name> origin/<default-branch>
```
