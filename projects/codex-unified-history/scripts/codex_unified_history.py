#!/usr/bin/env python3
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CODEX_HOME = HOME / ".codex"
CODEX_CONFIG = CODEX_HOME / "config.toml"
CODEX_DB = CODEX_HOME / "state_5.sqlite"
CCSWITCH_DB = HOME / ".cc-switch" / "cc-switch.db"

MODEL_PROVIDER_RE = re.compile(
    r'(?m)^\s*model_provider\s*=\s*"?([A-Za-z0-9_.-]+)"?\s*$'
)
RESERVED_OPENAI_SECTION_RE = re.compile(r"(?m)^\s*\[model_providers\.openai\]\s*$")
PROVIDER_SECTION_RE = re.compile(
    r"(?m)^\s*\[model_providers\.([A-Za-z0-9_.-]+)\]\s*$"
)


def safe_provider_id(name):
    provider = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip())
    provider = re.sub(r"_+", "_", provider).strip("_.-")
    if not provider:
        provider = "custom_provider"
    if provider == "openai":
        provider = "openai_custom"
    return provider


def has_custom_provider(config):
    return bool(PROVIDER_SECTION_RE.search(config or ""))


def rewrite_provider_config(config, provider):
    config = config or ""
    if MODEL_PROVIDER_RE.search(config):
        config = MODEL_PROVIDER_RE.sub(f'model_provider = "{provider}"', config, count=1)
    else:
        config = f'model_provider = "{provider}"\n' + config.lstrip("\n")
    config = PROVIDER_SECTION_RE.sub(f"[model_providers.{provider}]", config)

    lines = config.splitlines()
    out = []
    in_provider = False
    name_done = False
    for line in lines:
        section = re.match(r"^\s*\[([^]]+)\]\s*$", line)
        if section:
            if in_provider and not name_done:
                out.append(f'name = "{provider}"')
            in_provider = section.group(1) == f"model_providers.{provider}"
            name_done = False
            out.append(line)
            continue
        if in_provider and re.match(r"^\s*name\s*=", line):
            out.append(f'name = "{provider}"')
            name_done = True
            continue
        out.append(line)
    if in_provider and not name_done:
        out.append(f'name = "{provider}"')
    return "\n".join(out).rstrip() + "\n"


def patch_ccswitch_provider_names():
    if not CCSWITCH_DB.exists():
        return 0, None
    conn = sqlite3.connect(CCSWITCH_DB)
    conn.execute("PRAGMA busy_timeout=5000")
    updated = 0
    current_provider = None
    try:
        rows = conn.execute(
            "SELECT id, name, is_current, settings_config FROM providers WHERE app_type='codex'"
        ).fetchall()
        for provider_id, display_name, is_current, raw in rows:
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                continue
            config = data.get("config") or ""
            auth = data.get("auth") if isinstance(data.get("auth"), dict) else {}
            if auth.get("auth_mode") == "chatgpt" and not has_custom_provider(config):
                target = "openai"
            elif has_custom_provider(config):
                target = safe_provider_id(display_name)
            else:
                target = read_provider_from_text(config) or "openai"

            new_config = rewrite_provider_config(config, target)
            if new_config != config:
                data["config"] = new_config
                conn.execute(
                    "UPDATE providers SET settings_config=? WHERE id=?",
                    (
                        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                        provider_id,
                    ),
                )
                updated += 1
            if is_current:
                current_provider = target
        conn.commit()
    finally:
        conn.close()
    return updated, current_provider


def read_provider_from_text(text):
    match = MODEL_PROVIDER_RE.search(text or "")
    if match:
        return match.group(1)
    return None


def read_active_provider() -> str:
    if not CODEX_CONFIG.exists():
        return "openai"
    text = CODEX_CONFIG.read_text(encoding="utf-8")
    return read_provider_from_text(text) or "openai"


def patch_current_config_provider(provider):
    if not CODEX_CONFIG.exists() or not provider:
        return False
    text = CODEX_CONFIG.read_text(encoding="utf-8")
    if not has_custom_provider(text):
        return False
    new_text = rewrite_provider_config(text, provider)
    if new_text != text:
        CODEX_CONFIG.write_text(new_text, encoding="utf-8")
        return True
    return False


def current_config_has_reserved_override() -> bool:
    if not CODEX_CONFIG.exists():
        return False
    text = CODEX_CONFIG.read_text(encoding="utf-8")
    return bool(RESERVED_OPENAI_SECTION_RE.search(text))


def patch_history_db(provider: str) -> int:
    if not CODEX_DB.exists():
        return 0
    conn = sqlite3.connect(CODEX_DB)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        changed = conn.execute(
            "UPDATE threads SET model_provider=? "
            "WHERE model_provider IS NULL OR model_provider<>?",
            (provider, provider),
        ).rowcount
        conn.commit()
    finally:
        conn.close()
    return changed


def parse_timestamp_ms(value):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    except ValueError:
        return None


def read_session_times(path):
    created_ms = None
    updated_ms = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                line_ms = parse_timestamp_ms(item.get("timestamp"))
                if line_ms is not None:
                    updated_ms = line_ms if updated_ms is None else max(updated_ms, line_ms)
                if item.get("type") == "session_meta" and isinstance(
                    item.get("payload"), dict
                ):
                    created_ms = (
                        parse_timestamp_ms(item["payload"].get("timestamp"))
                        or created_ms
                    )
    except UnicodeDecodeError:
        return None, None
    return created_ms, updated_ms


def patch_session_meta(provider):
    changed_files = 0
    changed_records = 0
    for root in (CODEX_HOME / "sessions", CODEX_HOME / "archived_sessions"):
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            created_ms, updated_ms = read_session_times(path)
            try:
                lines = path.read_text(encoding="utf-8").splitlines(True)
            except UnicodeDecodeError:
                continue
            out = []
            changed = False
            for line in lines:
                raw = line.rstrip("\n")
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    out.append(line)
                    continue
                if item.get("type") == "session_meta" and isinstance(
                    item.get("payload"), dict
                ):
                    if item["payload"].get("model_provider") != provider:
                        item["payload"]["model_provider"] = provider
                        changed = True
                        changed_records += 1
                    out.append(
                        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                else:
                    out.append(line)
            if changed:
                path.write_text("".join(out), encoding="utf-8")
                # Codex can derive sidebar order from file mtimes while rebuilding
                # local state. Keep metadata edits from making old threads look new.
                if updated_ms is not None:
                    atime = path.stat().st_atime
                    os.utime(path, (atime, updated_ms / 1000))
                changed_files += 1
    return changed_files, changed_records


def repair_history_times():
    if not CODEX_DB.exists():
        return 0, 0
    conn = sqlite3.connect(CODEX_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    updated_rows = 0
    touched_files = 0
    try:
        rows = conn.execute(
            "SELECT id, rollout_path, created_at_ms, updated_at_ms FROM threads"
        ).fetchall()
        for row in rows:
            path = Path(row["rollout_path"] or "")
            if not path.exists():
                continue
            created_ms, updated_ms = read_session_times(path)
            if created_ms is None:
                created_ms = int(row["created_at_ms"] or 0) or updated_ms
            if updated_ms is None:
                updated_ms = int(row["updated_at_ms"] or 0) or created_ms
            if not created_ms or not updated_ms:
                continue
            if (
                int(row["created_at_ms"] or 0) != created_ms
                or int(row["updated_at_ms"] or 0) != updated_ms
            ):
                conn.execute(
                    "UPDATE threads SET created_at=?, created_at_ms=?, "
                    "updated_at=?, updated_at_ms=? WHERE id=?",
                    (
                        created_ms // 1000,
                        created_ms,
                        updated_ms // 1000,
                        updated_ms,
                        row["id"],
                    ),
                )
                updated_rows += 1
            current_mtime_ms = int(path.stat().st_mtime * 1000)
            if abs(current_mtime_ms - updated_ms) > 1000:
                os.utime(path, (path.stat().st_atime, updated_ms / 1000))
                touched_files += 1
        conn.commit()
    finally:
        conn.close()
    return updated_rows, touched_files


def rebuild_session_index() -> int:
    if not CODEX_DB.exists():
        return 0
    conn = sqlite3.connect(CODEX_DB)
    try:
        rows = conn.execute(
            """
            SELECT id,
                   COALESCE(NULLIF(title, ''), NULLIF(first_user_message, ''), id) AS thread_name,
                   COALESCE(updated_at_ms, updated_at * 1000, created_at_ms, created_at * 1000) AS updated_ms
            FROM threads
            WHERE archived = 0
            ORDER BY updated_ms ASC, id ASC
            """
        ).fetchall()
    finally:
        conn.close()
    with (CODEX_HOME / "session_index.jsonl").open("w", encoding="utf-8") as f:
        for tid, name, updated_ms in rows:
            updated_at = datetime.fromtimestamp(
                int(updated_ms or 0) / 1000, timezone.utc
            ).isoformat().replace("+00:00", "Z")
            f.write(
                json.dumps(
                    {"id": tid, "thread_name": name, "updated_at": updated_at},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return len(rows)


def main() -> None:
    ccswitch_rows, ccswitch_current_provider = patch_ccswitch_provider_names()
    if ccswitch_current_provider:
        config_updated = patch_current_config_provider(ccswitch_current_provider)
    else:
        config_updated = False
    provider = read_active_provider()
    if current_config_has_reserved_override():
        raise SystemExit(
            "Refusing to run: current config overrides reserved [model_providers.openai]. "
            "Fix the active provider config first."
    )
    db_rows = patch_history_db(provider)
    files, records = patch_session_meta(provider)
    time_rows, touched_files = repair_history_times()
    index_rows = rebuild_session_index()
    print(
        json.dumps(
            {
                "active_provider": provider,
                "ccswitch_providers_updated": ccswitch_rows,
                "config_updated": config_updated,
                "history_rows_updated": db_rows,
                "session_files_updated": files,
                "session_meta_updated": records,
                "time_rows_updated": time_rows,
                "file_mtimes_repaired": touched_files,
                "index_rows": index_rows,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
