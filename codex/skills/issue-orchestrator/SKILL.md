---
name: issue-orchestrator
description: Coordinate cross-repository or cross-thread Issue implementation. Use for multiple repos, API/schema/contracts, repo-specific Worktrees, Codex task coordination, implementer/guard roles, or preventing cross-project drift while preserving each repository workflow.
---

# Issue Orchestrator

Issueを追跡単位のまま、複数repositoryのscope、Worktree、契約、検証、完了報告を調整する。各repoの実装/TDD/Git/reviewはrepo policyと`git-workflow`へ委譲する。

## 1. Classify

- 影響repositoryと変更理由
- canonical Issue/spec/code
- contract/API/schemaの有無
- 各repoのbranch、Worktree、dirty状態、既存PR/task
- 必要role: coordinator、repo implementer、contract guard

単一repoなら通常workflowへ戻す。不確かなrepoへbranch/taskを作らない。

## 2. Isolate

- Repoごとにstatus、remote default、Worktrees、Issue/PRを調べる。
- 別作業のdirty差分をswitch/stashせず、必要なら隔離Worktreeを使う。
- 同じIssue/branch/PR/taskを重複作成しない。
- `parallel-worktree`が明示選択され所有registryがある場合は、そのhelperへGit mutationを委譲する。
- Worktree作成に失敗してもcurrent Worktreeへfallback、自動削除、強制cleanupをしない。

## 3. Coordinate

Thread/task作成はユーザーが明示的に求めた場合だけ行う。作成する場合は[references/context-packets.md](references/context-packets.md)の短いpacketを使い、owner、allowed scope、forbidden scope、expected reportを固定する。

Cross-repo契約は1つのcanonical sourceを決め、各repoのmock/fixture/testとの差をmachine checkへ昇格する。

## 4. Verify and finish

- 各repoから変更、contract delta、tests、未検証、commit/PRを収集する。
- 実装loop中に独立reviewを繰り返さず、配送境界で`git-workflow`のrisk別reviewを行う。
- Cross-repo task全体は最高riskを使う。
- 全repoの報告と契約を照合してから完了を報告する。

Issue作成、comment、push、PR、mergeは個別の明示承認なしに行わない。
