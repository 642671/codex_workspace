# Verification

## Check active provider

```bash
python3 - <<'PY'
from pathlib import Path
import re
text = Path.home().joinpath(".codex/config.toml").read_text(encoding="utf-8")
m = re.search(r'(?m)^\s*model_provider\s*=\s*"?([A-Za-z0-9_.-]+)"?', text)
print(m.group(1) if m else "openai")
PY
```

## Check history provider distribution

```bash
sqlite3 ~/.codex/state_5.sqlite \
"select model_provider,count(*) from threads group by model_provider;"
```

## Check duplicate groups

```bash
sqlite3 -header -column ~/.codex/state_5.sqlite \
"select count(*) duplicate_groups, coalesce(sum(c-1),0) removable_rows
 from (
   select title, first_user_message, created_at, count(*) c
   from threads
   group by title, first_user_message, created_at
   having c>1
 );"
```

## Check session index size

```bash
wc -l ~/.codex/session_index.jsonl
sqlite3 ~/.codex/state_5.sqlite "select count(*) from threads where archived=0;"
```

## Check LaunchAgent

```bash
plutil -lint ~/Library/LaunchAgents/com.local.codex-unified-history.plist
launchctl print gui/$(id -u)/com.local.codex-unified-history
```

## Check logs

```bash
tail -20 ~/.codex/unified-history/unified-history.log
```

