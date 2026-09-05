"""
تحلیل فراداده (Meta-Analytics)

هیچ داده‌ی جدیدی لازم نداره - از روی همون سیگنال‌هایی که قبلاً از
/signal گرفته شدن و به نتیجه رسیدن (TP/SL/سربه‌سر)، الگو استخراج
می‌کنه: کدوم تایم‌فریم بهتر جواب داده، کدوم نماد، کدوم روز هفته.

منطق برد/باخت دقیقاً هماهنگ با /mystats هست: TP1/TP2/TP3 برد، SL باخت،
سربه‌سر نه برد حساب می‌شه نه باخت (فقط جدا نمایش داده می‌شه).
"""
from collections import defaultdict
from datetime import datetime
import database as db

MIN_SAMPLES_FOR_CONFIDENCE = 5  # کمتر از این تعداد، نتیجه‌گیری آماری قابل‌اتکا نیست

WEEKDAY_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def _classify(status: str) -> str:
    if status == "SL_HIT":
        return "loss"
    if status == "BREAKEVEN_HIT":
        return "breakeven"
    return "win"  # TP1_HIT / TP2_HIT / TP3_HIT


def _group_stats(rows: list, key_func) -> list[dict]:
    """گروه‌بندی سیگنال‌های به‌نتیجه‌رسیده بر اساس یه کلید دلخواه (تایم‌فریم، نماد، روز هفته، ...)"""
    groups = defaultdict(lambda: {"win": 0, "loss": 0, "breakeven": 0})
    for row in rows:
        key = key_func(row)
        groups[key][_classify(row["status"])] += 1

    result = []
    for key, counts in groups.items():
        decided = counts["win"] + counts["loss"]  # سربه‌سر جزو تصمیم‌گیری برد/باخت حساب نمی‌شه
        total = decided + counts["breakeven"]
        win_rate = (counts["win"] / decided * 100) if decided > 0 else None
        result.append({
            "key": key,
            "wins": counts["win"],
            "losses": counts["loss"],
            "breakeven": counts["breakeven"],
            "total": total,
            "win_rate": win_rate,
            "low_sample": decided < MIN_SAMPLES_FOR_CONFIDENCE,
        })
    return result


async def analyze_by_timeframe(user_id: int = None) -> list[dict]:
    rows = await db.get_resolved_signals(user_id)
    stats = _group_stats(rows, lambda r: r["timeframe"])
    return sorted(stats, key=lambda s: s["total"], reverse=True)


async def analyze_by_symbol(user_id: int = None) -> list[dict]:
    rows = await db.get_resolved_signals(user_id)
    stats = _group_stats(rows, lambda r: r["symbol"])
    return sorted(stats, key=lambda s: s["total"], reverse=True)


async def analyze_by_weekday(user_id: int = None) -> list[dict]:
    rows = await db.get_resolved_signals(user_id)

    def weekday_key(r):
        dt = datetime.fromisoformat(r["created_at"])
        return WEEKDAY_FA[dt.weekday()]

    stats = _group_stats(rows, weekday_key)
    order = {day: i for i, day in enumerate(WEEKDAY_FA)}
    return sorted(stats, key=lambda s: order.get(s["key"], 99))


async def analyze_by_direction(user_id: int = None) -> list[dict]:
    """آیا سیگنال‌های خرید بهتر جواب دادن یا فروش؟"""
    rows = await db.get_resolved_signals(user_id)
    stats = _group_stats(rows, lambda r: r["direction"])
    return sorted(stats, key=lambda s: s["total"], reverse=True)


async def get_total_resolved_count(user_id: int = None) -> int:
    rows = await db.get_resolved_signals(user_id)
    return len(rows)
