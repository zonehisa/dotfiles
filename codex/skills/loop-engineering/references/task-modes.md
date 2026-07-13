# Task Modes

## Debugging

再現または代替sensorを作り、期待と実際が分岐する地点を特定する。最小の失敗testを追加して原因だけを直し、再現と隣接regressionを確認する。

## TDD / feature

観測可能な挙動と受入条件を1つ選び、既存test patternを調べる。期待理由でREDになる最小test、GREENにする最小実装、同じtestでのrefactorの順に進める。意味のあるedgeだけ1-2件追加する。UI-onlyはbrowser sensorを使い、binding、条件、保存、queryならTDDへ昇格する。

## Refactoring

既存挙動をtest/snapshot/comparisonで固定し、小さく構造を変え、同じ検証を繰り返す。依頼されていない挙動変更を混ぜない。

## Incident / repeated failure

緩和と原因を分け、timeline、impact、detection、contributing factors、follow-upを記録する。再発をtest/scriptへ、観測した失敗をRETROへ昇格する。

## Process improvement / decision

system境界、baseline、評価軸またはmetricを決め、最小の可逆実験を行う。事実、仮定、制約、好みを分け、何が結論を変えるかを残す。

## LLM / agent workflow

成功条件とsmall golden setを先に作る。behavior、boundary、intent、tool call、failure modeで例をtagし、1変数ずつ変更する。quality、latency、cost、tool successを必要に応じて測る。

## Verification selection

- Pure logic: unit test
- Cross-boundary behavior: feature/integration test
- UI: browser check
- API/provider: contract test
- Generated output: snapshot/golden
- Production-like behavior: log/metric/query
- LLM/routing/tool use: eval/golden set
