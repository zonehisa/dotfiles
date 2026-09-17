# Issue preflight

Issue の OPEN、Issue 本文、PR の merge 状態、ブランチ名だけでは、実装が必要だとは判定しない。
Issue に紐づくコード変更を開始・再開・stage・commit・push・PR 準備する時は、
[`scripts/issue_preflight.py`](../scripts/issue_preflight.py) の証跡を作る。`pw-helper` が管理する
active lifecycle は同じ helper を通し、repo-local runner が管理する lifecycle は同じ collect/validate/
pre-PR 契約をその runner から適用する。既存の管理元を変えたり二重管理したりしない。
Issue と無関係なローカル変更に Issue 番号を要求する規則ではない。

## 収集と判定

`collect` は一回の `git fetch origin` の後に、origin の live target、Issue 本文、Issue の timeline、
同じ owner/repository の Related PR を全状態で収集する。current branch が target branch と異なる場合は
その branch head の PR も全状態で確認する。timeline の typed cross-reference、同じ repository の PR URL、
`Related to #N`/`PR #N` を使って関連を確定する。`Depends on #N` のような通常の Issue 参照は PR として扱わない。
API、fetch、ページ上限、repository binding のどれかが検証できなければ
`unknown` と記録し、空の結果に置き換えない。

判定は二段階にする。

1. まず criteria を assessment なしで収集し、対象の最新ソース、テスト、Issue の要求を読む。
2. 各 requirement に対する判断を、同じ収集結果の `current_target.sha` と
   `issue_relevant.sha256` に結び付けて入力し、再収集する。

判断の意味は次の通り。

- `satisfied`: 要求を満たすと判断した。`rationale`、`residual_scope`、現在の source/search/test
  evidence が必要で、引用された path/blob は対象 SHA に結び付く。
- `missing`: 要求に確認済みの残作業がある。同じ証跡を残す。
- `unknown`: assessment の欠落・古さ、対象/API/fetch の失敗、証拠の不一致など。読み取り調査を続け、
  実装許可へ変換しない。

criteria の最小例（SHA は実際の収集結果を入れる）は次の形にする。

```json
[
  {
    "id": "behavior",
    "requirement": "保存時に検証結果を表示する",
    "source": [{"path": "app/feature.py", "exists": true}],
    "search": [{"path": "app/feature.py", "literal": "validate", "min_count": 1}],
    "tests": [{"path": "tests/test_feature.py", "exists": true}],
    "assessment": {
      "status": "missing",
      "rationale": "最新 target の実装とテストを確認したが保存時の表示経路がない",
      "residual_scope": "保存処理と回帰テストの追加",
      "assessed_target_sha": "<current_target.sha>",
      "assessed_issue_relevant_sha256": "<issue_relevant.sha256>",
      "evidence": [
        {"kind": "source", "path": "app/feature.py"},
        {"kind": "search", "path": "app/feature.py", "literal": "validate"},
        {"kind": "test", "path": "tests/test_feature.py"}
      ]
    }
  }
]
```

ファイルの存在、キーワード、テストファイルの存在は assessment の意味を代替しない。test の
`command`/`argv` は実行せず、証跡の入力にも arbitrary shell を入れない。`satisfied` の全 requirement
なら `no_edit_or_pr=true` とし、編集・PR を作らない。`needs_work` は `missing` が全て最新の事実で
裏付けられた時だけ返る。

作成時の creation base は `creation_base` として保存し、再開時に現在の head で上書きしない。standalone の
`collect` に `--base` がない場合は `creation_base.status=unknown`/`reason=not_provided` と記録する。
`current_target` は `refs/remotes/origin/<branch>` に解決し、local branch、tag、SHA を live target として
使わない。Issue 内容の relevant hash、target SHA、source blob、repository host/owner/name は再検証時に
一致しなければ古い証跡として無効にする。

例:

```bash
python3 codex/skills/git-workflow/scripts/issue_preflight.py collect \
  --repo . --issue 106 --target main --base <creation-base-sha> \
  --criteria-file criteria.json --output preflight.json
python3 codex/skills/git-workflow/scripts/issue_preflight.py validate \
  --repo . --evidence-file preflight.json
```

active lifecycle では次を使う。

```bash
pw-helper preflight-collect ...
pw-helper preflight-validate ...
pw-helper pre-pr ...
```

`pw-helper` は implementing への遷移、resume、stage、commit、push、pre-PR で、同じ lock の下で
fetch/API を再確認する。`satisfied` と `unknown` は書き込みを止め、古い implementing 状態を resume の
許可として保存しない。`pre-pr` は current base と submitted head、clean worktree、隔離した
`git merge-tree` の conflict と merge 後の effective delta を検証する。証拠 packet なしの `pre-pr` は
read-only の診断もしくは `unknown` であり、readiness PASS ではない。pre-PR の `--base` は packet の
`current_target.ref` と SHA に一致させる。repo-local runner 管理の lifecycle も同じ再収集・検証契約を適用する。
source-level のこの gate は
任意の外部ツールの shell 実行を横取りするものではない。
