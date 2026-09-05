#!/bin/sh
"$1" -c "import sys" >/dev/null 2>&1 && exit 0
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Memory engine warning: the configured Python interpreter is not running. Run the doctor skill."}}\n'
