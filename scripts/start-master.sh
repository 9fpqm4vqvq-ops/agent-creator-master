#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
runtime="$repo_root/tools/claude/node_modules/.bin/claude"
if [[ ! -x "$runtime" ]]; then
  echo 'Install the runtime first: npm ci --prefix tools/claude --no-audit --no-fund' >&2
  exit 1
fi
exec "$runtime" --agent master-agent "$@"
