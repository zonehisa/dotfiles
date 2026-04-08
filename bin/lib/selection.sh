#!/bin/bash

copy_selection_to_clipboard() {
    local previous_clipboard copied_text

    previous_clipboard=$(pbpaste)

    /usr/bin/osascript <<'APPLESCRIPT'
tell application "System Events"
    set frontAppName to name of first application process whose frontmost is true
    if frontAppName is not "Raycast" then
        keystroke "c" using command down
    end if
end tell
APPLESCRIPT

    for _ in 1 2 3 4 5 6 7 8; do
        /bin/sleep 0.05
        copied_text=$(pbpaste)
        if [ "$copied_text" != "$previous_clipboard" ]; then
            printf '%s' "$copied_text"
            return 0
        fi
    done

    return 1
}
