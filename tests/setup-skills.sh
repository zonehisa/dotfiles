#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT

declare -a LINKS=(
  ".codex/AGENTS.md:codex/AGENTS.md"
  ".agents/skills/parallel-worktree:codex/skills/parallel-worktree"
  ".codex/skills/git-workflow:codex/skills/git-workflow"
  ".codex/skills/dig:codex/skills/dig"
  ".codex/skills/loop-engineering:codex/skills/loop-engineering"
  ".codex/skills/issue-orchestrator:codex/skills/issue-orchestrator"
)

mkdir -p "$TEST_HOME/.codex/skills"
printf 'legacy global rules\n' > "$TEST_HOME/.codex/AGENTS.md"
mkdir -p "$TEST_HOME/legacy"
ln -s "$TEST_HOME/legacy/dig" "$TEST_HOME/.codex/skills/dig"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null

for entry in "${LINKS[@]}"; do
  target="$TEST_HOME/${entry%%:*}"
  source="$DOTFILES_DIR/${entry##*:}"
  [[ -L "$target" ]]
  [[ "$(readlink "$target")" == "$source" ]]
done

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null

for entry in "${LINKS[@]}"; do
  target="$TEST_HOME/${entry%%:*}"
  if [[ "${entry%%:*}" == ".codex/AGENTS.md" ]]; then
    [[ -f "$target" && ! -L "$target" ]]
    [[ "$(cat "$target")" == "legacy global rules" ]]
  elif [[ "${entry%%:*}" == ".codex/skills/dig" ]]; then
    [[ -L "$target" ]]
    [[ "$(readlink "$target")" == "$TEST_HOME/legacy/dig" ]]
  else
    [[ ! -e "$target" && ! -L "$target" ]]
  fi
done

printf 'Codex Skill link/unlink test passed.\n'
