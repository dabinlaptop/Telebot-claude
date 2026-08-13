"""
لایه دیتابیس - مدیریت کاربران، واچ‌لیست و تاریخچه سیگنال‌ها
از aiosqlite استفاده می‌کنیم چون ربات async هست
"""
import aiosqlite
from datetime import datetime
from config import DB_PATH


async def init_db():
    """ساخت جداول در صورت عدم وجود"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TEXT,
                auto_scan_enabled INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                added_at TEXT,
                UNIQUE(user_id, symbol)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                signal_type TEXT,
                score INTEGER,
                price REAL,
                created_at TEXT
            )
        """)
        await db.commit()


async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?, ?, ?)",
            (user_id, username, datetime.utcnow().isoformat())
        )
        await db.commit()


async def add_to_watchlist(user_id: int, symbol: str) -> bool:
    """برمی‌گردونه True اگه با موفقیت اضافه شد"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO watchlist (user_id, symbol, added_at) VALUES (?, ?, ?)",
                (user_id, symbol, datetime.utcnow().isoformat())
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False  # از قبل توی لیست بوده


async def remove_from_watchlist(user_id: int, symbol: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (user_id, symbol)
        )
        await db.commit()


async def get_watchlist(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT symbol FROM watchlist WHERE user_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def get_watchlist_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_active_watch_pairs() -> list[tuple[int, str]]:
    """همه‌ی جفت (user_id, symbol) کاربرانی که auto_scan فعاله"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT w.user_id, w.symbol
            FROM watchlist w
            JOIN users u ON u.user_id = w.user_id
            WHERE u.auto_scan_enabled = 1
        """)
        return await cursor.fetchall()


async def set_auto_scan(user_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET auto_scan_enabled = ? WHERE user_id = ?",
            (1 if enabled else 0, user_id)
        )
        await db.commit()


async def log_signal(symbol: str, signal_type: str, score: int, price: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO signal_history (symbol, signal_type, score, price, created_at) VALUES (?, ?, ?, ?, ?)",
            (symbol, signal_type, score, price, datetime.utcnow().isoformat())
        )
        await db.commit()


async def get_last_signal(symbol: str) -> dict | None:
    """آخرین سیگنال ثبت‌شده برای یه نماد - برای جلوگیری از اسپم سیگنال تکراری"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT signal_type, score, created_at FROM signal_history WHERE symbol = ? ORDER BY id DESC LIMIT 1",
            (symbol,)
        )
        row = await cursor.fetchone()
        if row:
            return {"signal_type": row[0], "score": row[1], "created_at": row[2]}
        return None
