"""
اسکن خودکار واچ‌لیست کاربران در پس‌زمینه
هر SCAN_INTERVAL ثانیه، همه‌ی نمادهای واچ‌شده تحلیل می‌شن و اگه سیگنال
نسبت به آخرین باری که ثبت شده تغییر کرده باشه (و NEUTRAL نباشه)، به
کاربرانی که اون نماد رو واچ کردن و autoscan فعاله پیام می‌فرسته.
"""
import logging
from collections import defaultdict
from telegram.ext import Application
from telegram.constants import ParseMode
from exchange import ExchangeClient
from signals import analyze_symbol, SIGNAL_EMOJI, SIGNAL_FA
import database as db
import backup

logger = logging.getLogger(__name__)


async def scan_job(app: Application):
    logger.info("شروع اسکن خودکار واچ‌لیست‌ها...")
    pairs = await db.get_all_active_watch_pairs()  # [(user_id, symbol), ...]
    if not pairs:
        return

    symbol_to_users = defaultdict(list)
    for user_id, symbol in pairs:
        symbol_to_users[symbol].append(user_id)

    client = ExchangeClient()
    try:
        for symbol, user_ids in symbol_to_users.items():
            try:
                result = await analyze_symbol(client, symbol)
            except Exception as e:
                logger.warning(f"خطا در تحلیل {symbol}: {e}")
                continue

            last = await db.get_last_signal(symbol)
            should_notify = (
                result.signal_type != "NEUTRAL"
                and (last is None or last["signal_type"] != result.signal_type)
            )

            await db.log_signal(symbol, result.signal_type, result.total_score, result.current_price)

            if not should_notify:
                continue

            emoji = SIGNAL_EMOJI[result.signal_type]
            text = (
                f"{emoji} *هشدار سیگنال جدید*\n\n"
                f"نماد: `{symbol}`\n"
                f"قیمت: `{result.current_price:,.4f}`\n"
                f"سیگنال: *{SIGNAL_FA[result.signal_type]}*\n"
                f"امتیاز: `{result.total_score}`/`{result.max_possible_score}`\n\n"
                f"⚠️ توصیه مالی نیست."
            )
            for user_id in user_ids:
                try:
                    await app.bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.warning(f"ارسال پیام به {user_id} ناموفق بود: {e}")
    finally:
        await client.close()
    logger.info("اسکن خودکار تمام شد.")


async def check_signal_performance_job(app: Application):
    """
    هر سیگنال بازی که از /signal صادر شده رو با قیمت لحظه‌ای مقایسه
    می‌کنه؛ اگه به سطح جدیدی (TP1/TP2/TP3/SL) نسبت به آخرین وضعیت
    ثبت‌شده رسیده باشه، وضعیتش رو به‌روز و به کاربر خبر می‌ده. فقط
    TP3، SL و BREAKEVEN نهایی‌ان (سیگنال می‌بنده)؛ TP1/TP2 سیگنال رو
    باز نگه می‌دارن چون ممکنه به سطح بعدی هم برسه.

    بعد از رسیدن به TP1 (اولین‌بار)، اگه BREAKEVEN_AFTER_TP1 فعال باشه،
    حد ضرر خودکار به نقطه‌ی ورود (سربه‌سر) منتقل می‌شه - یعنی از اون
    لحظه به بعد، این معامله دیگه نمی‌تونه ضرر واقعی بده؛ اگه بعداً به
    همون SL جدید (=entry) برخورد کنه، به‌جای SL_HIT، BREAKEVEN_HIT ثبت
    می‌شه (نه برد نه باخت).
    """
    from config import MAX_OPEN_SIGNALS_PER_CHECK, BREAKEVEN_AFTER_TP1

    logger.info("شروع پایش عملکرد سیگنال‌های باز...")
    open_signals = await db.get_open_signal_performances(limit=MAX_OPEN_SIGNALS_PER_CHECK)
    if not open_signals:
        return

    symbols = {s["symbol"] for s in open_signals}
    client = ExchangeClient()
    prices = {}
    try:
        for symbol in symbols:
            try:
                prices[symbol] = await client.fetch_ticker_price(symbol)
            except Exception as e:
                logger.warning(f"دریافت قیمت {symbol} ناموفق بود: {e}")
    finally:
        await client.close()

    status_order = {"OPEN": 0, "TP1_HIT": 1, "TP2_HIT": 2, "TP3_HIT": 3}

    for sig in open_signals:
        price = prices.get(sig["symbol"])
        if price is None:
            continue

        is_breakeven_sl = sig["sl"] is not None and abs(sig["sl"] - sig["entry"]) < 1e-9

        candidate_status = None
        if sig["direction"] == "BUY":
            if sig["sl"] and price <= sig["sl"]:
                candidate_status = "BREAKEVEN_HIT" if is_breakeven_sl else "SL_HIT"
            elif sig["tp3"] and price >= sig["tp3"]:
                candidate_status = "TP3_HIT"
            elif sig["tp2"] and price >= sig["tp2"]:
                candidate_status = "TP2_HIT"
            elif sig["tp1"] and price >= sig["tp1"]:
                candidate_status = "TP1_HIT"
        elif sig["direction"] == "SELL":
            if sig["sl"] and price >= sig["sl"]:
                candidate_status = "BREAKEVEN_HIT" if is_breakeven_sl else "SL_HIT"
            elif sig["tp3"] and price <= sig["tp3"]:
                candidate_status = "TP3_HIT"
            elif sig["tp2"] and price <= sig["tp2"]:
                candidate_status = "TP2_HIT"
            elif sig["tp1"] and price <= sig["tp1"]:
                candidate_status = "TP1_HIT"

        if not candidate_status or candidate_status == sig["status"]:
            continue  # هیچ پیشرفت جدیدی نسبت به آخرین باری که چک شده نیست

        # SL/BREAKEVEN همیشه یعنی وضعیت تغییر کرده (مگر از قبل همون بوده که بالا رد شد)
        is_progress = (
            candidate_status in ("SL_HIT", "BREAKEVEN_HIT")
            or status_order.get(candidate_status, 0) > status_order.get(sig["status"], 0)
        )
        if not is_progress:
            continue

        should_close = candidate_status in ("TP3_HIT", "SL_HIT", "BREAKEVEN_HIT")
        if should_close:
            await db.close_signal_performance(sig["id"], candidate_status)
        else:
            await db.update_signal_status(sig["id"], candidate_status)

        breakeven_note = ""
        if candidate_status == "TP1_HIT" and BREAKEVEN_AFTER_TP1:
            await db.move_sl_to_breakeven(sig["id"], sig["entry"])
            breakeven_note = "\n\n🛡 حد ضرر خودکار به نقطه‌ی سربه‌سر (Break-even) منتقل شد - از الان این معامله دیگه نمی‌تونه ضرر واقعی بده."

        emoji = {"TP1_HIT": "🎯", "TP2_HIT": "🎯", "TP3_HIT": "🎯",
                 "SL_HIT": "🛑", "BREAKEVEN_HIT": "🛡"}[candidate_status]
        status_fa = {
            "TP1_HIT": "به TP1 رسید", "TP2_HIT": "به TP2 رسید",
            "TP3_HIT": "به TP3 رسید (سیگنال بسته شد ✅)",
            "SL_HIT": "به حد ضرر خورد (سیگنال بسته شد ❌)",
            "BREAKEVEN_HIT": "بعد از رسیدن به TP1، به نقطه‌ی سربه‌سر برگشت (سیگنال بدون سود/ضرر بسته شد ⚪️)",
        }[candidate_status]
        try:
            await app.bot.send_message(
                chat_id=sig["user_id"],
                text=(
                    f"{emoji} *بروزرسانی سیگنال {sig['symbol']}* ({sig['timeframe']})\n"
                    f"وضعیت: {status_fa}\n"
                    f"قیمت فعلی: `{price:,.4f}`\n"
                    f"ورود: `{sig['entry']:,.4f}`"
                    f"{breakeven_note}\n\n"
                    f"برای دیدن آمار کلی: /mystats"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"ارسال بروزرسانی عملکرد به {sig['user_id']} ناموفق بود: {e}")

    logger.info("پایش عملکرد سیگنال‌ها تمام شد.")


async def backup_job(app: Application):
    """
    بکاپ خودکار دوره‌ای دیتابیس. اگه موفق بود چیزی به کسی اطلاع
    نمی‌ده (تا اسپم نشه)؛ ولی اگه شکست بخوره، به همه‌ی ادمین‌ها خبر
    می‌ده - چون شکست مکرر بکاپ یعنی موقع نیاز واقعی (خرابی دیسک، حذف
    اشتباهی و...) داده‌ای برای بازگردانی وجود نداره.
    """
    from config import ADMIN_IDS

    try:
        path = await backup.create_backup()
        logger.info(f"بکاپ خودکار دوره‌ای موفق: {path}")
    except Exception as e:
        logger.error(f"بکاپ خودکار دوره‌ای ناموفق بود: {e}")
        for admin_id in ADMIN_IDS:
            try:
                await app.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ بکاپ خودکار دیتابیس ناموفق بود:\n`{e}`\n\nلطفاً وضعیت دیسک/فضای ذخیره‌سازی رو چک کن.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
