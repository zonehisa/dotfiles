# Global Development Workflow

## Independent Diff Review Gate

- R0 / R1は独立AI review不要とする。ただしR1はbehavioral bindingのない静的表示変更に限定する。R2以上はコード変更やPR準備を完了扱いにする前に、実装担当とは別の新規Codex taskでレビューし、self-reviewや同じ会話を継承したsubagentで代替しない。
- 実装担当は `git status --short` で staged / unstaged / untracked を確認し、review対象全体だけをstageしてからベースコミットとstaged-tree指紋を記録する。未stage・未追跡は指紋対象外として別管理し、同一目的の変更を残さない。指紋記録後は差分を固定し、レビュー中は変更しない。新規タスクには Issue/仕様、ベースブランチ、作業ブランチ、staged対象差分、指紋、実行済みテストだけを渡し、実装時の結論や問題がなさそうという評価を渡さない。
- 独立reviewは`repository + Issue/branch + base + reviewer_role`ごとにCodex taskを1件だけ使う。保存済み`task_id`、なければ完全一致する最古taskを正本とし、他taskへ送信しない。差分・受け入れ条件・risk・対象fileが同じroundだけ二重送信せず、変更時は正本taskへ`Round N`として再reviewを依頼する。
- v1.1-liteは新規review lifecycleだけに適用する。Round 1はfull review、Round 2は前回findingの修正差分と直接影響先だけとし、通常は最大2Roundとする。Round 3はユーザーの明示承認時だけ実行し、P0〜P2が残れば停止して新規lifecycleを自動作成しない。
- reviewerは実装側の成功済みtestを再実行せず、Round 2で不変仕様、過去会話、過去tool outputを再読しない。証跡には既存の`review_fingerprint.py`だけを使う。
- レビュアーは読み取り専用とし、Findings-first で、正しさ・回帰・API/契約不整合・状態遷移・ロック/権限・セキュリティ/プライバシー・性能・保守性・テスト不足を優先して確認する。
- 指摘は実装担当が採用・却下・要確認に分類する。採用した不具合は、可能な限り最小の回帰テストまたは検知手段を先に追加してから修正し、対象全体を再stageして指紋を固定し、許可された次Roundで同じreview taskへ依頼する。コミット直前に指紋を再計算し、最終review時と一致しなければ配送を停止する。ただしbase移動前後の`patch_base_tree`と`patch_hash`が一致し、受け入れ条件・risk・対象fileが不変なら、両fingerprintを証跡へ残してreviewを継承できる。dirtyなsubmoduleは個別reviewを要求する。コミット後は`index_matches_head`とフック実行後の内容hashが一致し、review対象の残存差分がない場合だけ最終commit SHAをreview証跡へ結び付け、PR直前に現在のHEADと照合する。P0〜P2が残る状態ではcommit・PRを許可せず、見解不一致はユーザー判断を仰ぐ。
- 新規 Codex タスクを作成・確認できない環境では完了扱いを止め、ユーザーへ独立レビューの作成を依頼する。セルフレビューやサブエージェントへフォールバックしない。
- 新しい不具合クラスはプロジェクトのテストや `HARNESS.md` へ昇格する。レビュー後の見逃しは `RETRO.md` に記録し、汎用的ならグローバル skill へ昇格する。同種の誤検知が2回続いたレビュー観点は条件を具体化する。
- レビュアーにはprogress narrationなしのfinal-only短報を要求し、Coordinatorはstatusだけを静かにpollする。
- merge、deploy、または明示中止後のcleanupでは、review結果とtask IDを記録してから完了review taskと完了済み重複taskをarchiveする。実行中、未読、結果未回収、唯一の証跡は残す。
- 最終報告では、レビュータスク、レビュー回数、指摘総数、採用・却下・要確認数、追加したテスト/センサー、検証コマンド、未検証範囲を短く明示する。
