#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null

parallel_link="$TEST_HOME/.agents/skills/parallel-worktree"
workflow_link="$TEST_HOME/.codex/skills/git-workflow"

[[ -L "$parallel_link" ]]
[[ "$(readlink "$parallel_link")" == "$DOTFILES_DIR/codex/skills/parallel-worktree" ]]
[[ -L "$workflow_link" ]]
[[ "$(readlink "$workflow_link")" == "$DOTFILES_DIR/codex/skills/git-workflow" ]]

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null

[[ ! -e "$parallel_link" && ! -L "$parallel_link" ]]
[[ ! -e "$workflow_link" && ! -L "$workflow_link" ]]

printf 'Codex Skill link/unlink test passed.\n'
