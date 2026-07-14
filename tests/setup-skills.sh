#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

TEST_HOME="$TEST_ROOT/regular"

mkdir -p "$TEST_HOME/.codex"
printf 'existing global instructions\n' > "$TEST_HOME/.codex/AGENTS.md"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null

parallel_link="$TEST_HOME/.agents/skills/parallel-worktree"
agents_link="$TEST_HOME/.codex/AGENTS.md"
workflow_link="$TEST_HOME/.codex/skills/git-workflow"

[[ -L "$parallel_link" ]]
[[ "$(readlink "$parallel_link")" == "$DOTFILES_DIR/codex/skills/parallel-worktree" ]]
[[ -L "$agents_link" ]]
[[ "$(readlink "$agents_link")" == "$DOTFILES_DIR/codex/AGENTS.md" ]]
[[ -L "$workflow_link" ]]
[[ "$(readlink "$workflow_link")" == "$DOTFILES_DIR/codex/skills/git-workflow" ]]

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null

[[ ! -e "$parallel_link" && ! -L "$parallel_link" ]]
[[ -f "$agents_link" && ! -L "$agents_link" ]]
[[ "$(cat "$agents_link")" == "existing global instructions" ]]
[[ ! -e "$workflow_link" && ! -L "$workflow_link" ]]

for kind in valid dangling; do
  TEST_HOME="$TEST_ROOT/$kind"
  mkdir -p "$TEST_HOME/.codex" "$TEST_HOME/original"
  original_target="$TEST_HOME/original/AGENTS.md"
  if [[ "$kind" == "valid" ]]; then
    printf 'linked global instructions\n' > "$original_target"
  fi
  ln -s "$original_target" "$TEST_HOME/.codex/AGENTS.md"

  HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null
  [[ "$(readlink "$TEST_HOME/.codex/AGENTS.md")" == "$DOTFILES_DIR/codex/AGENTS.md" ]]

  HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null
  [[ -L "$TEST_HOME/.codex/AGENTS.md" ]]
  [[ "$(readlink "$TEST_HOME/.codex/AGENTS.md")" == "$original_target" ]]
done

printf 'Codex Skill link/unlink test passed.\n'
