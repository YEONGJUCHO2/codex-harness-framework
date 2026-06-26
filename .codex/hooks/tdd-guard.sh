#!/usr/bin/env bash
# TDD Guard Hook - PreToolUse[Edit|Write|apply_patch]
# Blocks implementation edits when no corresponding test file exists.
#
# Based on the Codex live demo Harness setup. The source hook checks direct
# file edit input; this version also supports Codex apply_patch payloads.

set -u

INPUT=$(cat)

if [ -z "$INPUT" ]; then
  exit 0
fi

PROJECT_ROOT=${CODEX_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}}

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

PATHS=$(
  printf '%s' "$INPUT" | python3 -c '
import json
import re
import sys

try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

if not isinstance(payload, dict):
    sys.exit(0)

tool_input = payload.get("tool_input") or {}
items = []

def collect_patch_text(value):
    if not isinstance(value, str):
        return

    for line in value.splitlines():
        match = re.match(r"^\*\*\* (Add|Update|Delete) File: (.+)$", line)
        if match:
            items.append((match.group(1).lower(), match.group(2).strip()))
            continue
        match = re.match(r"^\*\*\* Move to: (.+)$", line)
        if match:
            items.append(("update", match.group(1).strip()))


if isinstance(tool_input, str):
    collect_patch_text(tool_input)
elif isinstance(tool_input, dict):
    for key in ("file_path", "path", "filename"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            items.append(("update", value))

    for key in ("command", "cmd", "patch", "input"):
        collect_patch_text(tool_input.get(key))

seen = set()
for action, path in items:
    key = (action, path)
    if key in seen:
        continue
    seen.add(key)
    print(f"{action}\t{path}")
'
)

if [ -z "$PATHS" ]; then
  exit 0
fi

has_test_for() {
  local file_path="$1"
  local project_file_path dir_name base_name parent_dir ext

  case "$file_path" in
    /*) project_file_path="$file_path" ;;
    *) project_file_path="${PROJECT_ROOT}/${file_path}" ;;
  esac

  dir_name=$(dirname "$project_file_path")
  base_name=$(basename "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$//')
  parent_dir=$(dirname "$dir_name")

  for ext in ts tsx js jsx; do
    [ -f "${dir_name}/${base_name}.test.${ext}" ] && return 0
    [ -f "${dir_name}/${base_name}.spec.${ext}" ] && return 0
    [ -f "${dir_name}/__tests__/${base_name}.test.${ext}" ] && return 0
    [ -f "${dir_name}/__tests__/${base_name}.spec.${ext}" ] && return 0
    [ -f "${parent_dir}/__tests__/${base_name}.test.${ext}" ] && return 0
    [ -f "${parent_dir}/__tests__/${base_name}.spec.${ext}" ] && return 0
    [ -f "${PROJECT_ROOT}/src/__tests__/${base_name}.test.${ext}" ] && return 0
    [ -f "${PROJECT_ROOT}/src/__tests__/${base_name}.spec.${ext}" ] && return 0
  done

  return 1
}

while IFS=$'\t' read -r action file_path; do
  [ -z "$file_path" ] && continue
  [ "$action" = "delete" ] && continue

  case "$file_path" in
    *test*|*spec*|*.test.*|*.spec.*|*__tests__*) continue ;;
  esac

  case "$file_path" in
    *.json|*.css|*.scss|*.md|*.yml|*.yaml|*.env*|*.config.*|*tailwind*|*postcss*|*next.config*|*tsconfig*) continue ;;
  esac

  case "$file_path" in
    */types/*|*/types.ts|*/types.d.ts) continue ;;
  esac

  case "$file_path" in
    */layout.tsx|*/layout.ts|*/page.tsx|*/page.ts|*/loading.tsx|*/error.tsx|*/not-found.tsx|*/globals.css) continue ;;
  esac

  case "$file_path" in
    *.ts|*.tsx|*.js|*.jsx)
      if ! has_test_for "$file_path"; then
        base_name=$(basename "$file_path" | sed -E 's/\.(ts|tsx|js|jsx)$//')
        deny "TDD GUARD: '${base_name}'에 대한 테스트 파일이 존재하지 않습니다. 구현 코드를 작성하기 전에 테스트를 먼저 작성하세요. (테스트 파일 예: ${base_name}.test.ts)"
        exit 0
      fi
      ;;
  esac
done <<< "$PATHS"

exit 0
