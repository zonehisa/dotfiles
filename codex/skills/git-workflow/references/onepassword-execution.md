# 1Password CLI の実行窓口

1Password CLI から秘密情報を取得する処理、または任意の補助ツール Jev を使う時だけ読みます。
目的は同じタスク内の重複認証や、補助ツールの認証による滞留を減らすことです。
既存の Coordinator/main を窓口にし、新しい認証agent、独立task、常駐サービスは作りません。
別タスクとのsession共有、Keychainへの移動、SSH agent／Git署名、ブラウザログインは今回の対象外です。

## Jev を使えない場合

Jev は任意の補助であり、検証の必須基盤ではありません。以下を認証依頼・再認証の手順より先に適用します。

- キー・参照が未設定、1Password の認証失敗・キャンセル、Jev 側の認証拒否では、その作業は Jev を使わず続けます。
  Jev のためだけに認証を自動再試行したり、別agentへ切り替えたり、鍵を移動・複製したりしません。
- 必要な lint・typecheck・unit/E2E は既存のテストcommandで、UI は Coordinator/main の通常の IAB 確認で検証します。
  review後の最終候補・human acceptance等の既存条件は維持します。通常経路でも失敗・実行不能ならその検証を失敗・未検証として報告し、
  Jev 不使用を理由に省略・成功扱いしません。IAB から別ブラウザへの自動fallbackも行いません。
- 既にjobを開始していた場合は、そのstatusと結果を確認します。結果不明のUI操作・外部writeは通常経路でも重複実行しません。
- 報告には Jev 不使用の理由と代わりに実行した検証を短く記載します。Jev 連携自体の検証が明示された場合、
  通常経路の成功で代替せず、その受入条件を未検証として残します。

この分岐は Jev の補助利用だけに適用します。業務API・Git等の必須認証を省略・迂回するものではありません。

## 処理単位で依頼する

- 子は `op read`／`op run`／`op signin` を実行せず、API呼出し一回ごとではなくテスト一式等のjobを親へ返します。
  依頼には目的、正確なcommandとcwd、必要な環境変数名と既知の `op://` 参照、送信先、許可された作用を含めます。
  参照が不明ならユーザーへ必要な項目を確認し、vault全体を探索しません。キーの実値は要求しません。
- 親はcommandの内容・実行対象がユーザーの依頼と一致するか確認します。1Passwordの解除はpublish、課金、
  任意の外部送信、scope拡大の認可ではありません。sandbox、review gate、writerの担当はそのまま維持します。
  Git/GitHub外部writeは既存operatorが正確な対象・commandを準備し、親はそのまま実行して結果を返します。
  単一writerのsource edit等、親が実行できないjobは元の担当境界へ戻し、認証集約を理由に代行しません。
- 秘密情報が不要なlint、unit test、read-only調査等は元の担当で続けます。依存しない処理まで直列化しません。
  commandは既存のproject手順から通常どおり解決し、認証集約のためだけの再確認はしません。

## 同じ端末sessionで実行する

1. 親は公開されたterminal toolで再利用可能なPTY/sessionを確保し、返されたsession IDを保持します。
   現行の `exec_command` なら `tty=true` でshellを維持し、以後はそのIDへの `write_stdin` でjobを送ります。
   同じagent IDだけでは認証共有になりません。毎jobで新しいterminal sessionを作りません。
   再利用のためにshell全体を昇格させず、個別commandの承認経路を優先します。別sessionなら再認証があり得ます。
2. 必要な `op://` 参照だけを指定した `op run -- <job-command>` でjobの子プロセスへキーを渡します。
   親shellには参照だけを置き、キーの実値をexportして残したり、子agentへ配布したりしません。
   job終了後にその環境変数が後続jobへ継承されるとは扱いません。次のjobも同じ端末から `op run` します。
3. 1Passwordの対話確認はユーザーが行います。確認待ちの同じjobに対し、追加の認証commandや重複jobを起動しません。
   raw keyを表示するcommand、shell trace、環境変数一覧、秘密値入りの引数・チャット・ログ・一時ファイルは使いません。
   `op run` の標準maskingを維持し、返す結果にも秘密情報が含まれていないか確認します。
4. 子へは終了status、必要な検証結果、秘密情報を除いたエラーだけを返します。処理が成功したか不明なら、
   同じjobのstatusとread-onlyな結果確認を優先し、外部writeを再実行しません。
   「失敗」表示だけでは未実行の証拠になりません。再試行の安全性・認可は既存workflowに従って別途判断します。
5. 親が作ったsessionは当該作業の終了時に通常終了します。認証不要な作業のために維持せず、keepaliveや
   ロック設定の変更で認証期限を延ばしません。sessionを再開できなければ親から事情を説明し、必要時に再認証します。
   再利用不可のtool環境では「認証共有済み」とせず、jobを一度の起動にまとめられる範囲だけまとめます。

## 試行と限界

macOS/Linuxの1Password CLI認証は端末session単位で、その配下のsub-shellには共有されます。
10分間使わない場合、12時間の上限、または1Passwordのロックで再認証が必要になります。
Windowsではsub-shellも別認証になり得るため、同じ削減効果を前提にしません。
認証期限／ロック後に新しく秘密情報を取得する際は通常どおりユーザーに確認します。

試行結果はjob数、使用session数、実際に確認できた認証回数、待ち時間を短く報告します。
画面上の確認回数を観測できなければ「未計測」とし、command成功数から推定しません。
模擬jobでのsession再利用確認と、実際の1Password認証削減は別の結果として扱います。
今回の変更は手順の指定であり、tool呼出しの機械的な遮断や無確認実行を保証するものではありません。

公式仕様: [認証session](https://www.1password.dev/cli/app-integration-security)、
[`op run`](https://www.1password.dev/cli/reference/commands/run)。
