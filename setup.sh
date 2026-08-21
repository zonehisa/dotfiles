#!/bin/bash
set -euo pipefail

# ============================================
# dotfiles セットアップスクリプト
# ============================================
# 使い方:
#   1. 初回: ./setup.sh init   (設定ファイルを dotfiles にコピー)
#   2. リンク: ./setup.sh link  (シンボリックリンクを作成)
#   3. 両方: ./setup.sh         (init → link を順に実行)

DOTFILES_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SUFFIX=".bak.$(date +%Y%m%d_%H%M%S)"

# ---- 管理対象の定義 ----
# "ソース(~からの相対パス):dotfiles内の相対パス"
LINKS=(
  ".zshrc:.zshrc"
  ".config/sheldon/plugins.toml:.config/sheldon/plugins.toml"
  ".config/zeno/config.yml:.config/zeno/config.yml"
  ".config/starship.toml:.config/starship.toml"
  ".config/starship_alt.toml:.config/starship_alt.toml"
  ".config/starship_backup.toml:.config/starship_backup.toml"
  ".config/tmux/tmux.conf:.config/tmux/tmux.conf"
  ".config/alacritty/alacritty.toml:.config/alacritty/alacritty.toml"
  ".config/aerospace/aerospace.toml:.config/aerospace/aerospace.toml"
  ".config/karabiner/karabiner.json:.config/karabiner/karabiner.json"
  ".config/git/ignore:.config/git/ignore"
  ".config/gh/config.yml:.config/gh/config.yml"
  "Library/Application Support/lazygit/config.yml:.config/lazygit/config.yml"
  "raycast-scripts:raycast-scripts"
)

# Codex/agent/skill paths are kept separate so WSL2 can opt into only these links without
# touching macOS shell, Homebrew, desktop-app, or other host-specific configuration.
CODEX_LINKS=(
  ".agents/skills/parallel-worktree:codex/skills/parallel-worktree"
  ".codex/AGENTS.md:codex/AGENTS.md"
  ".codex/agents/implementer-luna.toml:codex/agents/implementer-luna.toml"
  ".codex/agents/explorer-luna.toml:codex/agents/explorer-luna.toml"
  ".codex/agents/verifier-luna.toml:codex/agents/verifier-luna.toml"
  ".codex/agents/git-operator-luna.toml:codex/agents/git-operator-luna.toml"
  ".codex/agents/reviewer-luna.toml:codex/agents/reviewer-luna.toml"
  ".codex/skills/git-workflow:codex/skills/git-workflow"
  ".codex/skills/pr-evidence-video:codex/skills/pr-evidence-video"
)

LINKS+=("${CODEX_LINKS[@]}")

# nvim (ディレクトリごとコピー/リンク)
NVIM_FILES=(
  "init.lua"
  "lazy-lock.json"
  "lua/base.lua"
  "lua/keymaps.lua"
  "lua/config/lazy.lua"
  "lua/plugins/autopairs.lua"
  "lua/plugins/cmp.lua"
  "lua/plugins/conform.lua"
  "lua/plugins/emmet.lua"
  "lua/plugins/fzf.lua"
  "lua/plugins/lsp.lua"
  "lua/plugins/lualine.lua"
  "lua/plugins/markdown.lua"
  "lua/plugins/statusline.lua"
  "lua/plugins/theme.lua"
  "lua/plugins/toggleterm.lua"
  "lua/plugins/tree.lua"
  "lua/plugins/treesitter.lua"
)

for f in "${NVIM_FILES[@]}"; do
  LINKS+=(".config/nvim/$f:.config/nvim/$f")
done

# wezterm
WEZTERM_FILES=(
  "wezterm.lua"
  "appearance.lua"
  "keymaps.lua"
  "statusbar.lua"
  "tab.lua"
  "workspace.lua"
  "modules/aws_profile.lua"
  "modules/color.lua"
  "modules/edit_prompt.lua"
  "modules/functions.lua"
  "modules/hyperlinks.lua"
  "modules/opacity.lua"
  "modules/quick_select.lua"
  "modules/toggle_term.lua"
)

for f in "${WEZTERM_FILES[@]}"; do
  LINKS+=(".config/wezterm/$f:.config/wezterm/$f")
done

# ---- ヘルパー関数 ----
info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m   $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
err()   { echo -e "\033[1;31m[ERR]\033[0m  $*"; }

warn_if_wsl_windows_mount() {
  if [[ "$DOTFILES_DIR" == /mnt/* ]] && [[ -r /proc/version ]] && grep -qi microsoft /proc/version; then
    warn "WSL2では repo を /mnt/c 配下に置かないでください（推奨: ~/code）。DrvFS の symlink/mount 差異により PR evidence は安全境界を作れず fail closed する場合があります。"
  fi
}

# ---- init: 設定ファイルを dotfiles にコピー ----
do_init() {
  info "設定ファイルを $DOTFILES_DIR にコピーします..."

  for entry in "${LINKS[@]}"; do
    src="$HOME/${entry%%:*}"
    dst="$DOTFILES_DIR/${entry##*:}"

    if [[ ! -e "$src" ]]; then
      warn "スキップ（ファイルなし）: $src"
      continue
    fi

    if [[ -e "$dst" ]]; then
      # 既にdotfilesにある場合はスキップ
      warn "スキップ（既に存在）: $dst"
      continue
    fi

    mkdir -p "$(dirname "$dst")"

    if [[ -d "$src" ]]; then
      cp -R "$src" "$dst"
    else
      cp "$src" "$dst"
    fi

    ok "コピー: $src → $dst"
  done

  # Brewfile は既に dotfiles にあるはず
  if [[ ! -f "$DOTFILES_DIR/Brewfile" ]] && command -v brew &>/dev/null; then
    info "Brewfile を生成中..."
    brew bundle dump --file="$DOTFILES_DIR/Brewfile" --force
    ok "Brewfile 生成完了"
  fi

  info "init 完了！ 'git add -A && git commit' でコミットしてください。"
}

# ---- link: シンボリックリンクを作成 ----
do_link_scope() {
  local scope="$1"
  local entry
  local -a entries

  if [[ "$scope" == "codex" ]]; then
    entries=("${CODEX_LINKS[@]}")
    warn_if_wsl_windows_mount
    info "Codex/agent/skill のシンボリックリンクを作成します..."
  else
    entries=("${LINKS[@]}")
    info "シンボリックリンクを作成します..."
  fi

  for entry in "${entries[@]}"; do
    target="$DOTFILES_DIR/${entry##*:}"
    link_path="$HOME/${entry%%:*}"

    if [[ ! -e "$target" ]]; then
      warn "スキップ（dotfilesにない）: $target"
      continue
    fi

    # 既にシンボリックリンクで正しいターゲットを指している場合はスキップ
    if [[ -L "$link_path" ]] && [[ "$(readlink "$link_path")" == "$target" ]]; then
      ok "リンク済み: $link_path"
      continue
    fi

    # 既存ファイル・リンクをバックアップ
    if [[ -e "$link_path" ]] || [[ -L "$link_path" ]]; then
      mv "$link_path" "${link_path}${BACKUP_SUFFIX}"
      warn "バックアップ: $link_path → ${link_path}${BACKUP_SUFFIX}"
    fi

    mkdir -p "$(dirname "$link_path")"
    ln -s "$target" "$link_path"
    ok "リンク: $link_path → $target"
  done

  if [[ "$scope" == "codex" ]]; then
    info "link-codex 完了！Codex/agent/skill のみをリンクしました。"
  else
    info "link 完了！新しいターミナルを開いて動作確認してください。"
  fi
}

do_link() { do_link_scope all; }
do_link_codex() { do_link_scope codex; }

# ---- unlink: シンボリックリンクを解除してバックアップを復元 ----
do_unlink_scope() {
  local scope="$1"
  local entry
  local -a entries

  if [[ "$scope" == "codex" ]]; then
    entries=("${CODEX_LINKS[@]}")
    info "Codex/agent/skill のシンボリックリンクを解除します..."
  else
    entries=("${LINKS[@]}")
    info "シンボリックリンクを解除します..."
  fi

  local latest_bak candidate

  for entry in "${entries[@]}"; do
    link_path="$HOME/${entry%%:*}"
    target="$DOTFILES_DIR/${entry##*:}"

    if [[ -L "$link_path" ]] && [[ "$(readlink "$link_path")" == "$target" ]]; then
      rm "$link_path"
      ok "リンク解除: $link_path"

      # 最新のバックアップがあれば復元する。候補なしでも set -e で終了しない。
      latest_bak=""
      if compgen -G "${link_path}.bak.*" >/dev/null; then
        for candidate in "${link_path}.bak."*; do
          if [[ -z "$latest_bak" || "$candidate" > "$latest_bak" ]]; then
            latest_bak="$candidate"
          fi
        done
      fi

      if [[ -n "$latest_bak" ]]; then
        mv "$latest_bak" "$link_path"
        ok "復元: $latest_bak → $link_path"
      fi
    fi
  done

  if [[ "$scope" == "codex" ]]; then
    info "unlink-codex 完了！"
  else
    info "unlink 完了！"
  fi
}

do_unlink() { do_unlink_scope all; }
do_unlink_codex() { do_unlink_scope codex; }

# ---- メイン ----
case "${1:-all}" in
  init)   do_init ;;
  link)   do_link ;;
  unlink) do_unlink ;;
  link-codex) do_link_codex ;;
  unlink-codex) do_unlink_codex ;;
  all)
    do_init
    echo ""
    do_link
    ;;
  *)
    echo "使い方: $0 {init|link|unlink|link-codex|unlink-codex|all}"
    echo "  init   - 設定ファイルを dotfiles にコピー"
    echo "  link   - シンボリックリンクを作成"
    echo "  unlink - シンボリックリンクを解除しバックアップを復元"
    echo "  link-codex - Codex/agent/skill のみをホームへリンク"
    echo "  unlink-codex - link-codex のリンクを解除しバックアップを復元"
    echo "  all    - init + link を実行（デフォルト）"
    exit 1
    ;;
esac
