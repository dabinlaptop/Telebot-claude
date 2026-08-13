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
