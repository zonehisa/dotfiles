# Delivery Workflows

## Risk-Routed Diff Review Gate

Run this gate once after implementation and user-feedback iterations are verified, when the user explicitly requests review, or immediately before completion, commit, or PR preparation. Do not run it after every TDD or UI-adjustment loop. Skip only typo, copy, comment, or obvious formatting-only changes.

## User-visible UI workflow order

The following order applies only to user-visible UI changes. Non-UI changes keep the existing flow.
For non-UI checkpoints, use targeted tests, log analysis, and objective non-browser checks directly; no Coordinator browser packet, human UI acceptance, or `accepted_source_fingerprint` is required.
Use explicit checkpoint/evidence wording; do not add a complex persisted state mechanism.

### Built-in IAB selection and evidence

Every user-visible UI checkpoint and human acceptance requires valid browser evidence owned by Coordinator/main; verifier final requires a validated `coordinator_browser_evidence` packet and source integrity. Verifier-side IAB availability is not required.

For user-visible UI, the Coordinator/main context is the browser executor and owner: it runs the visual/interactive checks and records the `coordinator_browser_evidence` packet.

For the default path, before the first visual or interactive check, explicitly select the built-in IAB with the exact selector `agent.browsers.get("iab")`. A Browser skill read, shell/HTTP/test result, `getDefault()`, `getForUrl()`, or `agent.browsers.get("extension")` is not valid browser evidence.

Chrome or Edge is an exception only when the user explicitly requests it, or Chrome/Edge-specific login, extension, or existing-tab access is required and the reason and approval are recorded. For an approved browser exception, select the exact matching `agent.browsers.get("chrome")` or `agent.browsers.get("edge")` selector and reject a missing reason, missing approval, or family mismatch. Never auto-fallback from IAB to another browser surface.

Both browser paths require an exact selector, checked URL, primary flow/view, applicable existing-policy viewport set, and no automatic fallback.

Missing vendor/node_modules/.env/DB, an app that is not started, or a port conflict is not a reason to defer IAB to verifier. The implementer must resolve setup/start, or stop and report IAB unavailable/blocker. Without valid browser evidence, do not advance to a coherent UI checkpoint, human acceptance, or verifier final.

For user-visible UI only, before final human acceptance the Coordinator freezes one canonical `coordinator_browser_evidence` packet for the exact `checkpoint_token`, `checkpoint_scope`, and `accepted_source_fingerprint`. It includes `browser_executor=coordinator/main`, exact `selector`, `browser_family`, checked URL, primary flow/view, viewport, result, artifact/tool evidence identifiers with SHA-256 hashes, and `automatic_fallback=false`; an approved Chrome/Edge exception additionally includes `exception_reason`, `user_approval_evidence`, and `matching_family`. The default packet records exact selector `iab` and family `iab`. The packet records `automatic_fallback=false`.
The canonical packet serialization explicitly includes the exact `checkpoint_token`, exact `checkpoint_scope`, and `accepted_source_fingerprint` fields; those bindings are hashed as part of `browser_evidence_hash`.
Canonical serialization is deterministic UTF-8 canonical JSON with sorted keys and no insignificant whitespace (or the exact equivalent rule); compute `browser_evidence_hash=SHA-256` over those bytes before human acceptance. The human reviews that exact `browser_evidence_hash`. Human acceptance and the immutable final acceptance envelope must repeat and bind to the same `checkpoint_token`, `checkpoint_scope`, `accepted_source_fingerprint`, and `browser_evidence_hash`; verifier recomputes the hash and requires every binding to match. The verifier recomputes `browser_evidence_hash` and rejects a mismatch. The final acceptance envelope is immutable and repeats the packet/hash plus human evidence explicitly referencing the same hash. Any packet field, revision, artifact, or hash change invalidates acceptance and requires a new packet/hash and human acceptance. Any checkpoint, scope, or source-fingerprint change also invalidates acceptance and requires a new packet/hash and human acceptance.
For user-visible UI only, `accepted_source_fingerprint` is an ephemeral canonical SHA-256 of the exact `checkpoint_scope` working-tree records only. Each deterministic record contains a normalized repo-relative path, file/symlink type, executable mode, and working-tree bytes SHA-256 or symlink target. HEAD/index/staging/mtime and out-of-scope paths are excluded. Staging/index-only changes leave `accepted_source_fingerprint` unchanged; any scoped content, type, mode, symlink, or deletion change invalidates acceptance. `ui_evidence.py` validates the scope without mutating Git or the index and rejects duplicates, absolute/`..`, missing/unsafe, escaping symlink, and special-file paths. Git status/diff remain supplementary before/after evidence, not the UI source fingerprint. The material browser packet is schema-versioned and hashed as canonical UTF-8 JSON with sorted keys and no insignificant whitespace. Its exact checkpoint token/scope, source fingerprint, selector/family/no-fallback, URL, flow/view, viewport, result, and evidence artifact IDs plus SHA-256 are material. A separate metadata sidecar allows only `generated_at` and `generator_version`; it cannot override or smuggle material fields and metadata changes do not affect `browser_evidence_hash`. A mismatch invalidates the acceptance and returns to the same implementer/IAB loop and human gate.
For non-UI checkpoints, after `checkpoint_token`/`checkpoint_scope` and implementer pause, no Coordinator browser packet, human UI acceptance, or `accepted_source_fingerprint` is required; run targeted tests, log analysis, and objective non-browser checks directly. If Coordinator/main cannot obtain the approved browser surface for user-visible UI, stop and report IAB unavailable/blocker; verifier-side browser unavailability alone is non-blocking when the valid packet and human acceptance are present.

1. Implementation/IAB loop: Coordinator/main is the browser executor and owner. It runs the default IAB or approved Chrome/Edge exception, records provisional IAB evidence, and returns visual/interactive findings to the same saved implementer loop for micro-adjustments. The implementer owns runnable setup/start, browser plan, and checkpoint state. Do not start completion review during the implementation/IAB loop.
2. Verifier technical verification: after the Coordinator identifies a coherent implementation checkpoint and provides a valid provisional Coordinator packet, `verifier_luna` validates the packet, source fingerprint, artifact hashes, source before/after integrity, targeted tests, logs, and objective non-browser checks. Do not wait for human UI/behavior acceptance before verifier; verifier does not acquire, share, or rerun the Coordinator IAB session and does not decide subjective appearance or usability acceptance. If verifier finds a problem, return to the same implementer/IAB loop and rerun verifier before completion review.
3. Completion review: only after verifier passes, freeze, stage, and fingerprint the accepted scope before starting the Luna/max R1-R4 completion review. Run the P0-P2 fix/reverify/rereview loop to closure. Any post-review source or material UI change reopens verifier and completion review before final IAB and human acceptance. Purely non-user-visible verification artifact changes do not invalidate human acceptance.
4. Final IAB and human UI/behavior acceptance: on review-cleared frozen content, Coordinator/main runs the final IAB, freezes the final material packet/hash, and presents that exact candidate to a real human/user. Only a real human/user may provide explicit combined UI acceptance for appearance and primary behavior. This occurs once for the final frozen content. Human combined appearance and primary-behavior acceptance applies to the same Coordinator checkpoint and its `coordinator_browser_evidence` packet. The Coordinator records that packet and human acceptance as the final UI acceptance evidence, tied to `checkpoint_token`, `checkpoint_scope`, and `accepted_source_fingerprint`. The human reviews and accepts the exact `browser_evidence_hash`; the immutable final acceptance envelope repeats the packet/hash and human evidence referencing the same hash. AI agents may not proxy or assume this acceptance.

Coordinator wait contract: perform one long event wait per delegated stage; after a timeout or attention signal, take at most one timeout/attention snapshot. Never poll unchanged state periodically; report only stage changes or a required sparse ongoing update.

For an explicitly requested video/evidence attachment, the following recording and rendering lifecycle applies.
The Coordinator/main captures or references the local raw recording from its browser evidence packet.
For user-visible UI only, verifier_luna validates the packet, artifact identifiers/hashes, and source integrity read-only; it
does not acquire or rerun the IAB session.

### Review Risk Rank

Classify the complete frozen diff before spawning the review agent. For mixed changes, use the highest applicable rank.

| Rank | Typical changes | Review route |
|---|---|---|
| R0 | Copy, comments, obvious formatting only | Skip |
| R1 | CSS, colors, spacing, static markup with no behavioral bindings | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R2 | Hover/focus/click behavior, JavaScript/Alpine, reactive bindings, display conditions | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R3 | Persistence, queries, state transitions, authorization, public contracts/APIs | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |
| R4 | Security boundaries, credible data-loss/corruption risk, concurrency/locking, critical incidents | Fresh-context `reviewer_luna` subagent: GPT-5.6 Luna, `max`, read-only |

Do not rank a change as R1 merely because it is presented as UI work: events, bindings, conditions, navigation behavior, or data access make it R2 or higher. Record the selected rank and reason in the review evidence.

P0-P2 findings and a higher-risk classification do not change the review route. Incomplete full-diff coverage or a fingerprint mismatch invalidates the review instead of producing an approval. Never automatically downgrade a review rank.

### Bounded Review Rounds

- These rules apply only to review lifecycles created after this policy; do not rewrite an existing lifecycle.
- Round 1 is a full review of the complete frozen diff.
- Round 2 receives only the prior findings, their fix delta, directly affected paths, the new fingerprint, the immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.
- An explicitly authorized Round 3 remains bounded to unresolved Round 2 findings, their fix delta, directly affected paths, the new full-scope fingerprint, the same immutable `threat_model_supported_use_declaration_hash`, and existing successful test evidence.
- Review normally stops after two rounds. Round 3 requires explicit user approval; stop delivery after Round 3. If P0-P2 remain, do not automatically create a new lifecycle.
- Use one `reviewer_luna` agent and the existing `review_fingerprint.py`; do not add another review-state mechanism.
- Do not rerun successful implementation-side tests. Do not reread unchanged specifications, prior conversation, or prior tool output.
- P0-P2 block commit and PR creation.
- A new review lifecycle must not be started automatically after two completed review lifecycles in one unchanged delivery scope.
- After two completed review lifecycles in one unchanged delivery scope, a third full-review lifecycle is not started automatically.
- Stop additional patch layering and require architecture/scope simplification plus an explicit user decision before any new lifecycle.
- An explicitly authorized Round 3 remains bounded and terminal; it must never trigger a fresh lifecycle.
- P0-P2 blockers must be grounded in a credible supported-use reproduction or a bounded code-path proof under the declared threat model and acceptance criteria.
- A runnable reproduction is not required when bounded proof exists.
- Purely theoretical or adversarial-local hardening outside supported use or the declared threat model is P3/residual risk unless the product explicitly supports hostile/multi-tenant conditions.
- Credible security/correctness risk remains blocking.
- Repeated P0-P2 findings in the same scope trigger architecture/acceptance-scope reconsideration, not additional defensive patches.

1. Run `git status --short`, stage the complete intended review scope only, then run `scripts/review_fingerprint.py --base <base-ref>`. The fingerprint represents the staged index; unstaged and untracked files are outside that review and must be reported and kept out of delivery. Freeze the staged paths plus `patch_base_tree` and `patch_hash`. Review dirty submodules separately first.
2. Build `review_lifecycle_key = repository + Issue/branch + base + reviewer_role`, `review_round_key = review_lifecycle_key + patch_base_tree + patch_hash`, and `review_context_key = acceptance_criteria + risk + threat_model_supported_use_declaration_hash + target_files`. The review_context_key includes the immutable `threat_model_supported_use_declaration_hash`. Round 1, Round 2, and an authorized Round 3 packet carry that same declaration/hash. A changed declaration/hash invalidates the current review context and requires a new context before submission; do not reuse stale bounded review evidence. Skip submission only when both round and context keys are unchanged.
3. For every R1-R4 review, spawn the `reviewer_luna` role with `fork_turns = "none"`; never inherit the implementation conversation. Save its agent ID and send later `Round N` reviews to that same agent after a valid review. Create one new agent at the start of each lifecycle.
4. For Round 1 only, give the reviewer only acceptance criteria, repository/base/branch, the complete frozen-diff scope, exact fingerprint, immutable threat-model/supported-use declaration/hash, and checks already run. For Round 2, send only the prior findings, fix delta, directly affected paths, new full-scope fingerprint, the same immutable threat-model/supported-use declaration/hash, and existing successful test evidence; do not send another complete diff. For an explicitly approved Round 3, send only unresolved Round 2 findings, fix delta, directly affected paths, new full-scope fingerprint, the same immutable threat-model/supported-use declaration/hash, and existing successful test evidence. Do not include implementation conclusions or suspected safe areas.
5. Require concise, read-only, findings-first P0-P3 output with file/line evidence. Prioritize correctness, regression, contracts, state transitions, locking/authorization, security/privacy, performance, maintainability, and missing tests. Do not restate satisfied requirements or unchanged code.
6. Require `review_valid = no` when the reviewer cannot access the complete frozen diff or cannot repeat the supplied fingerprint. Correct the review scope, restage and refreeze it, then discard the invalid review and replace it with a new fresh-context `reviewer_luna` agent for the lifecycle.
7. Ask the reviewer for a final-only response with no progress narration. Require the final output to repeat the fingerprint. A no-findings result contains only fingerprint, severity counts, `review_valid`, residual risks, and unverified areas. Wait once for the completion notification; do not repeatedly poll unchanged status.
8. Classify every finding as accepted, rejected with evidence, or requiring user input.
9. Batch accepted fixes, adding the smallest regression test/sensor first when feasible, then run the nearest verification. Treat P3 as advisory and defer it unless it violates acceptance criteria or the user explicitly includes it.
10. Restage the complete intended scope and freeze a new full-scope fingerprint once after the fix batch. For Round 2, send only the prior findings, fix delta, directly affected paths, full-scope fingerprint, the same immutable `threat_model_supported_use_declaration_hash`, and existing successful evidence to the same saved agent; do not send another complete diff. If Round 3 is explicitly approved, stop delivery after its final result; do not re-review solely for deferred P3.
11. If spawning, confirming, or reading the `reviewer_luna` subagent is unavailable, stop the completion/commit/PR gate. Do not fall back to another task, model, or self-review.
12. Immediately before commit, recompute the staged-tree fingerprint. Any staged-tree change requires re-review. After commit, run the fingerprint script with `--content-base <reviewed-head>` and require `index_matches_head`, a matching content hash, and no residual review-target changes before tying the commit SHA to review evidence.
13. Immediately before PR creation, require a clean tree, matching target, and either the reviewed clean-state HEAD or the commit SHA recorded directly after the reviewed working-tree commit. Additional or amended changes require re-review. A moved base does not require re-review only when the old reviewed and new fingerprints prove the same `patch_base_tree` and `patch_hash`, acceptance criteria and risk are unchanged, and both fingerprints are retained in the evidence; otherwise re-review.
14. User feedback or code changes after review invalidate the reviewed state; finish the new batch and run one final review at the next review/completion/commit/PR boundary.

Report the review rank and reason, route, reviewer agent ID, model/reasoning effort, fingerprint, reviewed commit when applicable, rounds, unique findings, classification counts, promoted tests/sensors, verification, and unverified scope. Promote project-specific defect classes to tests or `HARNESS.md`; record escaped reviewed defects in `RETRO.md`.

## PR Evidence Lifecycle

Video evidence is opt-in: the full PR evidence lifecycle runs only when the user explicitly requests
a video/evidence attachment for this delivery. If the user did not explicitly request video/evidence,
do not create, capture, inspect, reference, transform, or review any recording/video; do not call
`$pr-evidence-video`, run the evidence-only review, apply the privacy/artifact gate, upload evidence,
or block PR delivery; use the exact PR body text "Not requested (video evidence is opt-in)". If the
user explicitly requests video/evidence, require the
full PR evidence lifecycle: create the video with `$pr-evidence-video`, run the evidence-only review,
pass privacy/artifact checks, revalidate authorization/fingerprint/head, upload through the
browser/UI, and add the `## Visual Evidence` link. IAB functional verification and explicit human
UI/behavior acceptance remain mandatory for every user-visible UI change, whether or not video
evidence is requested. Non-user-visible configuration, documentation, and backend-only changes
remain outside both the UI IAB/human gate and the opt-in video path. For an explicitly requested
video/evidence attachment, if the privacy or artifact gate fails, keep PR delivery pending or closed.
A later explicit request for video/evidence for the same delivery enters the same full lifecycle and
authorization/fingerprint/head/privacy/upload boundaries; there is no automatic fallback or pretend
upload.

For an explicitly requested video/evidence attachment:
The `reviewer_luna` evidence-only lifecycle is separate from completion diff review. It checks the
exact artifact, SHA-256 hash, manifest, and contact frame, plus behavior coverage, target,
fingerprint, head, privacy, codec, size, and duration. It must not judge styling, rerender, inspect
source, or rerun tests; this evidence review does not replace or contaminate completion review.

`PRまで` authorizes only the exact already privacy/evidence-reviewed artifact upload to the same target PR/repository/branch/fingerprint/head, together with the PR body or Conversation link. Different, reencoded, replacement,
external-storage, or other-PR artifacts require new authorization. If upload is impossible, stop
without fallback hosting. Local artifact upload to a PR Conversation is browser/UI-only external
write; do not pretend that an API or `gh` upload occurred. The Coordinator retains the browser upload
and approval boundary if the operator cannot operate the UI. No API or `gh` pretend upload is
allowed.

Before any upload, revalidate the final pushed HEAD and inherited reviewed patch fingerprint. Any
head, artifact, or fingerprint change invalidates evidence and stops upload. Preserve the exact hash;
update handoff status and URL only after exact upload. A UI PR body includes the following only after
an explicitly requested video/evidence attachment has completed the full lifecycle:

```markdown
## Visual Evidence
[PR evidence video](<authorized Conversation or artifact link>)
```

When a UI delivery has no explicit video/evidence request, use the exact text below and do not block
delivery on missing video or artifact:

```markdown
## Visual Evidence
Not requested (video evidence is opt-in)
```

For a non-user-visible change, use `Not required (non-user-visible change)` instead. `pr_number` may
remain null until the PR exists.

## Commit

1. Require a passed risk-routed gate with `approved_subagent` and no unresolved P0-P2 for non-trivial changes.
2. Inspect status, staged/unstaged diffs, and recent commit conventions.
3. Stage only relevant files and split unrelated or formatting-only work before freezing or verifying review evidence. In an active `parallel-worktree` lifecycle, request `pw-helper stage-scope` instead of running `git add` directly.
4. Use repository commit conventions, falling back to `<type>(<scope>): <subject>`.
5. Commit only with explicit authorization. A plain commit request stops after reporting SHA, message, verification, and review evidence. When the user explicitly authorized `PRまで`, continue through push and PR creation without another approval only while the reviewed fingerprint, target Issue, repository, base, and branch remain unchanged. In an active `parallel-worktree` lifecycle, save the approved message in its private registry message directory and request `pw-helper commit`; never run `git commit` directly.

## Create a Pull Request

1. Require a passed risk-routed gate with `not_required` or `approved_subagent`, no unresolved P0-P2, and a clean working tree.
2. Verify repository, base, branch, Issue target, state file, commit log, diff, and existing PRs all identify the same work. Ignore stale state files whose saved branch differs.
3. Stop on target mismatch or an existing PR for the same head branch.
4. Run the nearest relevant tests. For user-visible workflow changes, require the Coordinator's valid browser evidence packet, explicit human UI/behavior acceptance, an accepted_source_fingerprint match, and the verifier pass for that checkpoint; do not require a verifier-side browser rerun.
5. Include only checks actually run. Add compact Mermaid diagrams or safe screenshots only when they are independently allowed and materially aid review; video generation, attachment, or link is permitted only after an explicit video/evidence request. Durable behavior belongs in project specs too.
6. Push and create the PR only with explicit authorization. `PRまで` is sufficient authorization for commit, push, and PR creation as one bundle for the exact reviewed scope; show concise progress but do not stop between steps. Use `Closes #...` only for the verified target Issue. In an active `parallel-worktree` lifecycle, request `pw-helper push` and use its registered repo/base/head evidence for PR creation; never push an arbitrary ref directly.
7. Report the PR URL and stop.

## Merge Readiness

- Do not recommend or perform merge until every required CI check reports success.
- Pending, missing, cancelled, or failing required checks keep the merge gate closed.

## Cleanup After Merge Or Deploy

An explicit cleanup request authorizes one batch after verifying the merge/deploy result:

1. Inspect all worktrees, branches, dedicated containers/volumes, and the primary checkout status.
2. Stop and remove only the task-dedicated runtime environment.
3. Remove only clean merged worktrees.
4. Delete branches whose commits are reachable from the target, or whose non-reachable commits are proven patch-equivalent to the merged commits. Preserve everything else and report why.
5. Re-list worktrees and remaining resources, then report the compact cleanup result.

Suggested PR sections: Summary, Changes, Related Issues, Tests, Manual Verification, and Evidence. Never expose secrets or private customer data in evidence.
