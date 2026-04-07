#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Auto Translate EN↔JP
# @raycast.mode silent
# @raycast.packageName Translation
# @raycast.icon 🔄

# Optional parameters:
# @raycast.shortcut cmd+shift+t
# @raycast.needsConfirmation false

/usr/bin/osascript <<'APPLESCRIPT'
tell application "System Events"
    keystroke "c" using command down
end tell
APPLESCRIPT

/bin/sleep 0.2

# クリップボードの内容を取得
text=$(pbpaste)

# 空チェック
if [ -z "$text" ]; then
    echo "クリップボードが空です"
    exit 1
fi

# 日本語文字が含まれているかチェック
if echo "$text" | grep -qE '[ぁ-んァ-ヶー一-龠０-９]'; then
    # 日本語 → 英語
    translation=$(trans -brief ja:en "$text" 2>/dev/null)
    echo "→ English"
else
    # 英語 → 日本語
    translation=$(trans -brief en:ja "$text" 2>/dev/null)
    echo "→ 日本語"
fi

# 翻訳結果をクリップボードにコピー
echo -n "$translation" | pbcopy
