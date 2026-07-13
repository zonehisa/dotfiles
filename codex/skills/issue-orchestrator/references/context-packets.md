# Context Packets

必要な事実だけを渡す。実装者の結論や「問題なさそう」という評価を含めない。

```text
Target:
- issue:
- repository:
- base / branch / Worktree:
- canonical spec:

Role:
- coordinator / implementer / contract guard / reviewer

Goal and acceptance criteria:
-

Allowed scope:
-

Forbidden:
- unrelated dirty work
- unapproved external mutations
- contract assumptions not in the canonical source

Verification:
- commands / expected evidence

Completion report:
- summary
- contract delta
- tests and results
- unverified scope
- follow-up repositories
- commit / PR
```

Independent reviewerにはIssue/criteria、base/head、changed paths、fingerprint、testsだけを渡す。Implementation reasoningや事前評価を渡さない。
