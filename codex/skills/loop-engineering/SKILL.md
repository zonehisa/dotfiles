---
name: loop-engineering
description: "Run hypothesis-driven improvement loops for TDD, debugging, feature work, refactoring, incidents, process improvement, research, decisions, experiments, LLM workflows, SPEC, HARNESS, and RETRO. Japanese triggers include TDD, テスト駆動開発, ループ, ハーネス, 仮説検証, 再現, 検証, 振り返り, 業務改善, 実験設計."
---

# Loop Engineering

日本語で、観測、仮説、最小変更/実験、検証、学習昇格の順に進める。

## Core contract

1. 現在のsystem、仕様、既存sensorを観測する。
2. 1つの検証可能な仮説を置く。
3. 仮説を判定できる最小変更または実験を行う。
4. 最も近く安い検証を実行する。
5. 結果と次の判断を記録する。
6. 再利用できる学びだけproject harnessへ昇格する。

Typos、comments、明白なformat以外に適用する。2 loop連続で新情報がなければ、観測点を増やすか狭い質問を1つ行う。

```text
仮説:
変更/実験:
検証:
結果:
次:
ハーネス更新:
```

## Route

- Debug/TDD/feature/refactor/research/experiment/agent workflow: read [references/task-modes.md](references/task-modes.md).
- Harness設計、SPEC/HARNESS/RETROへの昇格、incident: read [references/loop-principles.md](references/loop-principles.md).

Repository既存のAGENTS、SPEC、HARNESS、RETROを優先する。Git、model routing、独立review、PRは`git-workflow`へ委譲し、このSkillで重複定義しない。
