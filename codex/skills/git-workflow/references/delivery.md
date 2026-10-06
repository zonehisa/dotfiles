# Delivery workflow

Read this reference only at an implementation, review, commit, PR, or cleanup boundary. R0 may use a
clean single-foreground checkout; R1-R4 Issue deliveries use an Issue-dedicated Worktree from the latest
remote default branch. The Coordinator/main role remains the owner of the selected Worktree.

## Route and preparation

For an Issue-linked delivery, validate the [Issue preflight](issue-preflight.md) packet at the delivery
boundary. Re-fetch and bind the Issue hash, live `origin/<branch>` target, related PR context, and the
explicit `needs_work` assessments before stage/commit/push. A satisfied or unknown result blocks the
write. Before PR readiness, `pw-helper` also checks the clean worktree, submitted head, isolated virtual
merge conflict, and non-empty effective merge delta against the current base.

- Coordinator/main performs discovery and planning, may implement R0 directly, and may edit/test directly
  inside the selected R1-R4 Worktree. Before source edits, verify the Worktree realpath and branch; preserve
  the primary checkout and all unrelated staged, unstaged, untracked, and ignored files.
- Use `implementer_luna` only for parallel, dirty-checkout, background/long-running, explicitly delegated,
  or high-risk implementation. It is a single Luna `max` writer and never commits, pushes, creates a PR,
  or spawns another writer. A default Worktree alone does not require this child.
- For every new R1-R4 Issue, run one bounded `git fetch origin`, freeze `origin/<default-branch>` as the base,
  and provision the dedicated Worktree before source edits. Do not `pull` the primary checkout or create an
  independent Codex task merely to obtain this isolation.
- Completion review remains separate: R1-R4 use a fresh-context `reviewer_luna` with
  `fork_turns="none"`, GPT-5.6 Luna `max`, and read-only access. R0 (copy, comments, obvious
  formatting) may skip review.

## Risk-routed completion review

Classify the complete frozen scope after implementation and feedback iterations, not after each
edit or UI check. Mixed scopes use the highest rank.

| Rank | Typical scope | Completion route |
|---|---|---|
| R0 | copy, comments, obvious formatting | no reviewer |
| R1 | CSS, color, spacing, static markup | fresh `reviewer_luna`, Luna `max`, read-only |
| R2 | events, bindings, conditions, navigation, data access | fresh `reviewer_luna`, Luna `max`, read-only |
| R3 | persistence, queries, state transitions, authorization, public contracts | fresh `reviewer_luna`, Luna `max`, read-only |
| R4 | security boundaries, credible data-loss/corruption, concurrency/locking, critical incidents | fresh `reviewer_luna`, Luna `max`, read-only |

### Review submission preflight

Before sending an R1-R4 completion-review request, run `review_fingerprint.py` for the full staged
scope and validate the structured request record:

```bash
python3 codex/skills/git-workflow/scripts/review_preflight.py validate --packet <review-packet.json>
```

The packet records the repository, Issue, branch/base, objective, frozen acceptance criteria, risk
and reason, target paths, the exact supported-use declaration and its SHA-256, patch-base tree,
`fingerprint_scope`, changed-path fingerprint and the full `changed_paths` records emitted by
`review_fingerprint.py`, successful test evidence bound to that fingerprint, reviewer
identity/role/model/effort/context, and round. The helper recomputes the versioned fingerprint from
those records and checks every record path against `target_paths`. The Coordinator must retain the
fingerprint command output for the complete staged scope; the helper does not query Git or prove that
caller-supplied records came from that command. The helper fails closed on a
missing field, a declaration/hash mismatch, changed paths outside the target scope, unsuccessful or
stale test evidence, or a reviewer that does not meet the existing independent read-only route.
It checks records; it does not run tests, classify risk, generate a declaration/hash, or authorize
staging or publication. A Round 3 approval record must be bound to the current lifecycle/context/round
and changed-path fingerprint, including the immutable declaration hash. The Coordinator must still
verify its reference against actual direct user authorization; the helper cannot authenticate approval.
It also cannot prove when a declaration was written: freeze it before the first review request and
retain its source. Never backfill a missing historical hash from a later declaration; an old incomplete
record cannot authorize review or delivery.

When there is a prior completed review, compare the validated packet with that saved result before
starting another reviewer:

```bash
python3 codex/skills/git-workflow/scripts/review_preflight.py compare \
  --packet <review-packet.json> --previous-report <review-result.json>
```

The saved result must include `review_valid`, `completed`, the lifecycle/context/round keys, the
changed-path fingerprint, the immutable declaration hash, reviewer agent ID/role/model/effort,
fresh read-only context, round, and P0-P3 counts. A Round 3 request packet also requires a direct
user-approval record bound to the current lifecycle/context/round and changed-path fingerprint. Exact
matching context and fingerprint reuse the prior review and its findings;
do not start a duplicate review or rerun
successful tests. Reuse never clears P0-P2 blockers. A changed fingerprint with unchanged context
requires the next bounded round from the same reviewer; a changed patch-base tree, objective, acceptance
criterion, risk, target path, or declaration requires a new lifecycle and fresh reviewer. Missing or
invalid prior evidence cannot authorize reuse. Keep the existing round cap, approval boundary, and
risk-based completion gate.

Round 1 reviews the complete frozen scope. If only the patch/fix delta changes while the objective, acceptance
criteria, risk, target files, and the immutable threat-model declaration remain unchanged, reuse the
same reviewer for the next numbered round. Round 2 sends only prior findings, their fix delta,
directly affected paths, the new full-scope fingerprint, the same immutable
`threat_model_supported_use_declaration_hash`, and successful existing evidence. A user-approved
Round 3 is bounded by the same fields and is terminal. Skip a round when the patch and its review
context are unchanged. A changed patch-base tree, objective, acceptance criterion, risk, target path, or
immutable threat-model declaration starts a new lifecycle with a fresh reviewer. A base ref or commit
move with the same patch-base tree, changed-path fingerprint, and review context can reuse the saved
result. Do not create another full lifecycle after two completed lifecycles in unchanged scope;
repeated P0-P2 findings require simplification and an explicit user decision.

Spawn one fresh reviewer per lifecycle and save its agent ID. Send bounded `Round N` follow-ups to
that same reviewer. A missing reviewer, incomplete scope, or fingerprint mismatch invalidates the
review and blocks delivery; do not fall back to another task or model. Reviewers return a concise
findings-first, read-only final with `review_valid`, P0-P3 counts, disposition, residual risk,
unverified scope, and the supplied fingerprint. They do not rerun successful implementation tests.

Construct `review_lifecycle_key` from repository, Issue/branch, patch-base tree (the base content),
and reviewer role. Keep base ref and base SHA in the packet for audit. A ref or commit move may reuse
the prior result only when the patch-base tree and changed-path fingerprint are identical and the
objective, acceptance criteria, risk, target paths, and declaration are unchanged. A changed patch-base tree
starts a new lifecycle with a fresh reviewer. Construct `review_round_key` from that lifecycle key,
`patch_base_tree`, and the changed-path fingerprint.
Construct `review_context_key` from objective, acceptance criteria, risk, target files, and the
`threat_model_supported_use_declaration_hash`. Reuse a bounded result only when these keys and the
declaration/hash match. Any change to objective, acceptance criteria, risk, target files, or the
declaration/hash invalidates the context and requires a new lifecycle; Round 1, Round 2, and an authorized Round 3
carry the same immutable declaration/hash.

P0-P2 findings block commit and PR. Classify each finding as accepted, rejected with evidence, or
requiring user input. Add the smallest regression test/sensor before an accepted fix when feasible,
then restage and refreeze the entire scope. A credible supported-use security/correctness risk is
blocking; purely theoretical adversarial-local hardening outside the declared threat model is P3.

## Staging and changed-path fingerprint

Before review, run `git status --short`, stage the complete intended scope only, and record:

```bash
python3 codex/skills/git-workflow/scripts/review_fingerprint.py \
  --repo <repo> --base <base-ref>
```

The fingerprint is a canonical SHA-256 of sorted changed-path records between the patch base tree
and the staged target tree. Each record contains the normalized path and `before`/`after` entries
with Git `mode`, object `type`, and object ID in the `blob` field. The hash excludes commit IDs,
HEAD/index/staging metadata, mtimes, untracked files, and unrelated paths. A mode-only change,
addition, deletion, or blob change therefore changes the fingerprint; moving the same reviewed
target into a new commit with `--patch-base <base>` preserves it. The output labels this contract
`fingerprint_scope=changed-paths-blob-mode` and includes `changed_paths` for audit.

Immediately before commit recompute the fingerprint. After commit use `--patch-base` and require
`index_matches_head=true` plus a matching path fingerprint. Before PR creation require a clean tree,
matching branch/base/Issue, and the same reviewed HEAD or verified patch-equivalent fingerprint.
A base move is reusable only when `patch_base_tree` and the changed-path fingerprint are identical,
objective/acceptance criteria/risk/target files are unchanged, and both records are retained.

## User-visible UI gate

For UI changes, Coordinator/main is the sole browser executor. During implementation use ordinary
local checks and micro-adjustments only; do not start completion review or an IAB check after every
visual tweak. Run targeted tests and technical verification, then completion review, on the settled
source. On the review-cleared final candidate, Coordinator explicitly selects the built-in browser
by browser ID `iab` and performs one final visual/interactive check. Follow the current
browser-control documentation; if legacy documentation exposes `agent.browsers.get`, use its
documented form. Current CUA examples are
`cua.createBrowserTab("iab", url, {visible: true})` and
`cua.getTab(tabId, {browser: "iab"})`; never execute an undocumented or nonexistent API.
Chrome/Edge requires a user request or a recorded special requirement plus approval; never
auto-fallback. Freeze one packet containing selector/family, URL, primary flow/view, viewport, result,
`automatic_fallback=false`, artifact IDs/hashes, checkpoint token/scope, and the changed-path
`accepted_source_fingerprint`. Verifier validates this final packet/source/artifact integrity
read-only without acquiring or rerunning IAB, then the real human accepts appearance and
primary behavior once on that same candidate. Any material source change reopens technical
verification/review and requires a new final IAB packet. Non-UI changes require no browser packet or
human UI acceptance.

The UI gate order is: targeted tests and technical verification -> completion review -> Coordinator's
final IAB -> verifier's read-only packet check -> human appearance and primary-behavior acceptance.
The existing packet schema keeps `selector="iab"` and `browser_family="iab"` for the default path.

Serialize the material packet as canonical JSON and bind it to `browser_evidence_hash`; a metadata sidecar
may contain only generated-at/generator-version fields and cannot override material values.
The packet binds the exact `checkpoint_token` and `checkpoint_scope` to that hash.

`ui_evidence.py` rejects unsafe, duplicate, absolute, `..`, escaping-symlink, missing, and special
files. Its source fingerprint is canonical records of the explicit changed scope: normalized path,
file/symlink type, Git mode, and working-tree blob (symlink target is hashed). Staging/index-only
changes and out-of-scope files do not affect it; scoped content/type/mode/deletion changes do.

## External PR review (`prr`)

`prr` is a separate read-only lane. Use `external_pr_snapshot.py` with exact repository, PR number,
base/head SHAs, unique merge-base, sorted changed paths, and object-derived patch hash. It never
stages files, creates a checkout/source bundle, or calls `review_fingerprint.py`. An unchanged head
with the same snapshot identity may reuse the owning task's valid result; a changed head first
compares unresolved finding paths/direct impacts and then reviews only new delta/affected code.
Deletions and renames never auto-clear blockers. Comment posting still requires explicit approval and
one head-bound preparation followed by one read-only verification.

## Video evidence

Video/evidence is opt-in. Without an explicit user request, do not capture, inspect, render, upload,
or mention a recording; use exactly:

```markdown
## Visual Evidence
Not requested (video evidence is opt-in)
```

When explicitly requested, use `$pr-evidence-video`, pass privacy/artifact checks, revalidate the
pushed HEAD and changed-path fingerprint, and upload only through the approved browser/UI path.
Do not use API or `gh` to pretend an upload occurred. UI functional verification and human
appearance/behavior acceptance remain mandatory regardless of video.

## Authorization, commit, PR, and cleanup

A fix/change request alone is not publish authorization. Issue/PR creation, stage, commit, push,
comments, merge, and cleanup require explicit authorization from the user. Until staging is
authorized, continue read-only investigation, diff organization, non-staging review preparation,
and tests. At the staging gate, ask once for the missing authorization instead of silently widening
the request. An explicit request such as `対象変更をPRまで` authorizes, for that target scope only,
review preparation, staging, commit, push, and PR creation in that order as one delivery bundle;
it does not authorize merge or any unrelated path. Required CI must be successful before merge.
Cleanup removes only task-owned runtime resources, clean merged Worktrees, and branches proven
reachable or patch-equivalent; dirty or unproven resources remain protected.

Report risk/reason, route, agent ID/model/effort, fingerprint, rounds, finding dispositions,
tests/sensors, verification commands, and unverified scope.
