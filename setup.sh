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
  ".config/git/ignore:.config/git/ignore"
  ".config/gh/config.yml:.config/gh/config.yml"
)

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
    cp "$src" "$dst"
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
do_link() {
  info "シンボリックリンクを作成します..."

  for entry in "${LINKS[@]}"; do
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

    # 既存ファイルをバックアップ
    if [[ -e "$link_path" ]] && [[ ! -L "$link_path" ]]; then
      mv "$link_path" "${link_path}${BACKUP_SUFFIX}"
      warn "バックアップ: $link_path → ${link_path}${BACKUP_SUFFIX}"
    elif [[ -L "$link_path" ]]; then
      rm "$link_path"
    fi

    mkdir -p "$(dirname "$link_path")"
    ln -s "$target" "$link_path"
    ok "リンク: $link_path → $target"
  done

  info "link 完了！新しいターミナルを開いて動作確認してください。"
}

# ---- unlink: シンボリックリンクを解除してバックアップを復元 ----
do_unlink() {
  info "シンボリックリンクを解除します..."

  for entry in "${LINKS[@]}"; do
    link_path="$HOME/${entry%%:*}"
    target="$DOTFILES_DIR/${entry##*:}"

    if [[ -L "$link_path" ]] && [[ "$(readlink "$link_path")" == "$target" ]]; then
      rm "$link_path"
      ok "リンク解除: $link_path"

      # 最新のバックアップがあれば復元
      latest_bak=$(ls -1t "${link_path}.bak."* 2>/dev/null | head -1)
      if [[ -n "$latest_bak" ]]; then
        mv "$latest_bak" "$link_path"
        ok "復元: $latest_bak → $link_path"
      fi
    fi
  done

  info "unlink 完了！"
}

# ---- メイン ----
case "${1:-all}" in
  init)   do_init ;;
  link)   do_link ;;
  unlink) do_unlink ;;
  all)
    do_init
    echo ""
    do_link
    ;;
  *)
    echo "使い方: $0 {init|link|unlink|all}"
    echo "  init   - 設定ファイルを dotfiles にコピー"
    echo "  link   - シンボリックリンクを作成"
    echo "  unlink - シンボリックリンクを解除しバックアップを復元"
    echo "  all    - init + link を実行（デフォルト）"
    exit 1
    ;;
esac
