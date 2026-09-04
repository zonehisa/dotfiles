# dotfiles

macOS を主対象にしつつ、Codex/agent/skill と PR evidence workflow は WSL2 でも利用できる
開発環境設定のリポジトリです。

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

Codex の Skills と設定ファイルは次のパスへシンボリックリンクされます。Codex CLI の互換性のため、5つの custom agent TOML だけはシンボリックリンクではなく、repo と byte-identical な通常ファイルとしてホームへコピーされます。コピーの所有判定用に隣接する `.dotfiles-managed` marker を作成し、`unlink` 時に削除します。この suffix は setup 専用の予約済み metadata として扱ってください。agent TOML や Skills の更新を pull した後は `./setup.sh link-codex` を再実行してください（通常の `link`/引数なしの `all` でも同じ配置になります）。

- `codex/skills/parallel-worktree` → `~/.agents/skills/parallel-worktree`
- `codex/skills/git-workflow` → `~/.codex/skills/git-workflow`
- `codex/skills/pr-evidence-video` → `~/.codex/skills/pr-evidence-video`

通常ファイルとしてコピーされる custom agent TOML:

- `codex/agents/implementer-luna.toml` → `~/.codex/agents/implementer-luna.toml`
- `codex/agents/explorer-luna.toml` → `~/.codex/agents/explorer-luna.toml`
- `codex/agents/verifier-luna.toml` → `~/.codex/agents/verifier-luna.toml`
- `codex/agents/git-operator-luna.toml` → `~/.codex/agents/git-operator-luna.toml`
- `codex/agents/reviewer-luna.toml` → `~/.codex/agents/reviewer-luna.toml`

実行時registry、lock、evidenceは`${CODEX_HOME:-$HOME/.codex}/parallel-worktree`、Worktreeはadapterごとの管理領域に保持され、dotfilesでは管理しません。

### Codex workflow

R0（文言、コメント、明白な整形）は clean checkout で Coordinator/main が直接行います。R1〜R4 の新規 Issue は
開始時に一度 `git fetch origin` を行い、最新の `origin/<default-branch>`（通常は `origin/main`）から専用
Worktreeを作成して、primary checkoutをread-onlyで保全します。Worktree isolationは独立したCodex taskや
`implementer_luna`の必須化を意味せず、CoordinatorがWorktree内で直接実装できます。`git_operator_luna`は
read-onlyの必須役ではなく、Issue/PR作成、push、コメントなどGit/GitHub外部writeのexact targetと認可-bound
操作だけに使います。実装前にWorktreeのrealpathとbranchを確認し、不一致なら停止します。

R1〜R4 の変更は fresh-context Luna/max reviewer の completion gate を通します。user-visible UI は実装中に IAB を
繰り返さず、技術検証と review 後の最終候補で Coordinator/main が built-in IAB (`agent.browsers.get("iab")`) を
一度だけ選び、同じ候補で human appearance＋primary behavior acceptance を行います。video/evidence は明示 opt-in の時だけです。

詳細な risk、Worktree、UI packet、changed-path blob/mode fingerprint、認可、review、動画手順は
[`policies/development-workflow.md`](./policies/development-workflow.md) と
[`codex/skills/git-workflow/SKILL.md`](./codex/skills/git-workflow/SKILL.md) から必要な reference を読みます。

## コマンド

### `setup.sh`

```bash
./setup.sh init
./setup.sh link
./setup.sh unlink
./setup.sh link-codex
./setup.sh unlink-codex
./setup.sh
```

- `init`: ホーム配下の設定を repo にコピー
- `link`: repo からホーム配下へシンボリックリンクを作成し、custom agent TOML は通常ファイルとしてコピー
- `unlink`: `link` のリンク/agent コピーを解除し、最新のバックアップがあれば復元
- `link-codex`: Codex/agent/skill のみをホームへ配置（Skills/設定はリンク、agent TOML はコピー。WSL2 向け）
- `unlink-codex`: `link-codex` のリンク/agent コピーを解除し、最新のバックアップがあれば復元
- 引数なし: `init` → `link`

### WSL2

Codex 0.115 以降の Linux 実行環境として WSL2 をサポートします。WSL1 は Linux の
`bubblewrap` 境界を利用できないため対象外です。Windows 側の `/mnt/c` 配下ではなく、WSL2
の Linux ホーム（例: `~/code/dotfiles`）へ clone してください。`/mnt/c` は DrvFS の権限・
symlink・mount の挙動が異なるため、`link-codex` は警告を出し、PR evidence renderer は安全な
FD/mount 境界を確立できない場合に evidence materialization 前に fail closed します。

PR evidence の Remotion 実行には次の Linux 側依存が必要です。

- `bubblewrap >= 0.10.0` (`bwrap`, with `--bind-fd`)
- `node` / `npm` / `npx`
- `ffmpeg` / `ffprobe`
- WSLg 等から起動できる、既にインストール済みの Linux Chrome または Chromium

セキュリティ境界に使う `bwrap`、`npm`、`npx` は caller の `PATH` ではなく、root-owned
system path の `/usr/bin/bwrap`、`/usr/bin/npm`、`/usr/bin/npx` を使用します。これらを
その場所に用意してください。

WSL2 では macOS の shell、Homebrew、デスクトップアプリ設定をリンクせず、Codex/agent/skill
だけを次で有効化します。

```bash
cd ~/code/dotfiles
./setup.sh link-codex
```

戻す場合は `./setup.sh unlink-codex` を実行します。`init`、`link`、`unlink`、引数なしの
`init → link` でも、custom agent TOML は同じ通常ファイルのコピー契約に従います。

WSL2 環境の依存確認と契約テスト（実際の WSL2 runtime や browser render を成功済みとは
主張しません）のコマンド:

```bash
set -e
for tool in /usr/bin/bwrap /usr/bin/npm /usr/bin/npx; do test -x "$tool"; done
for tool in node ffmpeg ffprobe; do command -v "$tool" >/dev/null; done
/usr/bin/bwrap --help | grep -F -- --bind-fd >/dev/null
command -v google-chrome || command -v chromium || command -v chromium-browser
python3 -m unittest codex/skills/pr-evidence-video/tests/test_render_pr_evidence.py -v
```

Remotion の実行時は `bwrap --ro-bind / / --share-net` を使い、disposable run だけを writable
mount として FD-bound に渡します。`HOME`、`TMPDIR`、npm cache は run 内に固定されます。
`bwrap`、local browser、または安全な mount/descriptor 境界がない場合は、入力録画を run に
materialize せず停止します。

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
