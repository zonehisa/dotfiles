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

assert_regular_copy() {
  local path="$1"
  local target="$2"
  [[ -f "$path" && ! -L "$path" ]] || fail "expected regular file: $path"
  cmp -s "$target" "$path" || fail "unexpected copied content: $path"
}

agent_marker_path() {
  printf '%s.dotfiles-managed\n' "$1"
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
assert_regular_copy "$reviewer_link" "$DOTFILES_DIR/codex/agents/reviewer-luna.toml"
assert_regular_copy "$operator_link" "$DOTFILES_DIR/codex/agents/git-operator-luna.toml"
assert_regular_copy "$implementer_link" "$DOTFILES_DIR/codex/agents/implementer-luna.toml"
assert_regular_copy "$explorer_link" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
assert_regular_copy "$verifier_link" "$DOTFILES_DIR/codex/agents/verifier-luna.toml"

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
for agent_path in "$reviewer_link" "$operator_link" "$implementer_link" "$explorer_link" "$verifier_link"; do
  assert_absent "$(agent_marker_path "$agent_path")"
done

IDENTICAL_HOME="$TEST_ROOT/identical-agent"
mkdir -p "$IDENTICAL_HOME/.codex/agents"
cp "$DOTFILES_DIR/codex/agents/reviewer-luna.toml" "$IDENTICAL_HOME/.codex/agents/reviewer-luna.toml"
HOME="$IDENTICAL_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
identical_backup_count=$(find "$IDENTICAL_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
[[ "$identical_backup_count" == "1" ]] || fail "pre-existing identical agent file was not backed up"
identical_marker=$(agent_marker_path "$IDENTICAL_HOME/.codex/agents/reviewer-luna.toml")
[[ -f "$identical_marker" && ! -L "$identical_marker" ]] || fail "agent ownership marker was not created"
HOME="$IDENTICAL_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex >/dev/null
[[ -f "$IDENTICAL_HOME/.codex/agents/reviewer-luna.toml" && ! -L "$IDENTICAL_HOME/.codex/agents/reviewer-luna.toml" ]] || fail "pre-existing identical agent file was removed"
assert_absent "$identical_marker"

MISSING_COPY_HOME="$TEST_ROOT/missing-managed-copy"
mkdir -p "$MISSING_COPY_HOME/.codex/agents"
printf 'pre-existing reviewer configuration\n' > "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml"
HOME="$MISSING_COPY_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
missing_copy_marker=$(agent_marker_path "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml")
rm "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml"
HOME="$MISSING_COPY_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex >/dev/null
[[ -f "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml" && ! -L "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml" ]] || fail "missing managed copy did not restore original file"
[[ "$(cat "$MISSING_COPY_HOME/.codex/agents/reviewer-luna.toml")" == "pre-existing reviewer configuration" ]] || fail "missing managed copy restored wrong content"
assert_absent "$missing_copy_marker"

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
assert_regular_copy "$ROLE_HOME/.codex/agents/explorer-luna.toml" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
assert_regular_copy "$ROLE_HOME/.codex/agents/verifier-luna.toml" "$DOTFILES_DIR/codex/agents/verifier-luna.toml"
[[ "$(cat "$explorer_original")" == "existing explorer configuration" ]] || fail "copy install followed explorer symlink"

HOME="$ROLE_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null
assert_link "$ROLE_HOME/.codex/agents/explorer-luna.toml" "$explorer_original"
assert_link "$ROLE_HOME/.codex/agents/verifier-luna.toml" "$verifier_original"

LEGACY_HOME="$TEST_ROOT/legacy-agent-link"
mkdir -p "$LEGACY_HOME/.codex/agents"
ln -s "$DOTFILES_DIR/codex/agents/explorer-luna.toml" "$LEGACY_HOME/.codex/agents/explorer-luna.toml"
HOME="$LEGACY_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
assert_regular_copy "$LEGACY_HOME/.codex/agents/explorer-luna.toml" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
HOME="$LEGACY_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex >/dev/null
assert_absent "$LEGACY_HOME/.codex/agents/explorer-luna.toml"

CODEX_ONLY_HOME="$TEST_ROOT/codex-only"
mkdir -p "$CODEX_ONLY_HOME/.codex/agents" "$CODEX_ONLY_HOME/.codex/skills" "$CODEX_ONLY_HOME/.config"
printf 'keep shell config\n' > "$CODEX_ONLY_HOME/.zshrc"
printf 'keep desktop config\n' > "$CODEX_ONLY_HOME/.config/desktop.toml"
printf 'existing Codex instructions\n' > "$CODEX_ONLY_HOME/.codex/AGENTS.md"
printf 'existing reviewer configuration\n' > "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml"
printf 'existing Codex skill\n' > "$CODEX_ONLY_HOME/.codex/skills/pr-evidence-video"

HOME="$CODEX_ONLY_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
assert_link "$CODEX_ONLY_HOME/.agents/skills/parallel-worktree" "$DOTFILES_DIR/codex/skills/parallel-worktree"
assert_link "$CODEX_ONLY_HOME/.codex/AGENTS.md" "$DOTFILES_DIR/codex/AGENTS.md"
assert_link "$CODEX_ONLY_HOME/.codex/skills/pr-evidence-video" "$DOTFILES_DIR/codex/skills/pr-evidence-video"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml" "$DOTFILES_DIR/codex/agents/reviewer-luna.toml"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/implementer-luna.toml" "$DOTFILES_DIR/codex/agents/implementer-luna.toml"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/explorer-luna.toml" "$DOTFILES_DIR/codex/agents/explorer-luna.toml"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/verifier-luna.toml" "$DOTFILES_DIR/codex/agents/verifier-luna.toml"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/git-operator-luna.toml" "$DOTFILES_DIR/codex/agents/git-operator-luna.toml"

agent_backup_count_before=$(find "$CODEX_ONLY_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
HOME="$CODEX_ONLY_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
agent_backup_count_after=$(find "$CODEX_ONLY_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
[[ "$agent_backup_count_after" == "$agent_backup_count_before" ]] || fail "repeated link-codex created an agent backup"
assert_regular_copy "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml" "$DOTFILES_DIR/codex/agents/reviewer-luna.toml"
[[ ! -L "$CODEX_ONLY_HOME/.zshrc" ]] || fail "link-codex must not link shell configuration"
[[ "$(cat "$CODEX_ONLY_HOME/.zshrc")" == "keep shell config" ]] || fail "link-codex changed shell configuration"
[[ ! -L "$CODEX_ONLY_HOME/.config/desktop.toml" ]] || fail "link-codex must not link app configuration"
[[ "$(cat "$CODEX_ONLY_HOME/.config/desktop.toml")" == "keep desktop config" ]] || fail "link-codex changed app configuration"

HOME="$CODEX_ONLY_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex >/dev/null
assert_absent "$CODEX_ONLY_HOME/.agents/skills/parallel-worktree"
[[ -f "$CODEX_ONLY_HOME/.codex/AGENTS.md" && ! -L "$CODEX_ONLY_HOME/.codex/AGENTS.md" ]] || fail "unlink-codex did not restore AGENTS.md"
[[ "$(cat "$CODEX_ONLY_HOME/.codex/AGENTS.md")" == "existing Codex instructions" ]] || fail "unlink-codex restored wrong AGENTS.md"
[[ -f "$CODEX_ONLY_HOME/.codex/skills/pr-evidence-video" && ! -L "$CODEX_ONLY_HOME/.codex/skills/pr-evidence-video" ]] || fail "unlink-codex did not restore PR evidence skill"
[[ "$(cat "$CODEX_ONLY_HOME/.codex/skills/pr-evidence-video")" == "existing Codex skill" ]] || fail "unlink-codex restored wrong PR evidence skill"
[[ -f "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml" && ! -L "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml" ]] || fail "unlink-codex did not restore reviewer configuration"
[[ "$(cat "$CODEX_ONLY_HOME/.codex/agents/reviewer-luna.toml")" == "existing reviewer configuration" ]] || fail "unlink-codex restored wrong reviewer configuration"
assert_absent "$CODEX_ONLY_HOME/.codex/agents/implementer-luna.toml"
assert_absent "$CODEX_ONLY_HOME/.codex/agents/explorer-luna.toml"
assert_absent "$CODEX_ONLY_HOME/.codex/agents/verifier-luna.toml"
assert_absent "$CODEX_ONLY_HOME/.codex/agents/git-operator-luna.toml"
for agent_name in implementer explorer verifier git-operator reviewer; do
  assert_absent "$(agent_marker_path "$CODEX_ONLY_HOME/.codex/agents/${agent_name}-luna.toml")"
done
[[ ! -L "$CODEX_ONLY_HOME/.zshrc" && "$(cat "$CODEX_ONLY_HOME/.zshrc")" == "keep shell config" ]] || fail "unlink-codex changed shell configuration"
[[ ! -L "$CODEX_ONLY_HOME/.config/desktop.toml" && "$(cat "$CODEX_ONLY_HOME/.config/desktop.toml")" == "keep desktop config" ]] || fail "unlink-codex changed app configuration"

MODIFIED_HOME="$TEST_ROOT/modified-agent"
mkdir -p "$MODIFIED_HOME/.codex/agents"
HOME="$MODIFIED_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
modified_marker=$(agent_marker_path "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml")
rm "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml"
printf 'user-modified reviewer configuration\n' > "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml"
unlink_output=$(HOME="$MODIFIED_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex 2>&1)
[[ -f "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml" && ! -L "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml" ]] || fail "unlink-codex removed modified agent copy"
[[ "$(cat "$MODIFIED_HOME/.codex/agents/reviewer-luna.toml")" == "user-modified reviewer configuration" ]] || fail "unlink-codex changed modified agent copy"
[[ "$unlink_output" == *"保持"* ]] || fail "unlink-codex did not warn about modified agent copy"
assert_absent "$modified_marker"

SOURCE_UPDATE_ROOT="$TEST_ROOT/source-update"
SOURCE_UPDATE_HOME="$TEST_ROOT/source-update-home"
mkdir -p "$SOURCE_UPDATE_ROOT/codex/agents" "$SOURCE_UPDATE_HOME/.codex/agents"
cp "$DOTFILES_DIR/setup.sh" "$SOURCE_UPDATE_ROOT/setup.sh"
cp "$DOTFILES_DIR/codex/agents/reviewer-luna.toml" "$SOURCE_UPDATE_ROOT/codex/agents/reviewer-luna.toml"
source_update_copy="$SOURCE_UPDATE_HOME/.codex/agents/reviewer-luna.toml"
source_update_target="$SOURCE_UPDATE_ROOT/codex/agents/reviewer-luna.toml"
HOME="$SOURCE_UPDATE_HOME" bash "$SOURCE_UPDATE_ROOT/setup.sh" link-codex >/dev/null
assert_regular_copy "$source_update_copy" "$source_update_target"
source_update_backup_count_before=$(find "$SOURCE_UPDATE_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
printf '\n# source update\n' >> "$source_update_target"
HOME="$SOURCE_UPDATE_HOME" bash "$SOURCE_UPDATE_ROOT/setup.sh" link-codex >/dev/null
assert_regular_copy "$source_update_copy" "$source_update_target"
source_update_backup_count_after=$(find "$SOURCE_UPDATE_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
[[ "$source_update_backup_count_after" == "$source_update_backup_count_before" ]] || fail "clean source update created a backup chain"
rm "$source_update_copy"
printf 'user-modified before source update\n' > "$source_update_copy"
printf '\n# second source update\n' >> "$source_update_target"
HOME="$SOURCE_UPDATE_HOME" bash "$SOURCE_UPDATE_ROOT/setup.sh" link-codex >/dev/null
assert_regular_copy "$source_update_copy" "$source_update_target"
source_update_backup_count_modified=$(find "$SOURCE_UPDATE_HOME/.codex/agents" -maxdepth 1 -name 'reviewer-luna.toml.bak.*' -print | wc -l | tr -d ' ')
[[ "$source_update_backup_count_modified" == "$((source_update_backup_count_after + 1))" ]] || fail "modified agent copy was not backed up on source update"
HOME="$SOURCE_UPDATE_HOME" bash "$SOURCE_UPDATE_ROOT/setup.sh" unlink-codex >/dev/null
[[ "$(cat "$source_update_copy")" == "user-modified before source update" ]] || fail "source update did not preserve modified agent copy"

SOURCE_UNLINK_ROOT="$TEST_ROOT/source-change-before-unlink"
SOURCE_UNLINK_HOME="$TEST_ROOT/source-change-before-unlink-home"
mkdir -p "$SOURCE_UNLINK_ROOT/codex/agents" "$SOURCE_UNLINK_HOME/.codex/agents"
cp "$DOTFILES_DIR/setup.sh" "$SOURCE_UNLINK_ROOT/setup.sh"
cp "$DOTFILES_DIR/codex/agents/reviewer-luna.toml" "$SOURCE_UNLINK_ROOT/codex/agents/reviewer-luna.toml"
source_unlink_copy="$SOURCE_UNLINK_HOME/.codex/agents/reviewer-luna.toml"
source_unlink_target="$SOURCE_UNLINK_ROOT/codex/agents/reviewer-luna.toml"
printf 'original file before source change\n' > "$source_unlink_copy"
HOME="$SOURCE_UNLINK_HOME" bash "$SOURCE_UNLINK_ROOT/setup.sh" link-codex >/dev/null
printf '\n# source changed before unlink\n' >> "$source_unlink_target"
HOME="$SOURCE_UNLINK_HOME" bash "$SOURCE_UNLINK_ROOT/setup.sh" unlink-codex >/dev/null
[[ "$(cat "$source_unlink_copy")" == "original file before source change" ]] || fail "unlink retained an unchanged managed copy after source change"
assert_absent "$(agent_marker_path "$source_unlink_copy")"

SOURCE_EQUAL_ROOT="$TEST_ROOT/source-equal-current"
SOURCE_EQUAL_HOME="$TEST_ROOT/source-equal-current-home"
mkdir -p "$SOURCE_EQUAL_ROOT/codex/agents" "$SOURCE_EQUAL_HOME/.codex/agents"
cp "$DOTFILES_DIR/setup.sh" "$SOURCE_EQUAL_ROOT/setup.sh"
cp "$DOTFILES_DIR/codex/agents/reviewer-luna.toml" "$SOURCE_EQUAL_ROOT/codex/agents/reviewer-luna.toml"
source_equal_copy="$SOURCE_EQUAL_HOME/.codex/agents/reviewer-luna.toml"
source_equal_target="$SOURCE_EQUAL_ROOT/codex/agents/reviewer-luna.toml"
HOME="$SOURCE_EQUAL_HOME" bash "$SOURCE_EQUAL_ROOT/setup.sh" link-codex >/dev/null
printf '\n# source changed before user replacement\n' >> "$source_equal_target"
cp "$source_equal_target" "$source_equal_copy"
source_equal_unlink_output=$(HOME="$SOURCE_EQUAL_HOME" bash "$SOURCE_EQUAL_ROOT/setup.sh" unlink-codex 2>&1)
[[ -f "$source_equal_copy" && ! -L "$source_equal_copy" ]] || fail "unlink removed user-modified copy matching current source"
cmp -s "$source_equal_target" "$source_equal_copy" || fail "user-modified current-source copy changed"
assert_absent "$(agent_marker_path "$source_equal_copy")"
[[ "$source_equal_unlink_output" == *"保持"* ]] || fail "unlink did not warn for user-modified current-source copy"

REPLACED_VALID_HOME="$TEST_ROOT/replaced-valid-agent"
mkdir -p "$REPLACED_VALID_HOME/.codex/agents" "$REPLACED_VALID_HOME/original"
replaced_valid_copy="$REPLACED_VALID_HOME/.codex/agents/reviewer-luna.toml"
replaced_valid_marker=$(agent_marker_path "$replaced_valid_copy")
replaced_valid_target="$REPLACED_VALID_HOME/original/reviewer-luna.toml"
printf 'valid replacement target\n' > "$replaced_valid_target"
printf 'pre-existing marker metadata\n' > "$replaced_valid_marker"
HOME="$REPLACED_VALID_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
rm "$replaced_valid_copy"
ln -s "$replaced_valid_target" "$replaced_valid_copy"
replaced_valid_unlink_output=$(HOME="$REPLACED_VALID_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex 2>&1)
assert_link "$replaced_valid_copy" "$replaced_valid_target"
[[ -f "$replaced_valid_marker" && ! -L "$replaced_valid_marker" ]] || fail "valid replacement did not restore marker backup"
[[ "$(cat "$replaced_valid_marker")" == "pre-existing marker metadata" ]] || fail "valid replacement restored wrong marker metadata"
[[ "$replaced_valid_unlink_output" == *"保持"* ]] || fail "valid replacement did not warn"

REPLACED_DANGLING_HOME="$TEST_ROOT/replaced-dangling-agent"
mkdir -p "$REPLACED_DANGLING_HOME/.codex/agents"
replaced_dangling_copy="$REPLACED_DANGLING_HOME/.codex/agents/reviewer-luna.toml"
replaced_dangling_marker=$(agent_marker_path "$replaced_dangling_copy")
replaced_dangling_target="$REPLACED_DANGLING_HOME/missing/reviewer-luna.toml"
printf 'pre-existing marker metadata\n' > "$replaced_dangling_marker"
HOME="$REPLACED_DANGLING_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
rm "$replaced_dangling_copy"
ln -s "$replaced_dangling_target" "$replaced_dangling_copy"
replaced_dangling_unlink_output=$(HOME="$REPLACED_DANGLING_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex 2>&1)
assert_link "$replaced_dangling_copy" "$replaced_dangling_target"
[[ -f "$replaced_dangling_marker" && ! -L "$replaced_dangling_marker" ]] || fail "dangling replacement did not restore marker backup"
[[ "$(cat "$replaced_dangling_marker")" == "pre-existing marker metadata" ]] || fail "dangling replacement restored wrong marker metadata"
[[ "$replaced_dangling_unlink_output" == *"保持"* ]] || fail "dangling replacement did not warn"

BACKUP_ORDER_HOME="$TEST_ROOT/backup-order"
mkdir -p "$BACKUP_ORDER_HOME/.codex/agents"
backup_order_copy="$BACKUP_ORDER_HOME/.codex/agents/reviewer-luna.toml"
HOME="$BACKUP_ORDER_HOME" bash "$DOTFILES_DIR/setup.sh" link-codex >/dev/null
printf 'backup suffix nine\n' > "${backup_order_copy}.bak.20260101_000000.9"
printf 'backup suffix ten\n' > "${backup_order_copy}.bak.20260101_000000.10"
HOME="$BACKUP_ORDER_HOME" bash "$DOTFILES_DIR/setup.sh" unlink-codex >/dev/null
[[ "$(cat "$backup_order_copy")" == "backup suffix ten" ]] || fail "numeric backup suffix ordering restored the wrong file"

ALL_HOME="$TEST_ROOT/no-arg"
mkdir -p "$ALL_HOME/.config/sheldon" "$ALL_HOME/.codex"
printf 'existing shell config\n' > "$ALL_HOME/.zshrc"
printf 'existing sheldon config\n' > "$ALL_HOME/.config/sheldon/plugins.toml"
printf 'existing no-arg instructions\n' > "$ALL_HOME/.codex/AGENTS.md"
HOME="$ALL_HOME" bash "$DOTFILES_DIR/setup.sh" >/dev/null
assert_link "$ALL_HOME/.zshrc" "$DOTFILES_DIR/.zshrc"
assert_link "$ALL_HOME/.config/sheldon/plugins.toml" "$DOTFILES_DIR/.config/sheldon/plugins.toml"
assert_link "$ALL_HOME/.codex/AGENTS.md" "$DOTFILES_DIR/codex/AGENTS.md"
assert_regular_copy "$ALL_HOME/.codex/agents/implementer-luna.toml" "$DOTFILES_DIR/codex/agents/implementer-luna.toml"
HOME="$ALL_HOME" bash "$DOTFILES_DIR/setup.sh" unlink >/dev/null
[[ -f "$ALL_HOME/.zshrc" && "$(cat "$ALL_HOME/.zshrc")" == "existing shell config" ]] || fail "no-arg behavior changed shell link"
[[ -f "$ALL_HOME/.config/sheldon/plugins.toml" && "$(cat "$ALL_HOME/.config/sheldon/plugins.toml")" == "existing sheldon config" ]] || fail "no-arg behavior changed app config"
[[ -f "$ALL_HOME/.codex/AGENTS.md" && "$(cat "$ALL_HOME/.codex/AGENTS.md")" == "existing no-arg instructions" ]] || fail "no-arg behavior changed Codex link"
assert_absent "$ALL_HOME/.codex/agents/implementer-luna.toml"

STATUS_AFTER="$(git -C "$DOTFILES_DIR" status --short)"
[[ "$STATUS_AFTER" == "$STATUS_BEFORE" ]] || fail "setup test changed repository status"

printf 'Codex Skill link/unlink test passed.\n'
printf 'PR evidence skill link/unlink test passed.\n'
