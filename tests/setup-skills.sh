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

STATUS_BEFORE="$(git -C "$DOTFILES_DIR" status --short)"

TEST_HOME="$TEST_ROOT/regular"

mkdir -p "$TEST_HOME/.codex/agents"
printf 'existing global instructions\n' > "$TEST_HOME/.codex/AGENTS.md"
printf 'existing implementer configuration\n' > "$TEST_HOME/.codex/agents/implementer-luna.toml"
mkdir -p "$TEST_HOME/.codex/skills"
printf 'existing PR evidence skill\n' > "$TEST_HOME/.codex/skills/pr-evidence-video"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null

parallel_link="$TEST_HOME/.agents/skills/parallel-worktree"
agents_link="$TEST_HOME/.codex/AGENTS.md"
workflow_link="$TEST_HOME/.codex/skills/git-workflow"
evidence_link="$TEST_HOME/.codex/skills/pr-evidence-video"
reviewer_link="$TEST_HOME/.codex/agents/reviewer-luna.toml"
operator_link="$TEST_HOME/.codex/agents/git-operator-luna.toml"
implementer_link="$TEST_HOME/.codex/agents/implementer-luna.toml"
explorer_link="$TEST_HOME/.codex/agents/explorer-luna.toml"
verifier_link="$TEST_HOME/.codex/agents/verifier-luna.toml"

assert_link "$parallel_link" "$DOTFILES_DIR/codex/skills/parallel-worktree"
assert_link "$agents_link" "$DOTFILES_DIR/codex/AGENTS.md"
assert_link "$workflow_link" "$DOTFILES_DIR/codex/skills/git-workflow"
assert_link "$evidence_link" "$DOTFILES_DIR/codex/skills/pr-evidence-video"
assert_link "$reviewer_link" "$DOTFILES_DIR/codex/agents/reviewer-luna.toml"
assert_link "$operator_link" "$DOTFILES_DIR/codex/agents/git-operator-luna.toml"
assert_link "$implementer_link" "$DOTFILES_DIR/codex/agents/implementer-luna.toml"
assert_link "$explorer_link" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
assert_link "$verifier_link" "$DOTFILES_DIR/codex/agents/verifier-luna.toml"

HOME="$TEST_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null

assert_absent "$parallel_link"
[[ -f "$agents_link" && ! -L "$agents_link" ]] || fail "expected restored regular file: $agents_link"
[[ "$(cat "$agents_link")" == "existing global instructions" ]] || fail "unexpected restored AGENTS.md content"
assert_absent "$workflow_link"
[[ -f "$evidence_link" && ! -L "$evidence_link" ]] || fail "expected restored regular evidence skill: $evidence_link"
[[ "$(cat "$evidence_link")" == "existing PR evidence skill" ]] || fail "unexpected restored evidence skill"
assert_absent "$reviewer_link"
assert_absent "$operator_link"
[[ -f "$implementer_link" && ! -L "$implementer_link" ]] || fail "expected restored regular file: $implementer_link"
[[ "$(cat "$implementer_link")" == "existing implementer configuration" ]] || fail "unexpected restored implementer configuration"
assert_absent "$explorer_link"
assert_absent "$verifier_link"

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

ROLE_HOME="$TEST_ROOT/agent-links"
mkdir -p "$ROLE_HOME/.codex/agents" "$ROLE_HOME/original"
explorer_original="$ROLE_HOME/original/explorer-luna.toml"
verifier_original="$ROLE_HOME/original/missing-verifier-luna.toml"
printf 'existing explorer configuration\n' > "$explorer_original"
ln -s "$explorer_original" "$ROLE_HOME/.codex/agents/explorer-luna.toml"
ln -s "$verifier_original" "$ROLE_HOME/.codex/agents/verifier-luna.toml"

HOME="$ROLE_HOME" bash "$DOTFILES_DIR/setup.sh" link >/dev/null
assert_link "$ROLE_HOME/.codex/agents/explorer-luna.toml" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
assert_link "$ROLE_HOME/.codex/agents/verifier-luna.toml" "$DOTFILES_DIR/codex/agents/verifier-luna.toml"

HOME="$ROLE_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null
assert_link "$ROLE_HOME/.codex/agents/explorer-luna.toml" "$explorer_original"
assert_link "$ROLE_HOME/.codex/agents/verifier-luna.toml" "$verifier_original"

STATUS_AFTER="$(git -C "$DOTFILES_DIR" status --short)"
[[ "$STATUS_AFTER" == "$STATUS_BEFORE" ]] || fail "setup test changed repository status"

printf 'Codex Skill link/unlink test passed.\n'
printf 'PR evidence skill link/unlink test passed.\n'
