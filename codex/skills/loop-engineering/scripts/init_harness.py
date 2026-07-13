#!/usr/bin/env python3
"""Initialize a project loop-engineering harness without overwriting files."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


SPEC = """# SPEC.md

このファイルは、このプロジェクトで期待される挙動の正本です。

## スコープ

- プロジェクト:
- 主な利用者:
- 重要なワークフロー:

## 挙動境界

| 境界 | 期待される挙動 | 壊してはいけない不変条件 | 検証 |
| --- | --- | --- | --- |
| 例 | 何が起きるべきか | 何を壊してはいけないか | HARNESS.md の検証へリンク |

## 完了条件

- [ ] 挙動が明確になったら、観測可能な完了条件を追加する。

## 対象外

- 曖昧な実装を防ぐため、必要に応じて非目標を明記する。

## 未解決の質問

- 自信を持った実装を妨げるプロダクト・技術上の質問を追加する。
"""


HARNESS = """# HARNESS.md

このファイルは、このプロジェクトが挙動をどう観測・再現・テスト・検証するかを記録します。

## 検証マップ

| 挙動 / リスク | センサー | コマンドまたは手順 | 所有者 / メモ |
| --- | --- | --- | --- |
| 例 | unit / feature / browser / log / metric / eval | `command` または手動手順 | メモ |

## 標準チェック

```bash
# このリポジトリで最小限有用な検証コマンドを追加する。
```

## TDD ループ

| 挙動 | 失敗テスト | 最小実装 | リファクタ確認 | コマンド |
| --- | --- | --- | --- | --- |
| 例 | 期待通りに red になるテスト | green にする最小変更 | 既存挙動が維持される確認 | `command` |

## 再現レシピ

### 例

1. 準備:
2. 操作:
3. 観測:
4. 期待:

## ブラウザ / 手動確認

- まだ完全自動化できないユーザー可視ワークフローを追加する。

## Fixture / Seed / Test Data

- 繰り返し可能な検証に必要な安定データを追加する。

## 観測性

- ログ:
- メトリクス:
- ダッシュボード:
- クエリ:

## 既知のギャップ

- [ ] 不足しているセンサーや flaky な領域を追加する。

## ハーネス成熟度

現在のレベル: 0

- 0: 場当たり的
- 1: チェック名がある
- 2: 挙動と検証が紐づいている
- 3: 回帰に強い
- 4: 自己改善する
"""


RETRO = """# RETRO.md

このファイルは、失敗、学び、ハーネス改善を記録します。

## ループログ

### YYYY-MM-DD - タイトル

- 仮説:
- 変更 / 実験:
- 検証:
- 結果:
- 次:
- 昇格先:

## 再発した失敗クラス

| 失敗 | 回数 | 検知 | 予防 |
| --- | ---: | --- | --- |
| 例 | 1 | 現在のセンサー | 提案するハーネス改善 |

## 昇格したルール

- `SPEC.md`, `HARNESS.md`, `AGENTS.md`, hooks, tests, skills へ移したルールを追加する。
"""


FILES = {
    "SPEC.md": SPEC,
    "HARNESS.md": HARNESS,
    "RETRO.md": RETRO,
}


def git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    root = result.stdout.strip()
    return Path(root) if root else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize SPEC.md, HARNESS.md, and RETRO.md without overwriting existing files."
    )
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to git root or cwd.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    root = args.root or git_root(Path.cwd()) or Path.cwd()
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []

    for name, content in FILES.items():
        path = root / name
        if path.exists() and not args.force:
            skipped.append(name)
            continue
        path.write_text(content, encoding="utf-8")
        created.append(name)

    print(f"Root: {root}")
    if created:
        print("Created:")
        for name in created:
            print(f"- {name}")
    if skipped:
        print("Skipped existing files:")
        for name in skipped:
            print(f"- {name}")
    if not created and not skipped:
        print("No files processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
