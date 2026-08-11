# Global Development Workflow

## Risk-Routed Diff Review Gate

- typo、文言、コメント、明白な整形だけのR0を除き、コード変更やPR準備を完了扱いにする前に未コミット差分全体をレビューする。混在差分は最高riskを使い、UIでもイベント、binding、条件、navigation、data accessを含めばR2以上とする。
- `git-workflow`のcompletion review以外は`git_operator_luna`サブエージェントを使う。`fork_turns = "none"`、GPT-5.6 Luna `max`、workspace-writeとし、repository、Issue/branch/base、要求operation、現在state、ユーザーが与えた正確な権限だけをcontext packetで渡す。同じworkflow lifecycleの承認後follow-upは保存したagent IDへ送る。
- If the current agent is already running as `git_operator_luna`, execute the assigned operation directly; never recursively delegate or spawn another `git_operator_luna` operator.
- Coordinatorはユーザー対話と権限判断を保持し、packetにない権限をoperatorへ推測させない。operator自身のcompletion diffはreviewさせず、別のfresh-context `reviewer_luna`を使う。`git_operator_luna`を作成・確認できない場合はGit workflowを止め、Coordinatorや別modelへfallbackしない。
- R1〜R4は、実装履歴を渡さないfresh-contextの`reviewer_luna`サブエージェントを使う。`fork_turns = "none"`、GPT-5.6 Luna `max`、read-onlyとし、親の結論や安全そうな箇所を渡さない。review lifecycleごとに新規agentを作り、有効なreview後の再reviewは保存したagent IDへ`Round N`として依頼する。
- 新規review lifecycleではRound 1を全差分のfull review、Round 2を直前findingの修正差分と直接影響先に限定し、通常は最大2Roundとする。Round 3はユーザーの明示承認時だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡に限定して実行し、その結果で配送を停止して新規lifecycleを自動作成しない。
- reviewerは実装側の成功済みtestを再実行せず、Round 2で不変仕様、過去会話、過去tool outputを再読しない。証跡には既存の`review_fingerprint.py`だけを使う。
- 差分全体を確認できない状態またはfingerprint不一致のreviewは無効とし、差分を再stage・再固定して新しいfresh-contextの`reviewer_luna`でやり直す。P0〜P2やrisk再分類はroute変更条件にせず、Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡だけを同じagentへ再提出する。Round 3はユーザーの明示承認後だけ実行し、その結果で配送を停止する。
- 実装担当は`git status --short`でstaged / unstaged / untrackedを確認し、review対象全体だけをstageしてからbaseとstaged-tree指紋を記録する。未stage・未追跡は別管理し、同一目的の変更を残さない。指紋記録後は差分を固定する。Round 1ではレビュアーにIssue/仕様、base、branch、完全なstaged対象、指紋、実行済みtestを渡す。Round 2は直前finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡だけを渡し、Round 3はユーザーの明示承認後だけ、Round 2の未解決finding、修正差分、直接影響先、全差分fingerprint、成功済み証跡に限定する。
- レビュアーはFindings-firstで、正しさ・回帰・API/契約不整合・状態遷移・lock/権限・security/privacy・性能・保守性・test不足を優先する。progress narrationなしのfinal-only短報と指紋の復唱を要求し、Coordinatorは完了通知を1回待つ。定期的なbusy pollをしない。
- 指摘は採用・却下・要確認に分類する。採用した不具合は可能な限り最小の回帰testまたはsensorを先に追加してから修正し、対象全体を再stage・再固定する。P0〜P2が解消するまでgateを開かず、見解不一致はユーザー判断を仰ぐ。
- コミット直前に指紋を再計算し、最終review時と一致しなければ再reviewへ戻す。ただしbase移動前後の`patch_base_tree`と`patch_hash`が一致し、受け入れ条件・risk・対象fileが不変なら両fingerprintを証跡へ残して継承できる。dirtyなsubmoduleは個別reviewを要求する。コミット後は`index_matches_head`と内容hashを照合し、PR直前に現在のHEADと照合する。
- `reviewer_luna`サブエージェントを作成・確認できない場合は完了扱いを止める。別taskや別modelへfallbackしない。
- 新しい不具合classはproject testや`HARNESS.md`へ昇格する。review後の見逃しは`RETRO.md`に記録し、汎用的ならglobal skillへ昇格する。同種の誤検知が2回続いたreview観点は条件を具体化する。
- 最終報告では、riskと理由、review route、agent ID、model/effort、指紋、round数、指摘総数、採用・却下・要確認数、追加test/sensor、検証command、未検証範囲を短く明示する。
