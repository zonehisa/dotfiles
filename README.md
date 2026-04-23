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
