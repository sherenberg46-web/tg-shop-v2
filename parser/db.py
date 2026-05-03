"""Async SQLite helpers for the parser (connects to the same DB as the backend)."""
import aiosqlite
from parser.config import DB_PATH


async def get_connection() -> aiosqlite.Connection:
    """Open and return a connection to the shop database."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    # Migrations — safe to run each time (ALTER TABLE is no-op if column exists)
    for _sql in [
        "ALTER TABLE products ADD COLUMN task_type TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN genre TEXT",
        "ALTER TABLE products ADD COLUMN requires_ps_plus INTEGER DEFAULT 0",
    ]:
        try:
            await conn.execute(_sql)
            await conn.commit()
        except Exception:
            pass  # column already exists
    return conn


async def ensure_categories(conn: aiosqlite.Connection) -> dict[str, int]:
    """Ensure all store categories exist; return {slug: id} map."""
    from parser.config import STORE_CATEGORIES
    for slug, name in STORE_CATEGORIES:
        await conn.execute(
            "INSERT OR IGNORE INTO categories (slug, name) VALUES (?, ?)",
            (slug, name),
        )
    await conn.commit()
    cat: dict[str, int] = {}
    async with conn.execute("SELECT id, slug FROM categories") as cur:
        async for row in cur:
            cat[row["slug"]] = row["id"]
    return cat


async def log_start(conn: aiosqlite.Connection, region: str, task_type: str) -> int:
    """Insert a parser_log row and return its id."""
    cur = await conn.execute(
        "INSERT INTO parser_log (region, task_type, status) VALUES (?, ?, 'running')",
        (region, task_type),
    )
    await conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


async def log_finish(
    conn: aiosqlite.Connection,
    log_id: int,
    *,
    status: str = "done",
    added: int = 0,
    updated: int = 0,
    errors: int = 0,
    details: str = "",
) -> None:
    """Update the parser_log row with final stats."""
    await conn.execute(
        """UPDATE parser_log
           SET finished_at = CURRENT_TIMESTAMP, status = ?,
               products_added = ?, products_updated = ?,
               errors_count = ?, details = ?
           WHERE id = ?""",
        (status, added, updated, errors, details, log_id),
    )
    await conn.commit()
