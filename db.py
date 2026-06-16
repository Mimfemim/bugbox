from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

ALLOWED_STATUSES: tuple[str, ...] = (
    "NEW",
    "TRIAGED",
    "IN_PROGRESS",
    "FIXED",
    "CLOSED",
)

OPEN_STATUSES: tuple[str, ...] = ("NEW", "TRIAGED", "IN_PROGRESS")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER,
    reporter_name TEXT,
    raw_text TEXT,
    media_type TEXT,
    telegram_file_id TEXT,
    ai_title TEXT,
    ai_summary TEXT,
    category TEXT,
    severity TEXT,
    priority TEXT,
    device TEXT,
    reproducibility TEXT,
    suggested_owner TEXT,
    status TEXT,
    ai_status TEXT DEFAULT 'PENDING',
    created_at TEXT,
    updated_at TEXT
);
"""

INSERT_SQL = """
INSERT INTO bugs (
    reporter_id, reporter_name, raw_text, media_type, telegram_file_id,
    ai_title, ai_summary, category, severity, priority, device,
    reproducibility, suggested_owner, status, ai_status, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

CREATE_ADMINS_SQL = """
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    added_by INTEGER,
    added_at TEXT
);
"""


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(CREATE_TABLE_SQL)
            cursor = await conn.execute("PRAGMA table_info(bugs)")
            columns = {row[1] for row in await cursor.fetchall()}
            if "ai_status" not in columns:
                await conn.execute(
                    "ALTER TABLE bugs ADD COLUMN ai_status TEXT DEFAULT 'PENDING'"
                )
            await conn.execute(CREATE_ADMINS_SQL)
            await conn.commit()

    async def insert_bug(
        self,
        *,
        reporter_id: Optional[int],
        reporter_name: str,
        raw_text: str,
        media_type: Optional[str],
        telegram_file_id: Optional[str],
        analysis: dict[str, Any],
        ai_status: str = "PENDING",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                INSERT_SQL,
                (
                    reporter_id,
                    reporter_name,
                    raw_text,
                    media_type,
                    telegram_file_id,
                    analysis.get("title"),
                    analysis.get("summary"),
                    analysis.get("category"),
                    analysis.get("severity"),
                    analysis.get("priority"),
                    analysis.get("device"),
                    analysis.get("reproducibility"),
                    analysis.get("suggested_owner"),
                    analysis.get("status", "NEW"),
                    ai_status,
                    now,
                    now,
                ),
            )
            await conn.commit()
            return cursor.lastrowid or 0

    async def update_analysis(
        self, bug_id: int, analysis: dict[str, Any], ai_status: str = "ANALYZED"
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                UPDATE bugs SET
                    ai_title = ?, ai_summary = ?, category = ?, severity = ?,
                    priority = ?, device = ?, reproducibility = ?,
                    suggested_owner = ?, ai_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    analysis.get("title"),
                    analysis.get("summary"),
                    analysis.get("category"),
                    analysis.get("severity"),
                    analysis.get("priority"),
                    analysis.get("device"),
                    analysis.get("reproducibility"),
                    analysis.get("suggested_owner"),
                    ai_status,
                    now,
                    bug_id,
                ),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def list_pending(self, limit: int = 200) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM bugs WHERE ai_status = 'PENDING' ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def count_pending(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM bugs WHERE ai_status = 'PENDING'"
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def update_status(self, bug_id: int, status: str) -> bool:
        if status not in ALLOWED_STATUSES:
            return False
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "UPDATE bugs SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, bug_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def delete_bug(self, bug_id: int) -> bool:
        """Permanently remove a bug report (super-admin cleanup)."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM bugs WHERE id = ?", (bug_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ----- Admin management --------------------------------------------------

    async def add_admin(
        self, user_id: int, name: str = "", added_by: int = 0
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO admins (user_id, name, added_by, added_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, name, added_by, now),
            )
            await conn.commit()

    async def remove_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM admins WHERE user_id = ?", (user_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def is_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
            )
            return await cursor.fetchone() is not None

    async def list_admins(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM admins ORDER BY added_at ASC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ----- Backup ------------------------------------------------------------

    async def backup_to(self, dest_path: str) -> None:
        """Create a consistent snapshot of the live DB using SQLite's online
        backup API (safe even while the bot is writing)."""
        async with aiosqlite.connect(self.db_path) as src:
            async with aiosqlite.connect(dest_path) as dst:
                await src.backup(dst)

    async def get_bug(self, bug_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM bugs WHERE id = ?", (bug_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_latest(self, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM bugs ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def list_by_severity(
        self, severity: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM bugs WHERE severity = ? ORDER BY id DESC LIMIT ?",
                (severity, limit),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def list_all(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM bugs ORDER BY id ASC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM bugs")
            total_row = await cursor.fetchone()
            total = int(total_row[0]) if total_row else 0

            placeholders = ",".join("?" * len(OPEN_STATUSES))
            cursor = await conn.execute(
                f"SELECT COUNT(*) FROM bugs WHERE status IN ({placeholders})",
                OPEN_STATUSES,
            )
            open_row = await cursor.fetchone()
            open_count = int(open_row[0]) if open_row else 0

            sev_counts: dict[str, int] = {
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0,
            }
            cursor = await conn.execute(
                "SELECT severity, COUNT(*) FROM bugs GROUP BY severity"
            )
            for sev, cnt in await cursor.fetchall():
                if sev in sev_counts:
                    sev_counts[sev] = int(cnt)

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM bugs WHERE ai_status = 'PENDING'"
            )
            pending_row = await cursor.fetchone()
            pending = int(pending_row[0]) if pending_row else 0

            return {
                "total": total,
                "open": open_count,
                "pending": pending,
                **sev_counts,
            }
