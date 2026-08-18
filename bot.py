"""
فایل اصلی - راه‌اندازی ربات تلگرام
اجرا: python bot.py
"""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, TypeHandler, ApplicationHandlerStop
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, AUTO_SCAN_INTERVAL, SIGNAL_PERFORMANCE_CHECK_INTERVAL
import database as db
from scheduler import scan_job, check_signal_performance_job
from handlers.basic import start, help_command
from handlers.analysis import signal_command, chart_command, price_command, top_command, gainers_command
from handlers.watchlist import watch_command, unwatch_command, mywatchlist_command, autoscan_command
from handlers.callbacks import callback_router
from handlers.risk import setrisk_command, myrisk_command, mystats_command
from handlers.admin import (
    admin_help_command, block_command, unblock_command, blocklist_command,
    stats_command, broadcast_command,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def block_check_handler(update: Update, context):
    """
    اجرا قبل از هر هندلر دیگه (group=-1). اگه کاربر مسدود باشه، پیام
    می‌ده و با ApplicationHandlerStop جلوی اجرای بقیه‌ی هندلرها رو
    می‌گیره - یعنی کاربر مسدود حتی نمی‌تونه /start رو هم اجرا کنه.
    """
    user = update.effective_user
    if user is None:
        return
    if await db.is_user_blocked(user.id):
        if update.message:
            await update.message.reply_text("🚫 دسترسی شما به این ربات مسدود شده است.")
        elif update.callback_query:
            await update.callback_query.answer("🚫 دسترسی شما مسدود شده است.", show_alert=True)
        raise ApplicationHandlerStop


async def post_init(app: Application):
    """بعد از راه‌اندازی ربات: دیتابیس رو بساز و زمان‌بندها رو فعال کن"""
    await db.init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", seconds=AUTO_SCAN_INTERVAL, args=[app])
    scheduler.add_job(check_signal_performance_job, "interval", seconds=SIGNAL_PERFORMANCE_CHECK_INTERVAL, args=[app])
    scheduler.start()

    logger.info(
        "ربات آماده‌ست. اسکن واچ‌لیست هر %s ثانیه، پایش عملکرد سیگنال هر %s ثانیه.",
        AUTO_SCAN_INTERVAL, SIGNAL_PERFORMANCE_CHECK_INTERVAL
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! فایل .env رو بساز و توکن رو بذار توش.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # گروه -1 یعنی قبل از همه‌ی هندلرهای دیگه اجرا بشه
    app.add_handler(TypeHandler(Update, block_check_handler), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("chart", chart_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("gainers", gainers_command))
    app.add_handler(CommandHandler("watch", watch_command))
    app.add_handler(CommandHandler("unwatch", unwatch_command))
    app.add_handler(CommandHandler("mywatchlist", mywatchlist_command))
    app.add_handler(CommandHandler("autoscan", autoscan_command))
    app.add_handler(CommandHandler("setrisk", setrisk_command))
    app.add_handler(CommandHandler("myrisk", myrisk_command))
    app.add_handler(CommandHandler("mystats", mystats_command))

    # دستورات ادمین (خودشون داخلاً چک می‌کنن کاربر ادمینه یا نه)
    app.add_handler(CommandHandler("admin", admin_help_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("unblock", unblock_command))
    app.add_handler(CommandHandler("blocklist", blocklist_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    app.add_handler(CallbackQueryHandler(callback_router))

    logger.info("ربات در حال اجراست (polling)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
