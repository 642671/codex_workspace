#!/usr/bin/env bash
set -euo pipefail

LOG="$HOME/.codex/unified-history/unified-history.log"
SCRIPT="$HOME/.codex/unified-history/codex_unified_history.py"
FINGERPRINT="$HOME/.codex/unified-history/fingerprint"

mkdir -p "$(dirname "$LOG")"

compute_fingerprint() {
  python3 - <<'PY'
import hashlib
from pathlib import Path

paths = [
    Path.home() / ".cc-switch" / "cc-switch.db",
    Path.home() / ".codex" / "config.toml",
    Path.home() / ".codex" / "state_5.sqlite",
]
digest = hashlib.sha256()
for path in paths:
    if path.exists():
        stat = path.stat()
        digest.update(str(path).encode())
        digest.update(str(stat.st_mtime_ns).encode())
        digest.update(str(stat.st_size).encode())
print(digest.hexdigest())
PY
}

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] unified history check"
  before="$(compute_fingerprint)"
  if [[ -f "$FINGERPRINT" ]] && [[ "$(cat "$FINGERPRINT")" == "$before" ]]; then
    echo "No relevant changes; skip"
    exit 0
  fi
  python3 "$SCRIPT"
  compute_fingerprint > "$FINGERPRINT"
} >> "$LOG" 2>&1
