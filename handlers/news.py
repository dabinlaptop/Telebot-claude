from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database as db
import news as news_module

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/news - نمایش اخبار مهم با درصد تاثیر"""
    await update.message.reply_text("⏳ در حال دریافت اخبار مهم بازار...", parse_mode=ParseMode.MARKDOWN)
    try:
        items = await news_module.get_combined_news(crypto_limit=6, forex_limit=4)
        text = news_module.format_news_message(items, max_items=8)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data="news:refresh")],
            [InlineKeyboardButton("⚙️ تنظیمات اخبار", callback_data="news:settings")],
        ])
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در دریافت اخبار: {e}")

async def news_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/newssettings - تنظیمات اخبار"""
    user_id = update.effective_user.id
    enabled = await db.get_user_news_enabled(user_id)
    auto = await db.get_user_news_auto(user_id)
    status = "فعال ✅" if enabled else "غیرفعال ❌"
    auto_status = "فعال ✅" if auto else "غیرفعال ❌"
    text = (
        f"⚙️ *تنظیمات اخبار*\n\n"
        f"📰 نمایش اخبار زیر سیگنال‌ها: *{status}*\n"
        f"🔔 ارسال خودکار اخبار مهم: *{auto_status}*\n\n"
        f"• اگه «نمایش زیر سیگنال» فعال باشه، زیر هر تحلیل /signal یه خلاصه از اخبار داغ مرتبط میاد.\n"
        f"• اگه «ارسال خودکار» فعال باشه، اخبار خیلی مهم (تاثیر بالای 80%) خودکار برات ارسال می‌شه.\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("تغییر نمایش زیر سیگنال", callback_data="news:toggle_enabled")],
        [InlineKeyboardButton("تغییر ارسال خودکار", callback_data="news:toggle_auto")],
        [InlineKeyboardButton("📰 دیدن اخبار", callback_data="news:refresh")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def handle_news_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "news:refresh":
        await query.edit_message_text("⏳ در حال بروزرسانی اخبار...")
        try:
            items = await news_module.get_combined_news(crypto_limit=6, forex_limit=4)
            text = news_module.format_news_message(items, max_items=8)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data="news:refresh")],
                [InlineKeyboardButton("⚙️ تنظیمات اخبار", callback_data="news:settings")],
            ])
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            await query.edit_message_text(f"❌ خطا: {e}")

    elif data == "news:settings":
        enabled = await db.get_user_news_enabled(user_id)
        auto = await db.get_user_news_auto(user_id)
        status = "فعال ✅" if enabled else "غیرفعال ❌"
        auto_status = "فعال ✅" if auto else "غیرفعال ❌"
        text = (
            f"⚙️ *تنظیمات اخبار*\n\n"
            f"📰 نمایش اخبار زیر سیگنال‌ها: *{status}*\n"
            f"🔔 ارسال خودکار اخبار مهم: *{auto_status}*\n"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تغییر نمایش زیر سیگنال", callback_data="news:toggle_enabled")],
            [InlineKeyboardButton("تغییر ارسال خودکار", callback_data="news:toggle_auto")],
            [InlineKeyboardButton("📰 دیدن اخبار", callback_data="news:refresh")],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data == "news:toggle_enabled":
        cur = await db.get_user_news_enabled(user_id)
        await db.set_user_news_enabled(user_id, not cur)
        new_status = "فعال ✅" if not cur else "غیرفعال ❌"
        await query.answer(f"نمایش اخبار زیر سیگنال: {new_status}", show_alert=True)
        # refresh settings view
        enabled = not cur
        auto = await db.get_user_news_auto(user_id)
        auto_status = "فعال ✅" if auto else "غیرفعال ❌"
        status = "فعال ✅" if enabled else "غیرفعال ❌"
        text = f"⚙️ *تنظیمات اخبار*\n\n📰 نمایش اخبار زیر سیگنال‌ها: *{status}*\n🔔 ارسال خودکار اخبار مهم: *{auto_status}*\n"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تغییر نمایش زیر سیگنال", callback_data="news:toggle_enabled")],
            [InlineKeyboardButton("تغییر ارسال خودکار", callback_data="news:toggle_auto")],
            [InlineKeyboardButton("📰 دیدن اخبار", callback_data="news:refresh")],
        ])
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            pass

    elif data == "news:toggle_auto":
        cur = await db.get_user_news_auto(user_id)
        await db.set_user_news_auto(user_id, not cur)
        new_status = "فعال ✅" if not cur else "غیرفعال ❌"
        await query.answer(f"ارسال خودکار: {new_status}", show_alert=True)
        enabled = await db.get_user_news_enabled(user_id)
        auto = not cur
        status = "فعال ✅" if enabled else "غیرفعال ❌"
        auto_status = "فعال ✅" if auto else "غیرفعال ❌"
        text = f"⚙️ *تنظیمات اخبار*\n\n📰 نمایش اخبار زیر سیگنال‌ها: *{status}*\n🔔 ارسال خودکار اخبار مهم: *{auto_status}*\n"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تغییر نمایش زیر سیگنال", callback_data="news:toggle_enabled")],
            [InlineKeyboardButton("تغییر ارسال خودکار", callback_data="news:toggle_auto")],
            [InlineKeyboardButton("📰 دیدن اخبار", callback_data="news:refresh")],
        ])
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            pass
