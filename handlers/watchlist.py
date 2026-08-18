from telegram import Update
from telegram.ext import ContextTypes
from exchange import ExchangeClient, normalize_symbol
from config import MAX_WATCHLIST_PER_USER
import database as db


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/watch BTCUSDT`", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    symbol = normalize_symbol(context.args[0])

    max_watchlist = await db.get_int_setting("max_watchlist_per_user", MAX_WATCHLIST_PER_USER)
    count = await db.get_watchlist_count(user_id)
    if count >= max_watchlist:
        await update.message.reply_text(f"❌ حداکثر {max_watchlist} نماد می‌تونی واچ کنی.")
        return

    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await update.message.reply_text(f"❌ نماد `{symbol}` پیدا نشد.", parse_mode="Markdown")
            return
    finally:
        await client.close()

    added = await db.add_to_watchlist(user_id, symbol)
    if added:
        await update.message.reply_text(
            f"✅ `{symbol}` به واچ‌لیست اضافه شد. هر تغییر مهم در سیگنال بهت اطلاع می‌دم.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"ℹ️ `{symbol}` از قبل توی واچ‌لیستت بود.", parse_mode="Markdown")


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/unwatch BTCUSDT`", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    symbol = normalize_symbol(context.args[0])
    await db.remove_from_watchlist(user_id, symbol)
    await update.message.reply_text(f"🗑 `{symbol}` از واچ‌لیست حذف شد.", parse_mode="Markdown")


async def mywatchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    symbols = await db.get_watchlist(user_id)
    if not symbols:
        await update.message.reply_text("واچ‌لیستت خالیه. با `/watch BTCUSDT` شروع کن.", parse_mode="Markdown")
        return
    text = "📋 *واچ‌لیست تو:*\n" + "\n".join(f"• `{s}`" for s in symbols)
    await update.message.reply_text(text, parse_mode="Markdown")


async def autoscan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("استفاده: `/autoscan on` یا `/autoscan off`", parse_mode="Markdown")
        return

    enabled = context.args[0].lower() == "on"
    await db.set_auto_scan(user_id, enabled)
    status = "فعال ✅" if enabled else "غیرفعال ❌"
    await update.message.reply_text(f"اسکن خودکار برات {status} شد.")
