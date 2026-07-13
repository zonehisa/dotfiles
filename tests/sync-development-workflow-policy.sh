#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_REPO="$(mktemp -d)"
trap 'rm -rf "$TEST_REPO"' EXIT

git -C "$TEST_REPO" init -q

"$DOTFILES_DIR/bin/sync-development-workflow-policy" --repo "$TEST_REPO"
"$DOTFILES_DIR/bin/sync-development-workflow-policy" --repo "$TEST_REPO" --check

grep -q 'GENERATED FILE: DO NOT EDIT' "$TEST_REPO/.agent/policies/development-workflow.generated.md"
test -x "$TEST_REPO/.agent/scripts/review_fingerprint.py"

printf '\nmodified\n' >> "$TEST_REPO/.agent/policies/development-workflow.generated.md"
if "$DOTFILES_DIR/bin/sync-development-workflow-policy" --repo "$TEST_REPO" --check; then
  echo "tampered generated policy was not detected" >&2
  exit 1
fi

printf 'Development workflow policy sync test passed.\n'
