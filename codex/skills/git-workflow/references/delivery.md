# Delivery workflow

Read this reference only at an implementation, review, commit, PR, or cleanup boundary. The
normal clean single-foreground path is owned by Coordinator/main; delegated roles and Worktrees
are conditional rather than mandatory.

## Route and preparation

- Coordinator/main may inspect Git/GitHub, resolve targets, plan, edit source, and run targeted
  tests directly. Use `git_operator_luna` only for an authorized external write (Issue/PR,
  push, comment, merge, or cleanup) or an explicitly isolated Git operation.
- Use `implementer_luna` only for parallel, dirty-checkout, background/long-running, explicitly
  isolated, or high-risk implementation. It is a single Luna `max` writer and never commits,
  pushes, creates a PR, or spawns another writer.
- Use a Worktree only for parallel work, a dirty primary checkout, background work, or explicit
  isolation. Preserve all unrelated staged, unstaged, untracked, and ignored files.
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

Round 1 reviews the complete frozen scope. Round 2 sends only prior findings, their fix delta,
directly affected paths, the new full-scope fingerprint, the same immutable
`threat_model_supported_use_declaration_hash`, and successful existing evidence. A user-approved
Round 3 is bounded by the same fields and is terminal. Do not create another full lifecycle after
two completed lifecycles in unchanged scope; repeated P0-P2 findings require simplification and
an explicit user decision.

Spawn one fresh reviewer per lifecycle and save its agent ID. Send bounded `Round N` follow-ups to
that same reviewer. A missing reviewer, incomplete scope, or fingerprint mismatch invalidates the
review and blocks delivery; do not fall back to another task or model. Reviewers return a concise
findings-first, read-only final with `review_valid`, P0-P3 counts, disposition, residual risk,
unverified scope, and the supplied fingerprint. They do not rerun successful implementation tests.

Construct `review_lifecycle_key` from repository, Issue/branch, base, and reviewer role. Construct
`review_round_key` from that lifecycle key, `patch_base_tree`, and the changed-path fingerprint.
Construct `review_context_key` from acceptance criteria, risk, target files, and the immutable
`threat_model_supported_use_declaration_hash`. Reuse a bounded result only when these keys and the
declaration/hash match. Any change to acceptance criteria, risk, target files, or the declaration/hash
invalidates the context and requires a new lifecycle; Round 1, Round 2, and an authorized Round 3
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
acceptance criteria/risk/target files are unchanged, and both records are retained.

## User-visible UI gate

For UI changes, Coordinator/main is the sole browser executor. During implementation use ordinary
local checks and micro-adjustments only; do not start completion review or an IAB check after every
visual tweak. Run the targeted technical verification and completion review on the settled source.
On review-cleared content, Coordinator selects the built-in IAB with the exact
`agent.browsers.get("iab")` selector and performs one final visual/interactive check. Chrome/Edge
requires a user request or a recorded special requirement plus approval; never auto-fallback. Freeze
one packet containing selector/family, URL, primary flow/view, viewport, result,
`automatic_fallback=false`, artifact IDs/hashes, checkpoint token/scope, and the changed-path
`accepted_source_fingerprint`. Verifier validates this final packet/source/artifact integrity
read-only without acquiring or rerunning IAB, then the real human accepts appearance and
primary behavior once on that same candidate. Any material source change reopens technical
verification/review and requires a new final IAB packet. Non-UI changes require no browser packet or
human UI acceptance.

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

Issue/PR creation, stage, commit, push, comments, merge, and cleanup require explicit authorization
from the user. `PRまで` bundles commit, push, and PR creation only for the unchanged reviewed target;
it does not authorize merge. Required CI must be successful before merge. Cleanup removes only
task-owned runtime resources, clean merged Worktrees, and branches proven reachable or
patch-equivalent; dirty or unproven resources remain protected.

Report risk/reason, route, agent ID/model/effort, fingerprint, rounds, finding dispositions,
tests/sensors, verification commands, and unverified scope.
