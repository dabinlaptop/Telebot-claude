"""
لایه دیتابیس - مدیریت کاربران، واچ‌لیست و تاریخچه سیگنال‌ها
از aiosqlite استفاده می‌کنیم چون ربات async هست
"""
import aiosqlite
from datetime import datetime, timedelta
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
        # کاربران مسدودشده توسط ادمین
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                blocked_at TEXT
            )
        """)
        # تنظیمات مدیریت ریسک هر کاربر (برای محاسبه‌ی خودکار حجم پوزیشن)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_risk_settings (
                user_id INTEGER PRIMARY KEY,
                account_balance REAL,
                risk_percent REAL,
                updated_at TEXT
            )
        """)
        # پایش عملکرد سیگنال‌های صادرشده از موتور تک‌تایم‌فریمی (برای /mystats)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signal_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                entry REAL,
                sl REAL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                status TEXT DEFAULT 'OPEN',
                created_at TEXT,
                closed_at TEXT
            )
        """)
        # سیگنال‌هایی که منتظر تاییدیه‌ی کاربرن (بله/خیر پیگیری شه)؛ بعد
        # از پاسخ کاربر، یا به signal_performance منتقل می‌شن یا حذف می‌شن
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                timeframe TEXT,
                direction TEXT,
                entry REAL,
                sl REAL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                created_at TEXT
            )
        """)
        # تنظیمات سراسری ربات (خوانده و نوشته‌شده هم از پنل وب، هم از کد)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
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


# ==================== مدیریت کاربران مسدود (پنل ادمین) ====================

async def block_user(user_id: int, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at) VALUES (?, ?, ?)",
            (user_id, reason, datetime.utcnow().isoformat())
        )
        await db.commit()


async def unblock_user(user_id: int) -> bool:
    """برمی‌گردونه True اگه واقعاً مسدود بوده و حذف شد"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
        existed = await cursor.fetchone() is not None
        await db.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        await db.commit()
        return existed


async def is_user_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None


async def get_blocked_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, reason, blocked_at FROM blocked_users ORDER BY blocked_at DESC"
        )
        rows = await cursor.fetchall()
        return [{"user_id": r[0], "reason": r[1], "blocked_at": r[2]} for r in rows]


# ==================== آمار کلی ربات (پنل ادمین) ====================

async def get_bot_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active_autoscan = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE auto_scan_enabled = 1"
        )).fetchone())[0]
        total_watchlist = (await (await db.execute("SELECT COUNT(*) FROM watchlist")).fetchone())[0]
        total_blocked = (await (await db.execute("SELECT COUNT(*) FROM blocked_users")).fetchone())[0]
        today = datetime.utcnow().strftime("%Y-%m-%d")
        signals_today = (await (await db.execute(
            "SELECT COUNT(*) FROM signal_history WHERE created_at LIKE ?", (f"{today}%",)
        )).fetchone())[0]
        return {
            "total_users": total_users,
            "active_autoscan": active_autoscan,
            "total_watchlist": total_watchlist,
            "total_blocked": total_blocked,
            "signals_today": signals_today,
        }


async def get_all_user_ids() -> list[int]:
    """برای ارسال پیام همگانی (broadcast)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


# ==================== تنظیمات مدیریت ریسک هر کاربر ====================

async def set_user_risk(user_id: int, account_balance: float, risk_percent: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO user_risk_settings (user_id, account_balance, risk_percent, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   account_balance=excluded.account_balance,
                   risk_percent=excluded.risk_percent,
                   updated_at=excluded.updated_at""",
            (user_id, account_balance, risk_percent, datetime.utcnow().isoformat())
        )
        await db.commit()


async def get_user_risk(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT account_balance, risk_percent FROM user_risk_settings WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"account_balance": row[0], "risk_percent": row[1]}
        return None


# ==================== پایش عملکرد سیگنال‌ها ====================

async def record_signal_performance(user_id: int, symbol: str, timeframe: str, direction: str,
                                     entry: float, sl: float, tps: list) -> int:
    """ثبت یه سیگنال تازه‌صادرشده برای پایش بعدی؛ آی‌دی ردیف رو برمی‌گردونه"""
    tp1 = tps[0] if len(tps) > 0 else None
    tp2 = tps[1] if len(tps) > 1 else None
    tp3 = tps[2] if len(tps) > 2 else None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO signal_performance
               (user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)""",
            (user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, datetime.utcnow().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_open_signal_performances(limit: int = 200) -> list[dict]:
    """
    سیگنال‌هایی که هنوز به وضعیت نهایی (TP3 یا SL) نرسیدن - شامل سیگنال‌های
    OPEN و همچنین اون‌هایی که فقط TP1/TP2 خوردن (چون هنوز ممکنه به سطح
    بعدی برسن یا برگردن بخورن به SL، پس باید همچنان پایش بشن)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, status
               FROM signal_performance
               WHERE status NOT IN ('TP3_HIT', 'SL_HIT')
               ORDER BY id ASC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        cols = ["id", "user_id", "symbol", "timeframe", "direction", "entry", "sl", "tp1", "tp2", "tp3", "status"]
        return [dict(zip(cols, r)) for r in rows]


async def close_signal_performance(perf_id: int, status: str):
    """برای وضعیت‌های نهایی (TP3_HIT یا SL_HIT) - closed_at رو هم ثبت می‌کنه"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE signal_performance SET status = ?, closed_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), perf_id)
        )
        await db.commit()


async def update_signal_status(perf_id: int, status: str):
    """برای وضعیت‌های میانی (TP1_HIT/TP2_HIT) - سیگنال هنوز باز می‌مونه، closed_at خالی می‌مونه"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE signal_performance SET status = ? WHERE id = ?",
            (status, perf_id)
        )
        await db.commit()


async def get_user_performance_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT status, COUNT(*) FROM signal_performance WHERE user_id = ? GROUP BY status",
            (user_id,)
        )
        rows = await cursor.fetchall()
        counts = {status: count for status, count in rows}
        wins = counts.get("TP1_HIT", 0) + counts.get("TP2_HIT", 0) + counts.get("TP3_HIT", 0)
        losses = counts.get("SL_HIT", 0)
        open_count = counts.get("OPEN", 0)
        closed = wins + losses
        win_rate = (wins / closed * 100) if closed > 0 else None
        return {
            "wins": wins, "losses": losses, "open": open_count,
            "closed": closed, "win_rate": win_rate, "breakdown": counts,
        }


async def get_user_open_signals(user_id: int) -> list[dict]:
    """لیست سیگنال‌های فعال (باز یا TP1/TP2 خورده) این کاربر - برای /mysignals"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, status, created_at
               FROM signal_performance
               WHERE user_id = ? AND status NOT IN ('TP3_HIT', 'SL_HIT')
               ORDER BY id DESC""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        cols = ["id", "symbol", "timeframe", "direction", "entry", "sl", "tp1", "tp2", "tp3", "status", "created_at"]
        return [dict(zip(cols, r)) for r in rows]


async def delete_signal_performance(perf_id: int, user_id: int) -> bool:
    """حذف دستی یه سیگنال از پایش - فقط اگه واقعاً مال همون کاربر باشه. برمی‌گردونه True اگه حذف شد."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM signal_performance WHERE id = ? AND user_id = ?", (perf_id, user_id)
        )
        exists = await cursor.fetchone() is not None
        if not exists:
            return False
        await db.execute("DELETE FROM signal_performance WHERE id = ? AND user_id = ?", (perf_id, user_id))
        await db.commit()
        return True


# ==================== سیگنال‌های در انتظار تاییدیه‌ی کاربر ====================

async def create_pending_signal(user_id: int, symbol: str, timeframe: str, direction: str,
                                 entry: float, sl: float, tps: list) -> int:
    """
    قبل از ثبت قطعی یه سیگنال برای پایش، اول اینجا به‌صورت موقت ذخیره
    می‌شه تا از کاربر تاییدیه گرفته بشه. آی‌دی ردیف رو برمی‌گردونه.
    """
    tp1 = tps[0] if len(tps) > 0 else None
    tp2 = tps[1] if len(tps) > 1 else None
    tp3 = tps[2] if len(tps) > 2 else None
    async with aiosqlite.connect(DB_PATH) as db:
        # پاکسازی سبک: pending‌های قدیمی همین کاربر (بیش از ۲۴ ساعت، یعنی
        # جواب نداده) رو حذف کن تا جدول بی‌دلیل بزرگ نشه. مقایسه رو با
        # timestamp پایتونی انجام می‌دیم (نه توابع تاریخ SQLite) چون
        # فرمت isoformat پایتون با فرمت پیش‌فرض datetime() در SQLite یکی نیست.
        cutoff = (datetime.utcnow() - timedelta(days=1)).isoformat()
        await db.execute(
            "DELETE FROM pending_signals WHERE user_id = ? AND created_at < ?",
            (user_id, cutoff)
        )
        cursor = await db.execute(
            """INSERT INTO pending_signals
               (user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3, datetime.utcnow().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_signal(pending_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, user_id, symbol, timeframe, direction, entry, sl, tp1, tp2, tp3
               FROM pending_signals WHERE id = ?""",
            (pending_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        cols = ["id", "user_id", "symbol", "timeframe", "direction", "entry", "sl", "tp1", "tp2", "tp3"]
        return dict(zip(cols, row))


async def delete_pending_signal(pending_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_signals WHERE id = ?", (pending_id,))
        await db.commit()


# ==================== تنظیمات سراسری (خوانده‌شده هم توسط ربات، هم پنل وب) ====================

async def get_setting(key: str, default: str = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO bot_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, str(value))
        )
        await db.commit()


async def get_all_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT key, value FROM bot_settings")
        rows = await cursor.fetchall()
        return {k: v for k, v in rows}


async def get_int_setting(key: str, default: int) -> int:
    val = await get_setting(key)
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


async def get_float_setting(key: str, default: float) -> float:
    val = await get_setting(key)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default
