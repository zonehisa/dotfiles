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
  ".codex/skills/git-workflow:codex/skills/git-workflow"
  ".codex/skills/pr-evidence-video:codex/skills/pr-evidence-video"
)

# Codex CLI は agent TOML が symlink の場合に registry へ登録しないため、明示した5ファイル
# だけは byte-identical な通常ファイルとして配置する。他の Codex 管理対象は symlink のまま。
CODEX_AGENT_COPIES=(
  ".codex/agents/implementer-luna.toml:codex/agents/implementer-luna.toml"
  ".codex/agents/explorer-luna.toml:codex/agents/explorer-luna.toml"
  ".codex/agents/verifier-luna.toml:codex/agents/verifier-luna.toml"
  ".codex/agents/git-operator-luna.toml:codex/agents/git-operator-luna.toml"
  ".codex/agents/reviewer-luna.toml:codex/agents/reviewer-luna.toml"
)
AGENT_MARKER_SUFFIX=".dotfiles-managed"
AGENT_MARKER_HEADER="dotfiles-agent-copy-v1"

CODEX_ENTRIES=("${CODEX_LINKS[@]}" "${CODEX_AGENT_COPIES[@]}")
LINKS+=("${CODEX_ENTRIES[@]}")

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

is_codex_agent_copy_entry() {
  local entry="$1"
  local copy_entry

  for copy_entry in "${CODEX_AGENT_COPIES[@]}"; do
    if [[ "$entry" == "$copy_entry" ]]; then
      return 0
    fi
  done

  return 1
}

agent_marker_path() {
  printf '%s%s\n' "$1" "$AGENT_MARKER_SUFFIX"
}

file_sha256() {
  local path="$1"

  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$path" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$path" | awk '{print $1}'
  else
    err "SHA-256 ツールが見つからないため agent TOML の所有 marker を作成できません: $path"
    return 1
  fi
}

read_agent_marker_digest() {
  local marker_path="$1"
  local header
  local digest

  [[ -f "$marker_path" ]] && [[ ! -L "$marker_path" ]] || return 1
  IFS= read -r header < "$marker_path" || return 1
  digest="$(sed -n '2p' "$marker_path")"
  [[ "$header" == "$AGENT_MARKER_HEADER" ]] || return 1
  [[ "$digest" =~ ^[0-9a-fA-F]{64}$ ]] || return 1
  printf '%s\n' "$digest"
}

backup_existing_path() {
  local path="$1"
  local backup_path="${path}${BACKUP_SUFFIX}"
  local suffix=1

  while [[ -e "$backup_path" ]] || [[ -L "$backup_path" ]]; do
    backup_path="${path}${BACKUP_SUFFIX}.${suffix}"
    suffix=$((suffix + 1))
  done

  mv "$path" "$backup_path"
  warn "バックアップ: $path → $backup_path"
}

backup_order_key() {
  local backup_path="$1"
  local managed_path="$2"
  local prefix_length=$(( ${#managed_path} + 5 ))
  local backup_name="${backup_path:$prefix_length}"
  local timestamp="${backup_name%%.*}"
  local suffix=0

  if [[ "$backup_name" == *.* ]]; then
    suffix="${backup_name##*.}"
    if [[ ! "$suffix" =~ ^[0-9]+$ ]]; then
      suffix=0
    fi
  fi

  # The optional collision suffix is numeric, so .10 is newer than .9.
  printf '%s %010d\n' "$timestamp" "$suffix"
}

restore_latest_backup() {
  local path="$1"
  local latest_bak=""
  local latest_key=""
  local candidate
  local candidate_key

  # 最新のバックアップがあれば復元する。候補なしでも set -e で終了しない。
  if compgen -G "${path}.bak.*" >/dev/null; then
    for candidate in "${path}.bak."*; do
      candidate_key="$(backup_order_key "$candidate" "$path")"
      if [[ -z "$latest_bak" || "$candidate_key" > "$latest_key" ]]; then
        latest_bak="$candidate"
        latest_key="$candidate_key"
      fi
    done
  fi

  if [[ -n "$latest_bak" ]]; then
    mv "$latest_bak" "$path"
    ok "復元: $latest_bak → $path"
  fi
}

write_agent_marker() {
  local target="$1"
  local marker_path="$2"
  local digest

  digest="$(file_sha256 "$target")"
  if [[ -e "$marker_path" ]] || [[ -L "$marker_path" ]]; then
    if [[ -L "$marker_path" ]] || ! read_agent_marker_digest "$marker_path" >/dev/null; then
      backup_existing_path "$marker_path"
    fi
  fi

  printf '%s\n%s\n' "$AGENT_MARKER_HEADER" "$digest" > "$marker_path"
}

install_agent_copy() {
  local target="$1"
  local copy_path="$2"
  local marker_path
  local marker_digest
  local copy_digest
  local target_digest

  if [[ ! -f "$target" ]] || [[ -L "$target" ]]; then
    warn "スキップ（agent TOML が通常ファイルではありません）: $target"
    return
  fi

  marker_path="$(agent_marker_path "$copy_path")"
  target_digest="$(file_sha256 "$target")"

  if [[ -f "$copy_path" ]] && [[ ! -L "$copy_path" ]]; then
    if marker_digest="$(read_agent_marker_digest "$marker_path")"; then
      # 既に管理対象の内容なら、再実行時に不要なバックアップを作らない。
      if cmp -s "$target" "$copy_path"; then
        if [[ "$marker_digest" != "$target_digest" ]]; then
          write_agent_marker "$target" "$marker_path"
        fi
        ok "コピー済み: $copy_path"
        return
      fi

      # source だけが更新された場合は、前回管理内容と一致する copy を直接更新する。
      copy_digest="$(file_sha256 "$copy_path")"
      if [[ "$copy_digest" == "$marker_digest" ]]; then
        cp "$target" "$copy_path"
        write_agent_marker "$target" "$marker_path"
        ok "更新: $target → $copy_path"
        return
      fi
    fi
  fi

  if [[ -L "$copy_path" ]] && [[ "$(readlink "$copy_path")" == "$target" ]]; then
    # 以前の link-codex が作った旧 symlink は退避せず、通常ファイルへ移行する。
    rm "$copy_path"
    warn "旧 agent リンクを通常ファイルへ移行: $copy_path"
  elif [[ -e "$copy_path" ]] || [[ -L "$copy_path" ]]; then
    backup_existing_path "$copy_path"
  fi

  mkdir -p "$(dirname "$copy_path")"
  cp "$target" "$copy_path"
  write_agent_marker "$target" "$marker_path"
  ok "コピー: $target → $copy_path"
}

unlink_agent_copy() {
  local target="$1"
  local copy_path="$2"
  local marker_path
  local marker_digest
  local copy_digest

  marker_path="$(agent_marker_path "$copy_path")"

  if [[ -L "$copy_path" ]] && [[ "$(readlink "$copy_path")" == "$target" ]]; then
    # 移行前の旧 symlink も管理対象として解除するが、obsolete symlink は復元しない。
    rm "$copy_path"
    ok "旧 agent リンク解除: $copy_path"
    if marker_digest="$(read_agent_marker_digest "$marker_path")"; then
      rm "$marker_path"
      restore_latest_backup "$marker_path"
    fi
    restore_latest_backup "$copy_path"
  elif marker_digest="$(read_agent_marker_digest "$marker_path")"; then
    if [[ -f "$copy_path" ]] && [[ ! -L "$copy_path" ]]; then
      copy_digest="$(file_sha256 "$copy_path")"
      if [[ "$copy_digest" == "$marker_digest" ]]; then
        rm "$copy_path"
        rm "$marker_path"
        ok "agent コピー解除: $copy_path"
        restore_latest_backup "$copy_path"
        restore_latest_backup "$marker_path"
      else
        warn "保持（変更された agent コピー）: $copy_path"
        rm "$marker_path"
        restore_latest_backup "$marker_path"
      fi
    elif [[ ! -e "$copy_path" ]] && [[ ! -L "$copy_path" ]]; then
      # 復元に失敗しても marker を残して再試行できるよう、copy backup を先に戻す。
      restore_latest_backup "$copy_path"
      rm "$marker_path"
      restore_latest_backup "$marker_path"
    elif [[ -e "$copy_path" ]] || [[ -L "$copy_path" ]]; then
      warn "保持（変更された agent コピー）: $copy_path"
      rm "$marker_path"
      restore_latest_backup "$marker_path"
    fi
  elif [[ -e "$copy_path" ]] || [[ -L "$copy_path" ]]; then
    warn "保持（agent コピーの所有 marker がありません）: $copy_path"
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
  local target
  local link_path
  local -a entries

  if [[ "$scope" == "codex" ]]; then
    entries=("${CODEX_ENTRIES[@]}")
    warn_if_wsl_windows_mount
    info "Codex/agent/skill を配置します（agent TOML は通常ファイル）..."
  else
    entries=("${LINKS[@]}")
    info "シンボリックリンクと agent TOML を配置します..."
  fi

  for entry in "${entries[@]}"; do
    target="$DOTFILES_DIR/${entry##*:}"
    link_path="$HOME/${entry%%:*}"

    if is_codex_agent_copy_entry "$entry"; then
      install_agent_copy "$target" "$link_path"
      continue
    fi

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
      backup_existing_path "$link_path"
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
  local target
  local link_path
  local -a entries

  if [[ "$scope" == "codex" ]]; then
    entries=("${CODEX_ENTRIES[@]}")
    info "Codex/agent/skill を解除します..."
  else
    entries=("${LINKS[@]}")
    info "シンボリックリンクと agent TOML を解除します..."
  fi

  for entry in "${entries[@]}"; do
    link_path="$HOME/${entry%%:*}"
    target="$DOTFILES_DIR/${entry##*:}"

    if is_codex_agent_copy_entry "$entry"; then
      unlink_agent_copy "$target" "$link_path"
      continue
    fi

    if [[ -L "$link_path" ]] && [[ "$(readlink "$link_path")" == "$target" ]]; then
      rm "$link_path"
      ok "リンク解除: $link_path"
      restore_latest_backup "$link_path"
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
