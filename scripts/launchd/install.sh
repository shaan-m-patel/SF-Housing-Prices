#!/bin/zsh
# Install (or remove) the sfrent launchd agents for the current user.
#   scripts/launchd/install.sh                        # all jobs
#   scripts/launchd/install.sh rent-board zori craigslist   # only these jobs
#   scripts/launchd/install.sh --uninstall [jobs...]
# Jobs: rent-board (monthly), zori (monthly), rentcast (weekly), craigslist (weekly).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
mkdir -p "$AGENTS" "$REPO/logs"

MODE="install"
if [[ "${1:-}" == "--uninstall" ]]; then
  MODE="uninstall"
  shift
fi
JOBS=("$@")
if (( ${#JOBS} == 0 )); then
  JOBS=(rent-board zori rentcast craigslist)
fi

for job in "${JOBS[@]}"; do
  label="com.sfrent.$job"
  template="$HERE/$label.plist"
  target="$AGENTS/$label.plist"
  [[ -f "$template" ]] || { echo "unknown job: $job" >&2; exit 1; }
  launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
  if [[ "$MODE" == "uninstall" ]]; then
    rm -f "$target"
    echo "removed $label"
    continue
  fi
  sed "s|__REPO__|$REPO|g" "$template" >"$target"
  plutil -lint -s "$target"
  launchctl bootstrap "$DOMAIN" "$target"
  echo "loaded $label"
done

[[ "$MODE" == "uninstall" ]] || launchctl list | grep com.sfrent || true
