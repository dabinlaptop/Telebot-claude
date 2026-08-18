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
        max_watchlist = await db.get_int_setting("max_watchlist_per_user", MAX_WATCHLIST_PER_USER)
        count = await db.get_watchlist_count(user_id)
        if count >= max_watchlist:
            await query.message.reply_text(f"❌ حداکثر {max_watchlist} نماد می‌تونی واچ کنی.")
            return
        added = await db.add_to_watchlist(user_id, symbol)
        if added:
            await query.message.reply_text(f"✅ `{symbol}` به واچ‌لیست اضافه شد.", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(f"ℹ️ `{symbol}` از قبل توی واچ‌لیستت بود.", parse_mode=ParseMode.MARKDOWN)

    elif action == "track" and len(parts) == 2:
        await _handle_track_decision(query, int(parts[1]), confirm=True)

    elif action == "notrack" and len(parts) == 2:
        await _handle_track_decision(query, int(parts[1]), confirm=False)

    elif action == "delsig" and len(parts) == 2:
        perf_id = int(parts[1])
        user_id = query.from_user.id
        deleted = await db.delete_signal_performance(perf_id, user_id)
        if deleted:
            await query.edit_message_text("🗑 این سیگنال از لیست پایش حذف شد.")
        else:
            await query.edit_message_text("ℹ️ این سیگنال قبلاً حذف شده یا مال تو نیست.")


async def _handle_track_decision(query, pending_id: int, confirm: bool):
    """کاربر با دکمه‌ی 📌/❌ تصمیمش رو درباره‌ی پیگیری یه سیگنال اعلام کرده"""
    pending = await db.get_pending_signal(pending_id)
    if not pending:
        await query.answer("این درخواست منقضی شده (بیش از ۲۴ ساعت گذشته).", show_alert=True)
        return

    if pending["user_id"] != query.from_user.id:
        await query.answer("این دکمه مال تو نیست.", show_alert=True)
        return

    if confirm:
        await db.record_signal_performance(
            pending["user_id"], pending["symbol"], pending["timeframe"], pending["direction"],
            pending["entry"], pending["sl"], [pending["tp1"], pending["tp2"], pending["tp3"]]
        )
        await db.delete_pending_signal(pending_id)
        await query.answer("✅ ثبت شد. با /mystats و /mysignals می‌تونی پیگیریش کنی.", show_alert=True)
    else:
        await db.delete_pending_signal(pending_id)
        await query.answer("باشه، این سیگنال پیگیری نمی‌شه.", show_alert=True)

    # ردیف دکمه‌های پیگیری رو از کیبورد پیام اصلی حذف می‌کنیم (تصمیم گرفته شده)
    try:
        current_markup = query.message.reply_markup
        if current_markup:
            new_rows = [
                row for row in current_markup.inline_keyboard
                if not any((btn.callback_data or "").startswith(("track:", "notrack:")) for btn in row)
            ]
            from telegram import InlineKeyboardMarkup
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_rows))
    except Exception:
        pass  # اگه پیام خیلی قدیمی بود و قابل ویرایش نبود، مهم نیست
