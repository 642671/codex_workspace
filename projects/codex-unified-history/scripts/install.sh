#!/usr/bin/env bash
set -euo pipefail

LABEL="com.local.codex-unified-history"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/.codex/unified-history"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$ROOT/launchagents/com.example.codex-unified-history.plist"

mkdir -p "$TARGET_DIR" "$HOME/Library/LaunchAgents"

if [[ -f "$TARGET_DIR/codex_unified_history.py" ]]; then
  cp "$TARGET_DIR/codex_unified_history.py" "$TARGET_DIR/codex_unified_history.py.bak.$(date +%Y%m%d-%H%M%S)"
fi

cp "$ROOT/scripts/codex_unified_history.py" "$TARGET_DIR/codex_unified_history.py"
cp "$ROOT/scripts/codex_unified_history_agent.sh" "$TARGET_DIR/codex_unified_history_agent.sh"
chmod +x "$TARGET_DIR/codex_unified_history.py" "$TARGET_DIR/codex_unified_history_agent.sh"

sed "s#__HOME__#$HOME#g" "$TEMPLATE" > "$PLIST"
plutil -lint "$PLIST" >/dev/null

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

echo "Installed $LABEL"
echo "Script: $TARGET_DIR/codex_unified_history.py"
echo "LaunchAgent: $PLIST"

