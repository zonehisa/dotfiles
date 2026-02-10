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
| **Git** | `.config/git/ignore` |
| **GitHub CLI** | `.config/gh/config.yml` |

## セットアップ

### 新しいマシンに展開

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
chmod +x setup.sh
./setup.sh
```

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
