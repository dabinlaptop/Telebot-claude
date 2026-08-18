from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import MAX_WATCHLIST_PER_USER
import database as db
from handlers.analysis import (
    run_single_timeframe_signal, _get_price_text, _timeframe_keyboard
)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    مسیریابی کلیک روی دکمه‌های شیشه‌ای
    فرمت callback_data: "action:symbol" یا "action:symbol:timeframe"
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[0]

    if action == "tf" and len(parts) == 3:
        _, symbol, timeframe = parts
        user_id = query.from_user.id
        await query.edit_message_text(f"⏳ در حال تحلیل {symbol} روی تایم‌فریم {timeframe}...")
        try:
            text, chart_buf, keyboard = await run_single_timeframe_signal(symbol, timeframe, user_id=user_id)
        except Exception as e:
            await query.edit_message_text(f"❌ خطا در تحلیل: {e}")
            return
        if text is None:
            await query.edit_message_text(f"❌ نماد `{symbol}` پیدا نشد.", parse_mode=ParseMode.MARKDOWN)
            return
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await query.message.reply_photo(photo=chart_buf)

    elif action == "chtf" and len(parts) == 2:
        symbol = parts[1]
        await query.edit_message_text(
            f"⏱ برای «{symbol}» کدوم تایم‌فریم رو تحلیل کنم؟",
            reply_markup=_timeframe_keyboard(symbol)
        )

    elif action == "price" and len(parts) == 2:
        symbol = parts[1]
        text = await _get_price_text(symbol)
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    elif action == "watch" and len(parts) == 2:
        symbol = parts[1]
        user_id = query.from_user.id
        count = await db.get_watchlist_count(user_id)
        if count >= MAX_WATCHLIST_PER_USER:
            await query.message.reply_text(f"❌ حداکثر {MAX_WATCHLIST_PER_USER} نماد می‌تونی واچ کنی.")
            return
        added = await db.add_to_watchlist(user_id, symbol)
        if added:
            await query.message.reply_text(f"✅ `{symbol}` به واچ‌لیست اضافه شد.", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(f"ℹ️ `{symbol}` از قبل توی واچ‌لیستت بود.", parse_mode=ParseMode.MARKDOWN)
