"""
فایل اصلی - راه‌اندازی ربات تلگرام
اجرا: python bot.py
"""
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, AUTO_SCAN_INTERVAL
import database as db
from scheduler import scan_job
from handlers.basic import start, help_command
from handlers.analysis import signal_command, chart_command, price_command, top_command, gainers_command
from handlers.watchlist import watch_command, unwatch_command, mywatchlist_command, autoscan_command
from handlers.callbacks import callback_router

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    """بعد از راه‌اندازی ربات: دیتابیس رو بساز و زمان‌بند رو فعال کن"""
    await db.init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", seconds=AUTO_SCAN_INTERVAL, args=[app])
    scheduler.start()

    logger.info("ربات آماده‌ست. اسکن خودکار هر %s ثانیه اجرا می‌شه.", AUTO_SCAN_INTERVAL)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! فایل .env رو بساز و توکن رو بذار توش.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

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
    app.add_handler(CallbackQueryHandler(callback_router))

    logger.info("ربات در حال اجراست (polling)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
