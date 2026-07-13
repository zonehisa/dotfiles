# 🏠 dotfiles

macOSの開発環境設定ファイルをGit管理するリポジトリです。

## 管理対象

| ツール | ファイル |
|---|---|
| **zsh** | `.zshrc` |
| **Homebrew** | `Brewfile` |
| **sheldon** | `.config/sheldon/plugins.toml` |
| **zeno** | `.config/zeno/config.yml` |
| **Starship** | `.config/starship.toml` 他 |
| **tmux** | `.config/tmux/tmux.conf` |
| **Neovim** | `.config/nvim/` (init.lua + lua/) |
| **Alacritty** | `.config/alacritty/alacritty.toml` |
| **WezTerm** | `.config/wezterm/` (14ファイル) |
| **AeroSpace** | `.config/aerospace/aerospace.toml` |
| **Karabiner-Elements** | `.config/karabiner/karabiner.json` |
| **Git** | `.config/git/ignore` |
| **GitHub CLI** | `.config/gh/config.yml` |
| **lazygit** | `~/Library/Application Support/lazygit/config.yml` → `.config/lazygit/config.yml` |
| **Raycast Script Commands** | `~/raycast-scripts/` → `raycast-scripts/` |
| **Codex policy / Skills** | `policies/`, `codex/` |

## セットアップ

### 新しいマシンに展開

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

Codexのglobal guideと開発Skillは次へリンクされます。

- `codex/AGENTS.md` → `~/.codex/AGENTS.md`
- `codex/skills/parallel-worktree` → `~/.agents/skills/parallel-worktree`
- `codex/skills/git-workflow` → `~/.codex/skills/git-workflow`
- `codex/skills/dig` → `~/.codex/skills/dig`
- `codex/skills/loop-engineering` → `~/.codex/skills/loop-engineering`
- `codex/skills/issue-orchestrator` → `~/.codex/skills/issue-orchestrator`

共通開発policyは`policies/development-workflow.md`を正本とし、次でCodex referenceと対象repositoryのAntigravity policyへ同期します。

```bash
bin/sync-development-workflow-policy --repo /path/to/repository
bin/sync-development-workflow-policy --repo /path/to/repository --check
```

実行時registry、lock、evidenceは`${CODEX_HOME:-$HOME/.codex}/parallel-worktree`、Worktreeはadapterごとの管理領域に保持され、dotfilesでは管理しません。

### コマンド

```bash
./setup.sh init    # ~/.config から dotfiles にコピー
./setup.sh link    # dotfiles → ~/.config にシンボリックリンク作成
./setup.sh unlink  # シンボリックリンク解除＆バックアップ復元
./setup.sh         # init + link を実行
```

### Homebrew パッケージ復元

```bash
brew bundle --file=~/dotfiles/Brewfile
```

## ロールバック

万が一設定がおかしくなった場合：

```bash
./setup.sh unlink
```

これでシンボリックリンクを解除し、バックアップファイル (`.bak.*`) から自動で復元します。

## 補足

Raycast 本体の設定やインストール済み拡張は管理対象にせず、手元で作成・編集する Script Commands 用ディレクトリ `~/raycast-scripts/` だけを管理対象にしています。
