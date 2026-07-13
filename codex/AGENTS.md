# Global Development Rules

- 既存差分をユーザー作業として保護し、無関係なstash、reset、clean、整形、stage、commitを行わない。
- Issue、commit、push、PR、review投稿、mergeなど外部・配送操作は、`git-workflow`の明示承認境界に従う。
- 非自明なcode変更は、完了・commit・PR前に実装担当と別の新規Codex taskで凍結差分全体をreviewする。self-reviewやsubagentで代替しない。
- Reviewは実装loopごとに行わず、最終配送境界へまとめる。P0-P2が残る間は配送しない。
- Review後に非自明な差分が変われば証跡を無効化し、同じreview taskへ再提出する。
- 新しい不具合classはprojectのtest/HARNESSへ、review後の見逃しはRETROへ昇格する。
- Repoの`AGENTS.md`、policy、Skill、READMEを読み、より具体的なruleを優先する。
- Multi-repoは`issue-orchestrator`、明示選択された隔離Worktree lifecycleは`parallel-worktree`へ委譲する。

完了報告にはreview task、round、finding分類、追加sensor、検証、未検証範囲を含める。
