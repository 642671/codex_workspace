#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
CODEX_HOME = HOME / ".codex"
DB_PATH = CODEX_HOME / "state_5.sqlite"
INDEX_PATH = CODEX_HOME / "session_index.jsonl"


def file_stats(path_text):
    path = Path(path_text or "")
    try:
        stat = path.stat()
        with path.open("rb") as f:
            lines = sum(1 for _ in f)
        return stat.st_size, lines, stat.st_mtime
    except FileNotFoundError:
        return -1, -1, -1


def find_duplicates(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM threads").fetchall()
    groups = defaultdict(list)
    for row in rows:
        groups[(row["title"], row["first_user_message"], row["created_at"])].append(row)

    report = []
    remove_rows = []
    for key, group_rows in groups.items():
        if len(group_rows) <= 1:
            continue
        enriched = []
        for row in group_rows:
            size, lines, mtime = file_stats(row["rollout_path"])
            enriched.append((row, size, lines, mtime))
        keeper = max(
            enriched,
            key=lambda x: (
                x[2],
                x[1],
                x[0]["updated_at"],
                x[0]["created_at"],
                x[3],
                x[0]["id"],
            ),
        )
        removed = [x for x in enriched if x[0]["id"] != keeper[0]["id"]]
        remove_rows.extend(x[0] for x in removed)
        report.append(
            {
                "duplicate_count": len(group_rows),
                "removed_count": len(removed),
                "keep_id": keeper[0]["id"],
                "keep_rollout_path": keeper[0]["rollout_path"],
                "title_preview": (key[0] or "")[:200],
                "removed": [
                    {
                        "id": row["id"],
                        "rollout_path": row["rollout_path"],
                        "lines": lines,
                        "size": size,
                    }
                    for row, size, lines, _ in removed
                ],
            }
        )
    return report, remove_rows


def rebuild_session_index(conn):
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
    with INDEX_PATH.open("w", encoding="utf-8") as f:
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


def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate Codex local history entries created by copy/shadow sync attempts."
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the plan.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Missing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout=5000")
    report, remove_rows = find_duplicates(conn)
    remove_ids = [row["id"] for row in remove_rows]

    if args.dry_run:
        print(
            json.dumps(
                {
                    "duplicate_groups": len(report),
                    "removable_threads": len(remove_ids),
                    "groups": report,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        conn.close()
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = CODEX_HOME / "unified-history" / "backups" / f"dedupe-{stamp}"
    removed_files_dir = backup_dir / "removed-session-files"
    orphan_files_dir = backup_dir / "orphan-session-files"
    backup_dir.mkdir(parents=True, exist_ok=True)
    removed_files_dir.mkdir(parents=True, exist_ok=True)
    orphan_files_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(DB_PATH, backup_dir / "state_5.sqlite.before-dedupe")
    if INDEX_PATH.exists():
        shutil.copy2(INDEX_PATH, backup_dir / "session_index.jsonl.before-dedupe")

    if remove_ids:
        qmarks = ",".join("?" for _ in remove_ids)
        conn.execute(f"DELETE FROM thread_dynamic_tools WHERE thread_id IN ({qmarks})", remove_ids)
        conn.execute(f"DELETE FROM thread_spawn_edges WHERE child_thread_id IN ({qmarks})", remove_ids)
        conn.execute(f"DELETE FROM thread_spawn_edges WHERE parent_thread_id IN ({qmarks})", remove_ids)
        conn.execute(f"DELETE FROM agent_job_items WHERE assigned_thread_id IN ({qmarks})", remove_ids)
        conn.execute(f"DELETE FROM threads WHERE id IN ({qmarks})", remove_ids)
        conn.commit()

    moved = []
    for row in remove_rows:
        src = Path(row["rollout_path"] or "")
        if not src.exists():
            continue
        try:
            rel = src.relative_to(CODEX_HOME)
        except ValueError:
            rel = Path(src.name)
        dest = removed_files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(dest.stem + f".{row['id']}" + dest.suffix)
        shutil.move(str(src), str(dest))
        moved.append({"id": row["id"], "from": str(src), "to": str(dest)})

    active_paths = {
        Path(row[0]).resolve()
        for row in conn.execute("SELECT rollout_path FROM threads")
        if row[0]
    }
    orphans = []
    for root_name in ("sessions", "archived_sessions"):
        root = CODEX_HOME / root_name
        if not root.exists():
            continue
        for src in sorted(root.rglob("*.jsonl")):
            if src.resolve() in active_paths:
                continue
            rel = src.relative_to(CODEX_HOME)
            dest = orphan_files_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            orphans.append({"from": str(src), "to": str(dest)})

    index_rows = rebuild_session_index(conn)
    conn.close()

    result = {
        "backup_dir": str(backup_dir),
        "duplicate_groups": len(report),
        "removed_threads": len(remove_ids),
        "moved_duplicate_files": len(moved),
        "moved_orphan_files": len(orphans),
        "remaining_index_rows": index_rows,
        "groups": report,
        "moved": moved,
        "orphans": orphans,
    }
    (backup_dir / "dedupe-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
