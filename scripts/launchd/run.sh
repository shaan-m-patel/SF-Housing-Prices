#!/bin/zsh
# Entry point for the launchd jobs: `run.sh <source> [collector flags...]`.
# Runs the collector in prod mode, then rebuilds listings.parquet and the public aggregates.
# Row counts land in data/runlog.jsonl (`sfrent runlog`); stdout/stderr in logs/<source>.log.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
export SFRENT_ENV=prod
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p logs

SOURCE="$1"
shift
{
  echo "=== $(date -u +%FT%TZ) pull $SOURCE $*"
  uv run sfrent pull "$SOURCE" "$@"
  uv run sfrent build
} >>"logs/$SOURCE.log" 2>&1
