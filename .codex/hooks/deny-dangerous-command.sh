#!/usr/bin/env bash

set -u

INPUT=$(cat)

if [ -z "$INPUT" ]; then
  exit 0
fi

deny() {
  local reason="$1"
  python3 - "$reason" <<'PY'
import json
import sys

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": sys.argv[1],
    }
}, ensure_ascii=False))
PY
}

COMMANDS=$(
  printf '%s' "$INPUT" | python3 -c '
import json
import sys

COMMAND_KEYS = {"cmd", "command", "script", "shell_command"}

try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

def emit_commands(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in COMMAND_KEYS and isinstance(item, str):
                print(item)
            elif isinstance(item, (dict, list)):
                emit_commands(item)
    elif isinstance(value, list):
        for item in value:
            emit_commands(item)

if isinstance(payload, dict):
    emit_commands(payload.get("tool_input", payload))
'
)

if [ -z "$COMMANDS" ]; then
  exit 0
fi

DANGEROUS_PATTERN='rm[[:space:]]+-rf|git[[:space:]]+push[[:space:]]+--force|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+filter-branch|git[[:space:]]+rebase[[:space:]]+(-i|--interactive)|DROP[[:space:]]+TABLE|TRUNCATE[[:space:]]+TABLE|DELETE[[:space:]]+FROM|vercel([[:space:]][^;&|]*)*[[:space:]]+--prod|firebase[[:space:]]+deploy|supabase[[:space:]]+db[[:space:]]+(push|reset)|prisma[[:space:]]+migrate[[:space:]]+deploy|drizzle-kit[[:space:]]+push|railway[[:space:]]+up|fly[[:space:]]+deploy|kubectl[[:space:]]+(apply|delete)'

while IFS= read -r command; do
  [ -z "$command" ] && continue

  if printf '%s\n' "$command" | grep -Eiq "$DANGEROUS_PATTERN"; then
    deny "DANGEROUS COMMAND GUARD: blocked high-risk command: ${command}"
    exit 0
  fi
done <<< "$COMMANDS"

exit 0
