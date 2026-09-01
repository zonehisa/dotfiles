# Global Development Workflow

## Risk-Routed Diff Review Gate

- typo、文言、コメント、明白な整形だけのR0を除き、コード変更やPR準備を完了扱いにする前に未コミット差分全体をレビューする。混在差分は最高riskを使い、UIでもイベント、binding、条件、navigation、data accessを含めばR2以上とする。
- `git-workflow`のcompletion reviewを除くGit/GitHubの調査、target resolution、command preparation、非approval-bound実行は`git_operator_luna`サブエージェントを使う。`fork_turns = "none"`、GPT-5.6 Luna `max`、workspace-writeとし、repository、Issue/branch/base、要求operation、現在state、ユーザーが与えた正確な権限だけをcontext packetで渡す。同じworkflow lifecycleの承認後follow-upは保存したagent IDへ送る。
- If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.
- Coordinatorはユーザー対話と権限判断を保持し、packetにない権限をoperatorへ推測させない。operator自身のcompletion diffはreviewさせず、別のfresh-context `reviewer_luna`を使う。`git_operator_luna`を作成・確認できない場合はGit workflowを止め、Coordinatorや別modelへfallbackしない。
- R1〜R4は、実装履歴を渡さないfresh-contextの`reviewer_luna`サブエージェントを使う。`fork_turns = "none"`、GPT-5.6 Luna `max`、read-onlyとし、親の結論や安全そうな箇所を渡さない。review lifecycleごとに新規agentを作り、有効なreview後の再reviewは保存したagent IDへ`Round N`として依頼する。
- 新規review lifecycleではRound 1を全差分のfull review、Round 2を直前findingの修正差分と直接影響先に限定し、通常は最大2Roundとする。Round 3はユーザーの明示承認時だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡に限定して実行し、その結果で配送を停止して新規lifecycleを自動作成しない。
- reviewerは実装側の成功済みtestを再実行せず、Round 2で不変仕様、過去会話、過去tool outputを再読しない。証跡には既存の`review_fingerprint.py`だけを使う。
- 差分全体を確認できない状態またはfingerprint不一致のreviewは無効とし、差分を再stage・再固定して新しいfresh-contextの`reviewer_luna`でやり直す。P0〜P2やrisk再分類はroute変更条件にせず、Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡だけを同じagentへ再提出する。Round 3はユーザーの明示承認後だけ、未解決finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡に限定して実行し、その結果で配送を停止する。
- The review_context_key includes the immutable `threat_model_supported_use_declaration_hash`. Round 1, Round 2, and an authorized Round 3 packet carry that same declaration/hash. A changed declaration/hash invalidates the current review context and requires a new context before submission; do not reuse stale bounded review evidence.
- A new review lifecycle must not be started automatically after two completed review lifecycles in one unchanged delivery scope.
- After two completed review lifecycles in one unchanged delivery scope, a third full-review lifecycle is not started automatically.
- Stop additional patch layering and require architecture/scope simplification plus an explicit user decision before any new lifecycle.
- An explicitly authorized Round 3 remains bounded and terminal; it must never trigger a fresh lifecycle.
- P0-P2 blockers must be grounded in a credible supported-use reproduction or a bounded code-path proof under the declared threat model and acceptance criteria.
- A runnable reproduction is not required when bounded proof exists.
- Purely theoretical or adversarial-local hardening outside supported use or the declared threat model is P3/residual risk unless the product explicitly supports hostile/multi-tenant conditions.
- Credible security/correctness risk remains blocking.
- Repeated P0-P2 findings in the same scope trigger architecture/acceptance-scope reconsideration, not additional defensive patches.
- 実装担当は`git status --short`でstaged / unstaged / untrackedを確認し、review対象全体だけをstageしてからbaseとstaged-tree指紋を記録する。未stage・未追跡は別管理し、同一目的の変更を残さない。指紋記録後は差分を固定する。Round 1ではレビュアーにIssue/仕様、base、branch、完全なstaged対象、指紋、実行済みtestを渡す。Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡だけを渡し、Round 3はユーザーの明示承認後だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、同じimmutable `threat_model_supported_use_declaration_hash`、成功済み証跡に限定する。各packetには同じimmutable `threat_model_supported_use_declaration_hash`を含める。
- レビュアーはFindings-firstで、正しさ・回帰・API/契約不整合・状態遷移・lock/権限・security/privacy・性能・保守性・test不足を優先する。progress narrationなしのfinal-only短報と指紋の復唱を要求し、Coordinatorは完了通知を1回待つ。定期的なbusy pollをしない。
- 指摘は採用・却下・要確認に分類する。採用した不具合は可能な限り最小の回帰testまたはsensorを先に追加してから修正し、対象全体を再stage・再固定する。P0〜P2が解消するまでgateを開かず、見解不一致はユーザー判断を仰ぐ。
- コミット直前に指紋を再計算し、最終review時と一致しなければ再reviewへ戻す。ただしbase移動前後の`patch_base_tree`と`patch_hash`が一致し、受け入れ条件・risk・対象fileが不変なら両fingerprintを証跡へ残して継承できる。dirtyなsubmoduleは個別reviewを要求する。コミット後は`index_matches_head`と内容hashを照合し、PR直前に現在のHEADと照合する。
- `reviewer_luna`サブエージェントを作成・確認できない場合は完了扱いを止める。別taskや別modelへfallbackしない。
- 新しい不具合classはproject testや`HARNESS.md`へ昇格する。review後の見逃しは`RETRO.md`に記録し、汎用的ならglobal skillへ昇格する。同種の誤検知が2回続いたreview観点は条件を具体化する。
- 最終報告では、riskと理由、review route、agent ID、model/effort、指紋、round数、指摘総数、採用・却下・要確認数、追加test/sensor、検証command、未検証範囲を短く明示する。

## PR evidence boundary

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
remain outside both the UI IAB/human gate and the opt-in video path.
A later explicit request for video/evidence for the same delivery enters the same full lifecycle and
authorization/fingerprint/head/privacy/upload boundaries; there is no automatic fallback or pretend
upload.

The `implementer_luna` prepares runnable state and browser-plan readiness while Coordinator/main is the
browser executor and owner. At a coherent implementation checkpoint, Coordinator/main owns the
provisional browser evidence packet. For user-visible UI only, `verifier_luna` validates the packet,
artifact identifiers/hashes, and source integrity read-only; it does not acquire or rerun the IAB
session. After verifier and completion review, Coordinator/main owns the final IAB, final packet, and
human UI/behavior acceptance. For an explicitly requested video/evidence attachment, the Coordinator
calls `$pr-evidence-video` and owns presentation, privacy, and upload decision. Final evidence
must be revalidated against the pushed HEAD and inherited patch fingerprint, and any head, artifact, or
fingerprint change stops upload. Conversation upload is browser/UI-only; no API or `gh` pretend upload
is allowed.

For an explicitly requested video/evidence attachment, the following recording and rendering lifecycle applies.
The Coordinator/main captures or references the local raw recording from its browser evidence packet.
For user-visible UI only, verifier_luna validates the packet, artifact identifiers/hashes, and source integrity read-only; it
does not acquire or rerun the IAB session.

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

## Speed-first implementation delegation

- Coordinatorは親1つに対して同時に最大3つの子agentまでを使える。この上限は`implementer_luna`、`explorer_luna`、`verifier_luna`だけでなく、既存の`git_operator_luna`と`reviewer_luna`を含む全delegated roleの合計に適用する。実装ライフサイクルでは、独立した調査がある場合に`implementer_luna`、`explorer_luna`、`verifier_luna`を並列化するが、writerは常に`implementer_luna`の1つだけにする。`verifier_luna`の実装結果検証はcoherentな実装checkpoint後に行い、開始時は安全な非変異baseline、test map、browser planだけを独立実行できる。
- `implementer_luna`、`explorer_luna`、`verifier_luna`はすべてGPT-5.6 Luna、`max`を使う。`implementer_luna`は`workspace-write`で実装、source edit、targeted test、browser verification orchestrationを所有する。`explorer_luna`はread-onlyのboundedなcode/contract/impact調査だけを行い、`verifier_luna`は開始時の非変異baseline／test map／browser planとcheckpoint後のCoordinator packet read-only validation、targeted test、log分析、objective non-browser checksだけを行う。verifierの`workspace-write`はログ、スクリーンショット、coverageなどtool-generated artifact専用で、source／production code／test／設定は編集しない。
- 新規implementation lifecycleは`fork_turns = "none"`と最小context packetで起動する。packetにはrepository、Issue/branch/base、current state、acceptance criteria、risk、明示された権限だけを入れ、同じlifecycleのfix、test follow-up、browser follow-upには保存済みの同じ`implementer_luna` agent IDを再利用する。
- Checkpoint handoffは直列化する。`implementer_luna`が明確な`checkpoint_token`と正確な`checkpoint_scope`（source pathとacceptance criteria）を返したら、Coordinatorは保存済みimplementerをpauseし、scopeの`git status --short`／`git diff`をbefore evidenceとして記録する。Verifierのimplementation-result check中はsource-mutatingなimplementer workを実行せず、verifierはbefore/after Git status/diff evidenceを記録する。source-treeが変われば結果をinvalidとし、Coordinatorはverifier完了後にだけ同じimplementerをresumeする。checkpoint前の独立した非変異baseline／test map／browser planは許可する。
- 子agentは別のwriterをspawnせず、nested delegationを行わない。explorer/verifierは実装を代行せず、implementation agentはGit workflowやcompletion reviewを代行しない。実装agentはstage、commit、push、PRを行わず、Gitは既存の`git_operator_luna`、completion reviewは別のfresh-context `reviewer_luna`へ分離する。
