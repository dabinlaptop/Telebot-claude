"""
پنل ادمین ربات - فقط برای شناسه‌های عددی داخل ADMIN_IDS (در .env)
دستورات:
/admin       - راهنمای دستورات ادمین
/block ID    - مسدودکردن یه کاربر با شناسه‌ی عددی تلگرامش
/unblock ID  - رفع مسدودی
/blocklist   - لیست کاربران مسدود
/stats       - آمار کلی ربات
/broadcast   - ارسال پیام به همه‌ی کاربران
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_IDS
import database as db

logger = logging.getLogger(__name__)

ADMIN_HELP_TEXT = """
🛠 *پنل ادمین*

`/block ID [دلیل]` — مسدودکردن کاربر با شناسه‌ی عددی (دیگه نمی‌تونه با ربات کار کنه)
`/unblock ID` — رفع مسدودی
`/blocklist` — لیست کاربران مسدودشده
`/stats` — آمار کلی ربات (تعداد کاربران، واچ‌لیست‌ها، سیگنال‌های امروز)
`/broadcast متن پیام` — ارسال پیام به همه‌ی کاربران ربات

نکته: شناسه‌ی عددی کاربر (User ID) رو می‌تونی از فوروارد پیامش به
@userinfobot یا مشابهش پیدا کنی؛ username کافی نیست.
"""


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return  # کاربر عادی حتی نمی‌فهمه این دستور وجود داره
    await update.message.reply_text(ADMIN_HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: `/block شناسه_عددی [دلیل اختیاری]`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "بدون دلیل ثبت‌شده"

    if target_id in ADMIN_IDS:
        await update.message.reply_text("❌ نمی‌تونی یه ادمین دیگه رو مسدود کنی.")
        return

    await db.block_user(target_id, reason)
    await update.message.reply_text(f"🚫 کاربر `{target_id}` مسدود شد.\nدلیل: {reason}", parse_mode=ParseMode.MARKDOWN)


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: `/unblock شناسه_عددی`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = int(context.args[0])
    was_blocked = await db.unblock_user(target_id)
    if was_blocked:
        await update.message.reply_text(f"✅ کاربر `{target_id}` رفع مسدودیت شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"ℹ️ کاربر `{target_id}` اصلاً مسدود نبود.", parse_mode=ParseMode.MARKDOWN)


async def blocklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    blocked = await db.get_blocked_users()
    if not blocked:
        await update.message.reply_text("لیست مسدودها خالیه.")
        return

    lines = ["🚫 *کاربران مسدودشده:*", ""]
    for b in blocked:
        lines.append(f"• `{b['user_id']}` — {b['reason']} ({b['blocked_at'][:10]})")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    stats = await db.get_bot_stats()
    text = (
        "📊 *آمار کلی ربات*\n\n"
        f"👥 کل کاربران: {stats['total_users']}\n"
        f"🔄 اسکن خودکار فعال: {stats['active_autoscan']}\n"
        f"⭐ کل آیتم‌های واچ‌لیست: {stats['total_watchlist']}\n"
        f"🚫 کاربران مسدود: {stats['total_blocked']}\n"
        f"📈 سیگنال‌های امروز: {stats['signals_today']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("استفاده: `/broadcast متن پیامی که می‌خوای برای همه ارسال بشه`", parse_mode=ParseMode.MARKDOWN)
        return

    message_text = " ".join(context.args)
    user_ids = await db.get_all_user_ids()
    status_msg = await update.message.reply_text(f"⏳ در حال ارسال به {len(user_ids)} کاربر...")

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 {message_text}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # جلوگیری از برخورد با محدودیت نرخ ارسال تلگرام

    await status_msg.edit_text(f"✅ ارسال تمام شد.\nموفق: {sent} | ناموفق: {failed}")


# ---------- بررسی مسدودبودن (برای هندلر سراسری در bot.py) ----------

async def is_blocked(user_id: int) -> bool:
    return await db.is_user_blocked(user_id)
