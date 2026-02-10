# ============================================
# 環境変数・言語設定
# ============================================
export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8
export LESSCHARSET=utf-8

# ============================================
# PATH設定
# ============================================
# Homebrew（最優先）
if [[ "$OSTYPE" == "darwin"* ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init --path)"
  eval "$(pyenv init -)"
fi

# ユーザー固有のパス
export PATH="$HOME/bin:$PATH"
export PATH="/usr/local/bin:$PATH"
export SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
export EDITOR=nvim
export ZENO_HOME=~/.config/zeno

# git file preview with color
export ZENO_GIT_CAT="bat --color=always"

# git folder preview with color
# export ZENO_GIT_TREE="eza --tree"

if [[ -n $ZENO_LOADED ]]; then

  # if you use zsh's incremental search
  # bindkey -M isearch ' ' self-insert


  bindkey '^i' zeno-completion

  bindkey '^xx' zeno-insert-snippet           # open snippet picker (fzf) and insert at cursor

  bindkey '^x '  zeno-insert-space
  bindkey '^x^m' accept-line
  bindkey '^x^z' zeno-toggle-auto-snippet

  # preprompt bindings
  bindkey '^xp' zeno-preprompt
  bindkey '^xs' zeno-preprompt-snippet
  # Outside ZLE you can run `zeno-preprompt git {{cmd}}` or `zeno-preprompt-snippet foo`
  # to set the next prompt prefix; invoking them with an empty argument resets the state.

  bindkey ' ' zeno-auto-snippet              # space triggers snippet expansion
  bindkey '^r' zeno-smart-history-selection # smart history widget

  # fallback if completion not matched
  # (default: fzf-completion if exists; otherwise expand-or-complete)
  # export ZENO_COMPLETION_FALLBACK=expand-or-complete
fi

# PATH重複を削除
typeset -U path

# ============================================
# 履歴設定
# ============================================
HISTFILE=~/.zsh_history
HISTSIZE=100000
SAVEHIST=100000

# ============================================
# zsh オプション
# ============================================
# ディレクトリ移動
setopt AUTO_CD              # ディレクトリ名だけで移動
setopt AUTO_PUSHD           # cd時に自動でディレクトリスタックに追加
setopt PUSHD_IGNORE_DUPS    # 重複したディレクトリは追加しない
setopt PUSHD_SILENT         # pushdとpopdの度にディレクトリスタックを表示しない

# 履歴
setopt HIST_IGNORE_DUPS     # 重複する履歴を保存しない
setopt HIST_IGNORE_SPACE    # スペースで始まるコマンドは履歴に残さない
setopt HIST_IGNORE_ALL_DUPS # 古い重複を削除
setopt HIST_FIND_NO_DUPS    # 履歴検索で重複を表示しない
setopt HIST_SAVE_NO_DUPS    # 保存時に重複を削除
setopt SHARE_HISTORY        # 複数のターミナル間で履歴を共有
setopt HIST_REDUCE_BLANKS   # 余分な空白を削除
setopt EXTENDED_HISTORY     # 実行時刻とコマンド実行時間を記録

# 補完
setopt AUTO_MENU            # Tab連打で補完候補を順に表示
setopt AUTO_PARAM_SLASH     # ディレクトリ名の補完で末尾に/を自動追加
setopt COMPLETE_IN_WORD     # カーソル位置でも補完
setopt ALWAYS_TO_END        # 補完後カーソルを末尾へ

# その他
setopt CORRECT              # コマンドのスペル修正
setopt NO_BEEP              # ビープ音を消す
setopt INTERACTIVE_COMMENTS # コマンドラインでも#以降をコメント扱い

# ↑↓キーで prefix（先頭一致）履歴検索する
bindkey '^[[A' history-beginning-search-backward
bindkey '^[[B' history-beginning-search-forward

# プロンプト
unsetopt PROMPT_SP
export PROMPT_EOL_MARK=""

# ============================================
# エイリアス - 基本
# ============================================
# エディタ
alias vim='nvim'
alias vi='nvim'

# ユーティリティ
alias cc='claude'
alias now='date "+%Y-%m-%d %H:%M:%S"'

# ディレクトリ移動
alias ..='cd ..'
alias ...='../..'
alias ....='../../..'
alias .....='../../../..'

# ls系
if [[ "$OSTYPE" == "darwin"* ]]; then
    alias ls='ls -G'
else
    alias ls='ls --color=auto'
fi
alias l='ls -lah'
alias la='ls -lAh'
alias ll='ls -lh'
alias lsa='ls -lah'

# grep
alias grep='grep --color=auto'
alias egrep='grep -E --color=auto'
alias fgrep='grep -F --color=auto'

# 安全対策
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# その他
alias md='mkdir -p'

# ============================================
# エイリアス - Git
# ============================================
# 基本
alias g='git'
alias gst='git status'
alias gss='git status --short'
alias gsb='git status --short --branch'

# Add
alias ga='git add'
alias gaa='git add --all'
alias gau='git add --update'
alias gapa='git add --patch'

# Commit
alias gc='git commit --verbose'
alias gc!='git commit --verbose --amend'
alias gcmsg='git commit --message'
alias gcam='git commit --all --message'
alias gca='git commit --verbose --all'
alias gca!='git commit --verbose --all --amend'
alias gcan!='git commit --verbose --all --no-edit --amend'
alias gcn='git commit --verbose --no-edit'

# Checkout/Switch
alias gco='git checkout'
alias gcb='git checkout -b'
alias gcm='git checkout main'
alias gsw='git switch'
alias gswc='git switch --create'
alias gswm='git switch main'

# Branch
alias gb='git branch'
alias gba='git branch --all'
alias gbd='git branch --delete'
alias gbD='git branch --delete --force'
alias gbm='git branch --move'

# Diff
alias gd='git diff'
alias gdca='git diff --cached'
alias gds='git diff --staged'
alias gdw='git diff --word-diff'

# Log
alias glog='git log --oneline --decorate --graph'
alias gloga='git log --oneline --decorate --graph --all'
alias glo='git log --oneline --decorate'
alias glol='git log --graph --pretty="%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset"'
alias glola='git log --graph --pretty="%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset" --all'
alias glg='git log --stat'
alias glgg='git log --graph'

# Fetch/Pull/Push
alias gf='git fetch'
alias gfa='git fetch --all --tags --prune'
alias gl='git pull'
alias gp='git push'
alias gpr='git pull --rebase'
alias gpra='git pull --rebase --autostash'
alias gpsup='git push --set-upstream origin $(git branch --show-current)'
alias gpf='git push --force-with-lease'
alias gpf!='git push --force'

# Stash
alias gsta='git stash push'
alias gstaa='git stash apply'
alias gstp='git stash pop'
alias gstl='git stash list'
alias gstd='git stash drop'
alias gstc='git stash clear'

# Merge/Rebase
alias gm='git merge'
alias gma='git merge --abort'
alias grb='git rebase'
alias grbi='git rebase --interactive'
alias grba='git rebase --abort'
alias grbc='git rebase --continue'

# Remote
alias gr='git remote'
alias grv='git remote --verbose'
alias gra='git remote add'

# Reset/Restore
alias grh='git reset'
alias grhh='git reset --hard'
alias grhs='git reset --soft'
alias grs='git restore'
alias grst='git restore --staged'

# その他便利コマンド
alias gwip='git add -A; git rm $(git ls-files --deleted) 2> /dev/null; git commit --no-verify --no-gpg-sign --message "--wip-- [skip ci]"'
alias grt='cd "$(git rev-parse --show-toplevel || echo .)"'
alias gclean='git clean --interactive -d'

# ============================================
# エイリアス - tmux
# ============================================
alias tm='tmux'
alias ta='tmux attach'
alias tls='tmux list-sessions'
alias tmv='tmux split-window -v'
alias tms='tmux split-window -h'
alias tkill='tmux kill-session'

# ============================================
# エイリアス - Docker
# ============================================
alias d='docker'
alias dc='docker compose'
alias dps='docker ps'
alias dpsa='docker ps -a'
alias dimg='docker images'
alias dlog='docker logs'
alias dlogf='docker logs -f'
alias dex='docker exec -it'
alias dstop='docker stop'
alias drm='docker rm'
alias drmi='docker rmi'

# ============================================
# エイリアス - Laravel/PHP
# ============================================
alias sail='./vendor/bin/sail'
alias sa='sail artisan'
alias sac='sail artisan cache:clear'
alias sam='sail artisan migrate'
alias samf='sail artisan migrate:fresh'
alias sams='sail artisan migrate:fresh --seed'
alias sat='sail artisan test'
alias laravel-setup='curl -L https://gist.github.com/zonehisa/ca286a062e71ed4e1446e2b996c4b2e6/raw -o setup_laravel_sail.sh && chmod +x setup_laravel_sail.sh && ./setup_laravel_sail.sh'

# ============================================
# 関数 - Laravel
# ============================================
# Laravel新規プロジェクト作成
function laravel-new() {
    if [ -z "$1" ]; then
        echo "Usage: laravel-new <project-name>"
        return 1
    fi
    
    docker run -it --rm --user "$(id -u):$(id -g)" \
        -v "$(pwd):/app" -w /app \
        -e COMPOSER_HOME=/tmp/composer \
        laravelsail/php84-composer:latest \
        bash -c "composer global require laravel/installer && /tmp/composer/vendor/bin/laravel new $1"
    
    cd "$1" || return
    
    docker run --rm -it -u=1000:1000 \
        -v "$(pwd)":/var/www -w /var/www \
        laravelsail/php84-composer \
        php artisan sail:install --with mariadb
}

# Composer（PHPバージョン自動検出）
function composer() {
    local php_ver=80
    
    if [ -f composer.lock ]; then
        local vers=( ${(f)"$(
            grep -E '"php".*8\.[0-9]' composer.lock \
            | grep -Eo '8\.[0-9]+' \
            | cut -d. -f1,2 \
            | sed 's/\.//g' \
            | sort -u
        )"} )
        
        for i in ${vers[@]}; do
            if [[ $i -gt $php_ver ]]; then
                php_ver=$i
            fi
        done
    else
        php_ver=84
    fi

    # Sailのcomposerイメージは php82/php83/php84まで
    if [[ $php_ver -ge 85 ]]; then
        php_ver=84
    fi

    docker run --rm -it \
        -u "$(id -u):$(id -g)" \
        -v "$PWD":/app -w /app \
        "laravelsail/php${php_ver}-composer:latest" \
        composer "$@"
}

# ============================================
# 関数 - ユーティリティ
# ============================================
# ディレクトリを作成して移動
function mkcd() {
    mkdir -p "$1" && cd "$1"
}

# ファイルを探して開く
function ff() {
    find . -type f -iname "*$1*"
}

# プロセスを探す
function psgrep() {
    ps aux | grep -v grep | grep -i -e VSZ -e "$1"
}

# ============================================
# ツール初期化
# ============================================
# fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# zoxide（cdの代替）
if command -v zoxide &> /dev/null; then
    eval "$(zoxide init zsh)"
    alias cd='z'
fi

# kiro
[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"

# sheldon（プラグイン管理）
if command -v sheldon &> /dev/null; then
    eval "$(sheldon source)"
fi

# Starship（プロンプト）
if command -v starship &> /dev/null; then
    eval "$(starship init zsh)"
fi

# ============================================
# ローカル設定（gitで管理しない）
# ============================================
[ -f ~/.zshrc.local ] && source ~/.zshrc.local

# Added by Antigravity
export PATH="/Users/iroiropro/.antigravity/antigravity/bin:$PATH"

# Added by Antigravity
export PATH="/Users/iroiropro/.antigravity/antigravity/bin:$PATH"

# Auto Sandbox Hook
if [[ -f "$HOME/.zsh-sandbox.zsh" ]]; then
  source "$HOME/.zsh-sandbox.zsh"
fi

# ghq
function ghq-fzf() {
  local src=$(ghq list | fzf --preview "bat --color=always --style=header,grid --line-range :80 $(ghq root)/{}/README.*")
  if [ -n "$src" ]; then
    BUFFER="cd $(ghq root)/$src"
    zle accept-line
  fi
  zle -R -c
}
zle -N ghq-fzf
bindkey '^g' ghq-fzf
export NVM_DIR="$HOME/.nvm"
[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"
[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"

# Sandbox内でnpm scriptsを無効化
export npm_config_ignore_scripts=true
export PATH="$HOME/.deno/bin:$PATH"
bindkey '^]' zeno-auto-snippet
