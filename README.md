# dotfiles

macOS を主対象にした開発環境設定のリポジトリです。

## 含まれるもの

- `zsh`: [`.zshrc`](./.zshrc)
- `Homebrew`: [`Brewfile`](./Brewfile)
- `sheldon`: [`.config/sheldon/plugins.toml`](./.config/sheldon/plugins.toml)
- `zeno`: [`.config/zeno/config.yml`](./.config/zeno/config.yml)
- `starship`: [`.config/starship.toml`](./.config/starship.toml) ほか 2 ファイル
- `tmux`: [`.config/tmux/tmux.conf`](./.config/tmux/tmux.conf)
- `git`: [`.config/git/ignore`](./.config/git/ignore)
- `gh`: [`.config/gh/config.yml`](./.config/gh/config.yml)
- `lazygit`: [`.config/lazygit/config.yml`](./.config/lazygit/config.yml)
- `nvim`: [`.config/nvim/`](./.config/nvim)
- `wezterm`: [`.config/wezterm/`](./.config/wezterm)
- `alacritty`: [`.config/alacritty/alacritty.toml`](./.config/alacritty/alacritty.toml)
- `AeroSpace`: [`.config/aerospace/aerospace.toml`](./.config/aerospace/aerospace.toml)
- `Karabiner-Elements`: [`.config/karabiner/karabiner.json`](./.config/karabiner/karabiner.json)
- macOS 用補助スクリプト: [`bin/`](./bin)
- Codex Skills: [`codex/skills/`](./codex/skills)

## セットアップ

### macOS

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
chmod +x setup.sh
./setup.sh link
```

`setup.sh` は既存ファイルを `*.bak.YYYYMMDD_HHMMSS` として退避してから、dotfiles へのシンボリックリンクを作成します。

初回に手元の設定をこのリポジトリへ取り込みたい場合は:

```bash
./setup.sh init
```

`init` は `LINKS` に定義された対象だけを `~/` からこの repo へコピーします。既に repo 側にあるファイルは上書きしません。

Codexの設定とSkillsは次へリンクされます。

- `codex/skills/parallel-worktree` → `~/.agents/skills/parallel-worktree`
- `codex/skills/git-workflow` → `~/.codex/skills/git-workflow`
- `codex/skills/pr-evidence-video` → `~/.codex/skills/pr-evidence-video`
- `codex/agents/implementer-luna.toml` → `~/.codex/agents/implementer-luna.toml`
- `codex/agents/explorer-luna.toml` → `~/.codex/agents/explorer-luna.toml`
- `codex/agents/verifier-luna.toml` → `~/.codex/agents/verifier-luna.toml`
- `codex/agents/git-operator-luna.toml` → `~/.codex/agents/git-operator-luna.toml`
- `codex/agents/reviewer-luna.toml` → `~/.codex/agents/reviewer-luna.toml`

実行時registry、lock、evidenceは`${CODEX_HOME:-$HOME/.codex}/parallel-worktree`、Worktreeはadapterごとの管理領域に保持され、dotfilesでは管理しません。

実装時はGPT-5.6 Luna `max`の`implementer_luna`を唯一のwriterとして使います。独立したcode／contract／impact調査はread-onlyの`explorer_luna`、開始時の安全な非変異baseline／test map／browser planと実装checkpoint後のtargeted test／log／browser確認は`verifier_luna`へ分離します。実装checkpoint後はimplementerをpauseし、verifierがscopeのbefore/after Git status/diff evidenceを記録します。親から起動できる子agentは最大3つ（Git／review roleを含む全delegated roleの合計）で、nested delegationは行いません。

### User-visible UI workflow order

The following order applies only to user-visible UI changes. Non-UI changes keep the existing flow.
Use explicit checkpoint/evidence wording; do not add a complex persisted state mechanism.

1. Implementation/IAB loop: `implementer_luna` iterates implementation, in-app browser (IAB) checks, and micro-adjustments until a coherent candidate is ready. Do not start completion review during the implementation/IAB loop.
2. Human UI/behavior acceptance: the Coordinator presents the exact candidate to a real human/user. Only a real human/user may provide explicit combined UI acceptance for appearance and primary behavior. The Coordinator records explicit human UI/behavior acceptance evidence tied to `checkpoint_token` and `checkpoint_scope`. The Coordinator records an ephemeral `accepted_source_fingerprint` at acceptance time for the exact `checkpoint_scope`. The fingerprint covers source content plus staged/unstaged/untracked inventory. The acceptance-time accepted_source_fingerprint is read-only evidence. AI agents may not proxy or assume this acceptance. Human feedback resumes the same saved implementer/IAB loop; do not start verifier or reviewer yet.
3. Verifier technical verification: only after explicit human UI/behavior acceptance evidence tied to `checkpoint_token` and `checkpoint_scope` and a read-only accepted_source_fingerprint comparison, `verifier_luna` independently verifies the same accepted checkpoint with tests, logs, IAB/objective behavior, and source before/after integrity. Repeat the accepted_source_fingerprint comparison in before/after evidence. A mismatch invalidates the acceptance and returns to the same implementer/IAB loop and human gate. It does not decide subjective appearance or usability acceptance. Tool-generated artifacts outside the exact checkpoint scope do not invalidate the accepted source fingerprint.
4. Completion review: only after verifier passes, freeze, stage, and fingerprint the accepted scope before starting the Luna/max completion review. If verifier finds a problem or later source changes affect user-visible appearance or behavior, return to the same implementer/IAB loop and require combined human acceptance again before verifier. Purely non-user-visible verification artifact changes do not invalidate human acceptance.

### PR evidence

User-visible UI changes require PR video evidence. Screenshots are optional supplements and never
substitutes; backend, configuration, and documentation-only changes are excluded. The reusable
`pr-evidence-video` skill is installed at ~/.codex/skills/pr-evidence-video and renders only local,
privacy-reviewed, muted evidence with a manifest. Never install Remotion globally or in an
application checkout. The current dotfiles/configuration change itself is non-user-visible and
needs no video.

## コマンド

### `setup.sh`

```bash
./setup.sh init
./setup.sh link
./setup.sh unlink
./setup.sh
```

- `init`: ホーム配下の設定を repo にコピー
- `link`: repo からホーム配下へシンボリックリンクを作成
- `unlink`: `link` で作成したシンボリックリンクを外し、最新のバックアップがあれば復元
- 引数なし: `init` → `link`

## Homebrew

macOS で Homebrew パッケージを復元する場合:

```bash
brew bundle --file=~/dotfiles/Brewfile
```

## ロールバック

macOS 側のリンクを戻す場合:

```bash
./setup.sh unlink
```

## 注意点

- `gh` の認証情報は [`hosts.yml`](./.gitignore) で ignore しており、この repo には含めません。
- `bin/` 配下のスクリプトは `pbpaste`, `pbcopy`, `osascript`, `open`, `say` など macOS のコマンドを前提にしています。
