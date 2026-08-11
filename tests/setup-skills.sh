#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() {
  printf 'Assertion failed: %s\n' "$1" >&2
  exit 1
}

assert_link() {
  local path="$1"
  local target="$2"
  [[ -L "$path" ]] || fail "expected symlink: $path"
  [[ "$(readlink "$path")" == "$target" ]] || fail "unexpected symlink target: $path"
}

assert_absent() {
  local path="$1"
  [[ ! -e "$path" && ! -L "$path" ]] || fail "expected absent path: $path"
}

TEST_HOME="$TEST_ROOT/regular"

mkdir -p "$TEST_HOME/.codex"
printf 'existing global instructions\n' > "$TEST_HOME/.codex/AGENTS.md"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null

parallel_link="$TEST_HOME/.agents/skills/parallel-worktree"
agents_link="$TEST_HOME/.codex/AGENTS.md"
workflow_link="$TEST_HOME/.codex/skills/git-workflow"
reviewer_link="$TEST_HOME/.codex/agents/reviewer-luna.toml"
operator_link="$TEST_HOME/.codex/agents/git-operator-luna.toml"

assert_link "$parallel_link" "$DOTFILES_DIR/codex/skills/parallel-worktree"
assert_link "$agents_link" "$DOTFILES_DIR/codex/AGENTS.md"
assert_link "$workflow_link" "$DOTFILES_DIR/codex/skills/git-workflow"
assert_link "$reviewer_link" "$DOTFILES_DIR/codex/agents/reviewer-luna.toml"
assert_link "$operator_link" "$DOTFILES_DIR/codex/agents/git-operator-luna.toml"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null

assert_absent "$parallel_link"
[[ -f "$agents_link" && ! -L "$agents_link" ]] || fail "expected restored regular file: $agents_link"
[[ "$(cat "$agents_link")" == "existing global instructions" ]] || fail "unexpected restored AGENTS.md content"
assert_absent "$workflow_link"
assert_absent "$reviewer_link"
assert_absent "$operator_link"

for kind in valid dangling; do
  TEST_HOME="$TEST_ROOT/$kind"
  mkdir -p "$TEST_HOME/.codex" "$TEST_HOME/original"
  original_target="$TEST_HOME/original/AGENTS.md"
  if [[ "$kind" == "valid" ]]; then
    printf 'linked global instructions\n' > "$original_target"
  fi
  ln -s "$original_target" "$TEST_HOME/.codex/AGENTS.md"

  HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null
  assert_link "$TEST_HOME/.codex/AGENTS.md" "$DOTFILES_DIR/codex/AGENTS.md"

  HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null
  assert_link "$TEST_HOME/.codex/AGENTS.md" "$original_target"
done

printf 'Codex Skill link/unlink test passed.\n'
