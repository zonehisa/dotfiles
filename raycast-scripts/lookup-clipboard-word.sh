#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Lookup Clipboard Word
# @raycast.mode silent
# @raycast.packageName Dictionary
# @raycast.icon 📋

# Optional parameters:
# @raycast.needsConfirmation false

/usr/bin/osascript <<'APPLESCRIPT'
tell application "System Events"
    keystroke "c" using command down
end tell
APPLESCRIPT

/bin/sleep 0.2

term="$(pbpaste | tr '\n' ' ' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"

if [ -z "$term" ]; then
  echo "クリップボードが空です"
  exit 1
fi

encoded_term=$(/usr/bin/python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$term")

/usr/bin/open "dict:///$encoded_term"
