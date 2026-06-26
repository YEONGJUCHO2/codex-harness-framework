#!/usr/bin/env bash

set -u

PROJECT_ROOT=${CODEX_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}}

if [ ! -f "$PROJECT_ROOT/package.json" ]; then
  exit 0
fi

cd "$PROJECT_ROOT" || exit 1

npm run lint 2>&1 &&
  npm run build 2>&1 &&
  npm run test 2>&1
