"""
فایل اصلی - راه‌اندازی ربات تلگرام + پنل وب (هم‌زمان، توی یه پروسه)
اجرا: python bot.py
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, TypeHandler, ApplicationHandlerStop

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    BOT_TOKEN, AUTO_SCAN_INTERVAL, SIGNAL_PERFORMANCE_CHECK_INTERVAL,
    WEB_PANEL_ENABLED, WEB_PANEL_PORT, ADMIN_IDS, BACKUP_INTERVAL_SECONDS,
)
import database as db
from scheduler import scan_job, check_signal_performance_job, backup_job, news_auto_job
from handlers.basic import start, help_command
from handlers.analysis import signal_command, chart_command, price_command, top_command, gainers_command
from handlers.watchlist import watch_command, unwatch_command, mywatchlist_command, autoscan_command
from handlers.callbacks import callback_router
from handlers.risk import setrisk_command, myrisk_command, mystats_command, mysignals_command, myanalytics_command
from handlers.backtest import backtest_command
from handlers.news import news_command, news_settings_command, handle_news_callback
from handlers.admin import (
    admin_help_command, block_command, unblock_command, blocklist_command,
    stats_command, broadcast_command, users_command, finduser_command,
    whitelist_add_command, whitelist_remove_command, whitelist_list_command,
    accessmode_command, setwelcome_command, removewelcome_command, getwelcome_command,
    notify_admins_of_access_request, botanalytics_command, backup_command, backuplist_command,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def block_check_handler(update: Update, context):
    """
    اجرا قبل از هر هندلر دیگه (group=-1). سه کار می‌کنه:
    ۱) کاربر رو توی دیتابیس ثبت/بروزرسانی می‌کنه (برای هر تعاملی، نه
       فقط /start - تا یوزرنیم همیشه تازه باشه)
    ۲) اگه مسدود باشه، جلوش رو می‌گیره
    ۳) اگه حالت دسترسی روی «لیست سفید» باشه و کاربر نه ادمینه نه توی
       لیست سفید، جلوی همه‌چیز رو می‌گیره بجز خود /start (تا حداقل
       پیام «منتظر تاییدی» رو ببینه و ادمین بفهمه کسی درخواست داده)
    """
    user = update.effective_user
    if user is None:
        return

    await db.add_user(user.id, user.username or user.first_name or str(user.id))

    if await db.is_user_blocked(user.id):
        if update.message:
            await update.message.reply_text("🚫 دسترسی شما به این ربات مسدود شده است.")
        elif update.callback_query:
            await update.callback_query.answer("🚫 دسترسی شما مسدود شده است.", show_alert=True)
        raise ApplicationHandlerStop

    is_admin = user.id in ADMIN_IDS
    access_mode = await db.get_setting("access_mode", "open")
    if access_mode == "whitelist" and not is_admin:
        is_command_start = bool(update.message and update.message.text and update.message.text.startswith("/start"))
        user_whitelisted = await db.is_whitelisted(user.id)

        if is_command_start and not user_whitelisted:
            # کاربر تازه داره درخواست دسترسی می‌ده - فقط بار اول به
            # ادمین‌ها اطلاع بده (نه هر بار که دوباره /start می‌زنه)
            is_new_request = await db.create_access_request(user.id)
            if is_new_request:
                await notify_admins_of_access_request(context, user)
            # اجازه می‌دیم درخواست به خود start() برسه تا پیام خوش‌آمد/انتظار رو نشون بده
        elif not user_whitelisted:
            if update.message:
                await update.message.reply_text(
                    "⏳ دسترسی شما هنوز توسط ادمین تایید نشده. لطفاً منتظر بمون یا با /start دوباره چک کن."
                )
            elif update.callback_query:
                await update.callback_query.answer("⏳ دسترسی شما هنوز تایید نشده.", show_alert=True)
            raise ApplicationHandlerStop


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! فایل .env رو بساز و توکن رو بذار توش.")

    app = Application.builder().token(BOT_TOKEN).build()

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
    app.add_handler(CommandHandler("mysignals", mysignals_command))
    app.add_handler(CommandHandler("myanalytics", myanalytics_command))
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("newssettings", news_settings_command))

    # دستورات ادمین (خودشون داخلاً چک می‌کنن کاربر ادمینه یا نه)
    app.add_handler(CommandHandler("admin", admin_help_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("unblock", unblock_command))
    app.add_handler(CommandHandler("blocklist", blocklist_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("botanalytics", botanalytics_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("backuplist", backuplist_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("finduser", finduser_command))
    app.add_handler(CommandHandler("whitelist_add", whitelist_add_command))
    app.add_handler(CommandHandler("whitelist_remove", whitelist_remove_command))
    app.add_handler(CommandHandler("whitelist", whitelist_list_command))
    app.add_handler(CommandHandler("accessmode", accessmode_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("removewelcome", removewelcome_command))
    app.add_handler(CommandHandler("getwelcome", getwelcome_command))

    app.add_handler(CallbackQueryHandler(handle_news_callback, pattern=r"^news:"))
    app.add_handler(CallbackQueryHandler(callback_router))
    return app


def start_background_jobs(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scan_job, "interval", seconds=AUTO_SCAN_INTERVAL, args=[app])
    scheduler.add_job(check_signal_performance_job, "interval", seconds=SIGNAL_PERFORMANCE_CHECK_INTERVAL, args=[app])
    scheduler.add_job(backup_job, "interval", seconds=BACKUP_INTERVAL_SECONDS, args=[app])
    scheduler.add_job(news_auto_job, "interval", seconds=30*60, args=[app])
    scheduler.start()
    logger.info(
        "زمان‌بندها فعال شدن. اسکن واچ‌لیست هر %s ثانیه، پایش عملکرد سیگنال هر %s ثانیه، بکاپ دیتابیس هر %s ثانیه.",
        AUTO_SCAN_INTERVAL, SIGNAL_PERFORMANCE_CHECK_INTERVAL, BACKUP_INTERVAL_SECONDS
    )


async def run_bot_only(app: Application):
    """حالت ساده - فقط ربات، بدون پنل وب (وقتی WEB_PANEL_ENABLED=false باشه)"""
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])
        start_background_jobs(app)
        logger.info("ربات در حال اجراست (polling، بدون پنل وب)...")
        try:
            await asyncio.Event().wait()  # تا وقفه‌ی بیرونی (SIGTERM/Ctrl+C) منتظر می‌مونه
        finally:
            await app.updater.stop()
            await app.stop()


async def run_bot_and_web(app: Application):
    """حالت پیش‌فرض - ربات + پنل وب هم‌زمان روی یه پورت"""
    import uvicorn
    from web_panel import app as web_app

    uv_config = uvicorn.Config(web_app, host="0.0.0.0", port=WEB_PANEL_PORT, log_level="warning")
    server = uvicorn.Server(uv_config)

    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])
        start_background_jobs(app)
        logger.info("ربات در حال اجراست (polling) + پنل وب روی پورت %s...", WEB_PANEL_PORT)
        try:
            await server.serve()
        finally:
            await app.updater.stop()
            await app.stop()


async def main_async():
    await db.init_db()
    app = build_application()
    if WEB_PANEL_ENABLED:
        await run_bot_and_web(app)
    else:
        await run_bot_only(app)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
