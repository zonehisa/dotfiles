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

User-visible UI changes require PR video evidence; screenshots are optional supplements and never
substitutes. Backend, configuration, and documentation-only changes are excluded. The
`implementer_luna` coordinates browser-verification readiness but never makes the final presentation,
privacy, or upload decision. `verifier_luna` captures local evidence at a coherent checkpoint only
after human UI/behavior acceptance evidence and accepted_source_fingerprint match; before then it may
only perform non-mutating baseline, test-map, log-shape, or browser-plan checks. It calls
`$pr-evidence-video`; the Coordinator owns the final decision. Final evidence must be
revalidated against the pushed HEAD and inherited patch fingerprint, and any head, artifact, or
fingerprint change stops upload. Conversation upload is browser/UI-only; no API or `gh` pretend
upload is allowed.

## User-visible UI workflow order

The following order applies only to user-visible UI changes. Non-UI changes keep the existing flow.
Use explicit checkpoint/evidence wording; do not add a complex persisted state mechanism.

1. Implementation/IAB loop: `implementer_luna` iterates implementation, in-app browser (IAB) checks, and micro-adjustments until a coherent candidate is ready. Do not start completion review during the implementation/IAB loop.
2. Human UI/behavior acceptance: the Coordinator presents the exact candidate at a coherent checkpoint to a real human/user. Only a real human/user may provide explicit combined UI acceptance for appearance and primary behavior. The Coordinator records explicit human UI/behavior acceptance evidence tied to `checkpoint_token` and `checkpoint_scope`. The Coordinator records an ephemeral `accepted_source_fingerprint` at acceptance time for the exact `checkpoint_scope`. The fingerprint covers source content plus staged/unstaged/untracked inventory. The acceptance-time accepted_source_fingerprint is read-only evidence. AI agents may not proxy or assume this acceptance. Human feedback resumes the same saved implementer/IAB loop; do not start verifier or reviewer yet.
3. Verifier technical verification: only after explicit human UI/behavior acceptance evidence tied to `checkpoint_token` and `checkpoint_scope` and a read-only accepted_source_fingerprint comparison, `verifier_luna` verifies the same accepted checkpoint through tests, logs, IAB/objective behavior, and source before/after integrity. Repeat the accepted_source_fingerprint comparison in before/after evidence. A mismatch invalidates the acceptance and returns to the same implementer/IAB loop and human gate. It does not decide subjective appearance or usability acceptance. Tool-generated artifacts outside the exact checkpoint scope do not invalidate the accepted source fingerprint.
4. Completion review: only after verifier passes, freeze, stage, and fingerprint the accepted scope before starting the Luna/max completion review. If verifier finds a problem or later source changes affect user-visible appearance or behavior, return to the same implementer/IAB loop and require combined human acceptance again before verifier. Purely non-user-visible verification artifact changes do not invalidate human acceptance.

## Speed-first implementation delegation

- Coordinatorは親1つに対して同時に最大3つの子agentまでを使える。この上限は`implementer_luna`、`explorer_luna`、`verifier_luna`だけでなく、既存の`git_operator_luna`と`reviewer_luna`を含む全delegated roleの合計に適用する。実装ライフサイクルでは、独立した調査がある場合に`implementer_luna`、`explorer_luna`、`verifier_luna`を並列化するが、writerは常に`implementer_luna`の1つだけにする。`verifier_luna`の実装結果検証はcoherentな実装checkpoint後に行い、開始時は安全な非変異baseline、test map、browser planだけを独立実行できる。
- `implementer_luna`、`explorer_luna`、`verifier_luna`はすべてGPT-5.6 Luna、`max`を使う。`implementer_luna`は`workspace-write`で実装、source edit、targeted test、browser verification orchestrationを所有する。`explorer_luna`はread-onlyのboundedなcode/contract/impact調査だけを行い、`verifier_luna`は開始時の非変異baseline／test map／browser planとcheckpoint後のtargeted test、log分析、browser確認だけを行う。verifierの`workspace-write`はログ、スクリーンショット、coverageなどtool-generated artifact専用で、source／production code／test／設定は編集しない。
- 新規implementation lifecycleは`fork_turns = "none"`と最小context packetで起動する。packetにはrepository、Issue/branch/base、current state、acceptance criteria、risk、明示された権限だけを入れ、同じlifecycleのfix、test follow-up、browser follow-upには保存済みの同じ`implementer_luna` agent IDを再利用する。
- Checkpoint handoffは直列化する。`implementer_luna`が明確な`checkpoint_token`と正確な`checkpoint_scope`（source pathとacceptance criteria）を返したら、Coordinatorは保存済みimplementerをpauseし、scopeの`git status --short`／`git diff`をbefore evidenceとして記録する。Verifierのimplementation-result check中はsource-mutatingなimplementer workを実行せず、verifierはbefore/after Git status/diff evidenceを記録する。source-treeが変われば結果をinvalidとし、Coordinatorはverifier完了後にだけ同じimplementerをresumeする。checkpoint前の独立した非変異baseline／test map／browser planは許可する。
- 子agentは別のwriterをspawnせず、nested delegationを行わない。explorer/verifierは実装を代行せず、implementation agentはGit workflowやcompletion reviewを代行しない。実装agentはstage、commit、push、PRを行わず、Gitは既存の`git_operator_luna`、completion reviewは別のfresh-context `reviewer_luna`へ分離する。
