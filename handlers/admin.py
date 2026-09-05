"""
پنل ادمین ربات - فقط برای شناسه‌های عددی داخل ADMIN_IDS (در .env)
دستورات:
/admin       - راهنمای دستورات ادمین
/block ID    - مسدودکردن یه کاربر با شناسه‌ی عددی تلگرامش
/unblock ID  - رفع مسدودی
/blocklist   - لیست کاربران مسدود
/stats       - آمار کلی ربات
/broadcast   - ارسال پیام به همه‌ی کاربران
/users       - لیست کاربرانی که ربات رو استارت کردن
/finduser ID - جزئیات کامل یه کاربر خاص
/whitelist_add ID / /whitelist_remove ID / /whitelist - مدیریت لیست سفید
/accessmode  - تنظیم حالت دسترسی (open یا whitelist)
/setwelcome / /removewelcome / /getwelcome - پیام خوش‌آمدگویی سفارشی
"""
import asyncio
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_IDS
import database as db
import analytics
import backup
from handlers.risk import _fmt_group_line

logger = logging.getLogger(__name__)

ADMIN_HELP_TEXT = """
🛠 *پنل ادمین*

*مدیریت کاربران:*
`/users [صفحه]` — لیست کاربرانی که ربات رو استارت کردن (جدیدترین اول)
`/finduser ID` — جزئیات کامل یه کاربر خاص
`/block ID [دلیل]` — مسدودکردن کاربر
`/unblock ID` — رفع مسدودی
`/blocklist` — لیست کاربران مسدودشده

*لیست سفید (دسترسی کنترل‌شده):*
`/accessmode` — نمایش/تغییر حالت دسترسی (`open` یا `whitelist`)
`/whitelist_add ID [یادداشت]` — افزودن به لیست سفید
`/whitelist_remove ID` — حذف از لیست سفید
`/whitelist` — نمایش لیست سفید

*پیام خوش‌آمدگویی:*
`/setwelcome متن` — تنظیم پیام سفارشی که قبل از راهنما نشون داده می‌شه
`/removewelcome` — حذف پیام سفارشی (برگشت به حالت پیش‌فرض)
`/getwelcome` — نمایش پیام فعلی

*عمومی:*
`/stats` — آمار کلی ربات
`/broadcast متن پیام` — ارسال پیام به همه‌ی کاربران ربات
`/botanalytics` — تحلیل فراداده‌ی کل ربات (کدوم تایم‌فریم/نماد بیشترین
نرخ برد رو داشته، بین همه‌ی کاربران - نمونه‌ی آماری بزرگ‌تر از `/myanalytics` شخصی)
`/backup` — ساخت یه بکاپ فوری از دیتابیس و ارسالش همین‌جا (علاوه بر
بکاپ خودکار دوره‌ای که هر چند ساعت یه‌بار خودش انجام می‌شه)
`/backuplist` — لیست بکاپ‌های موجود

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


async def botanalytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تحلیل فراداده‌ی کل ربات (بین همه‌ی کاربران) - چون نمونه‌ی آماری‌ش
    خیلی بزرگ‌تر از هر کاربر تنهاست، نتیجه‌گیری‌هاش قابل‌اتکاتره.
    """
    if not _is_admin(update.effective_user.id):
        return

    total = await analytics.get_total_resolved_count(user_id=None)
    if total == 0:
        await update.message.reply_text("هنوز هیچ سیگنالی توی کل ربات به نتیجه نرسیده.")
        return

    by_tf = await analytics.analyze_by_timeframe(user_id=None)
    by_symbol = await analytics.analyze_by_symbol(user_id=None)
    by_direction = await analytics.analyze_by_direction(user_id=None)

    lines = [f"🔬 *تحلیل فراداده‌ی کل ربات* (از {total} سیگنال به‌نتیجه‌رسیده، همه‌ی کاربران)", ""]

    lines.append("📊 *بر اساس تایم‌فریم:*")
    for s in by_tf[:8]:
        lines.append(_fmt_group_line(s))

    lines.append("\n💎 *پرتکرارترین نمادها:*")
    for s in by_symbol[:8]:
        lines.append(_fmt_group_line(s))

    lines.append("\n🧭 *بر اساس جهت:*")
    for s in by_direction:
        lines.append(_fmt_group_line(s))

    lines.append(
        "\nℹ️ آیتم‌های «نمونه‌ی کم» یعنی تعداد سیگنال‌های به‌نتیجه‌رسیده "
        f"کمتر از {analytics.MIN_SAMPLES_FOR_CONFIDENCE} تا بوده."
    )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بکاپ فوری از دیتابیس می‌گیره و فایلش رو مستقیم همین‌جا (به‌عنوان سند تلگرامی) می‌فرسته"""
    if not _is_admin(update.effective_user.id):
        return

    msg = await update.message.reply_text("⏳ در حال ساخت بکاپ...")
    try:
        path = await backup.create_backup()
    except Exception as e:
        await msg.edit_text(f"❌ ساخت بکاپ ناموفق بود: {e}")
        return

    size_kb = os.path.getsize(path) / 1024
    await msg.edit_text(f"✅ بکاپ ساخته شد ({size_kb:.1f} KB). در حال ارسال فایل...")
    try:
        with open(path, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(path))
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"✅ بکاپ ساخته شد ولی ارسال فایل ناموفق بود: {e}\nمسیر روی سرور: `{path}`", parse_mode=ParseMode.MARKDOWN)


async def backuplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    backups = backup.list_backups()
    if not backups:
        await update.message.reply_text("هنوز هیچ بکاپی ساخته نشده. با `/backup` یکی بساز.", parse_mode=ParseMode.MARKDOWN)
        return

    lines = [f"💾 *بکاپ‌های موجود ({len(backups)}):*", ""]
    for b in backups:
        lines.append(f"• `{b['filename']}` — {b['size_kb']:.1f}KB — {b['created_at'].strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nبرای گرفتن یه بکاپ تازه: /backup\nبرای دانلود بکاپ‌های قدیمی‌تر: پنل وب → صفحه‌ی «بکاپ‌ها»")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


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


# ---------- لیست کاربران ----------

USERS_PAGE_SIZE = 15


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    page = 1
    if context.args and context.args[0].isdigit():
        page = max(1, int(context.args[0]))

    total = await db.get_user_total_count()
    offset = (page - 1) * USERS_PAGE_SIZE
    users = await db.get_users_page(limit=USERS_PAGE_SIZE, offset=offset)

    if not users:
        await update.message.reply_text("هیچ کاربری (توی این صفحه) پیدا نشد.")
        return

    total_pages = (total + USERS_PAGE_SIZE - 1) // USERS_PAGE_SIZE
    lines = [f"👥 *کاربران ربات* — صفحه {page} از {total_pages} (کل: {total})", ""]
    for u in users:
        flags = ""
        if u["is_blocked"]:
            flags += " 🚫"
        if u["is_whitelisted"]:
            flags += " ✅"
        uname = u["username"] or "بدون‌نام"
        lines.append(f"• `{u['user_id']}` — {uname}{flags} — {u['joined_at'][:10]}")

    if total_pages > 1:
        lines.append(f"\nبرای صفحه‌ی بعد: `/users {page + 1}`")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def finduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("استفاده: `/finduser شناسه_عددی`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = int(context.args[0])
    profile = await db.find_user(target_id)
    if not profile:
        await update.message.reply_text(f"❌ کاربری با شناسه‌ی `{target_id}` پیدا نشد.", parse_mode=ParseMode.MARKDOWN)
        return

    uname = profile["username"] or "بدون‌نام"
    lines = [
        f"👤 *پروفایل کاربر*",
        f"شناسه: `{profile['user_id']}`",
        f"یوزرنیم/نام: {uname}",
        f"تاریخ عضویت: {profile['joined_at'][:10]}",
        f"اسکن خودکار: {'فعال' if profile['auto_scan_enabled'] else 'غیرفعال'}",
        f"تعداد واچ‌لیست: {profile['watchlist_count']}",
        f"وضعیت مسدودی: {'🚫 مسدود — ' + profile['block_reason'] if profile['is_blocked'] else '✅ آزاد'}",
        f"لیست سفید: {'✅ عضو' if profile['is_whitelisted'] else '❌ نیست'}",
    ]
    if target_id in ADMIN_IDS:
        lines.append("👑 این کاربر ادمینه.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------- لیست سفید و حالت دسترسی ----------

async def whitelist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: `/whitelist_add شناسه_عددی [یادداشت اختیاری]`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = int(context.args[0])
    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    await db.add_to_whitelist(target_id, note)
    await update.message.reply_text(f"✅ کاربر `{target_id}` به لیست سفید اضافه شد و الان دسترسی کامل داره.", parse_mode=ParseMode.MARKDOWN)


async def whitelist_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: `/whitelist_remove شناسه_عددی`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = int(context.args[0])
    removed = await db.remove_from_whitelist(target_id)
    if removed:
        await update.message.reply_text(f"✅ کاربر `{target_id}` از لیست سفید حذف شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"ℹ️ کاربر `{target_id}` اصلاً توی لیست سفید نبود.", parse_mode=ParseMode.MARKDOWN)


async def whitelist_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    wl = await db.get_whitelist()
    if not wl:
        await update.message.reply_text("لیست سفید خالیه.")
        return

    lines = ["✅ *لیست سفید:*", ""]
    for w in wl:
        uname = w["username"] or "بدون‌نام"
        note_part = f" — {w['note']}" if w["note"] else ""
        lines.append(f"• `{w['user_id']}` — {uname}{note_part}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def accessmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    current = await db.get_setting("access_mode", "open")

    if not context.args:
        explain = (
            "🌐 *حالت باز (open)*: همه می‌تونن از ربات استفاده کنن مگر اینکه مسدودشون کنی."
            if current == "open" else
            "🔒 *حالت لیست سفید (whitelist)*: فقط کاربرانی که با `/whitelist_add` تاییدشون کردی (و ادمین‌ها) می‌تونن از ربات استفاده کنن. بقیه فقط `/start` رو می‌بینن و پیام «منتظر تایید» می‌گیرن."
        )
        await update.message.reply_text(
            f"حالت دسترسی فعلی: *{current}*\n\n{explain}\n\n"
            f"برای تغییر: `/accessmode open` یا `/accessmode whitelist`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    new_mode = context.args[0].lower()
    if new_mode not in ("open", "whitelist"):
        await update.message.reply_text("مقدار باید `open` یا `whitelist` باشه.", parse_mode=ParseMode.MARKDOWN)
        return

    await db.set_setting("access_mode", new_mode)
    if new_mode == "whitelist":
        await update.message.reply_text(
            "🔒 حالت دسترسی روی *لیست سفید* تنظیم شد. از الان فقط کاربران لیست‌سفیدشده (و ادمین‌ها) "
            "می‌تونن از ربات استفاده کنن.\n\nبا `/whitelist_add شناسه_عددی` کاربر اضافه کن.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("🌐 حالت دسترسی روی *باز* تنظیم شد. همه (مگر مسدودشده‌ها) دسترسی دارن.", parse_mode=ParseMode.MARKDOWN)


# ---------- پیام خوش‌آمدگویی سفارشی ----------

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("استفاده: `/setwelcome متن پیام خوش‌آمدگویی`", parse_mode=ParseMode.MARKDOWN)
        return

    message_text = update.message.text.split(None, 1)[1]  # همه‌چیز بعد از /setwelcome (فاصله‌ها رو حفظ می‌کنه)
    await db.set_setting("custom_welcome_message", message_text)
    await update.message.reply_text("✅ پیام خوش‌آمدگویی سفارشی ثبت شد. با `/getwelcome` می‌تونی ببینیش.")


async def removewelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    await db.set_setting("custom_welcome_message", "")
    await update.message.reply_text("🗑 پیام سفارشی حذف شد؛ از الان فقط راهنمای پیش‌فرض نشون داده می‌شه.")


async def getwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return

    current = await db.get_setting("custom_welcome_message", "")
    if not current:
        await update.message.reply_text("هیچ پیام سفارشی‌ای تنظیم نشده.")
        return
    await update.message.reply_text(f"پیام فعلی:\n\n{current}")


# ---------- نوتیفیکیشن خودکار به ادمین‌ها هنگام درخواست دسترسی جدید ----------

async def notify_admins_of_access_request(context: ContextTypes.DEFAULT_TYPE, user) -> None:
    """
    وقتی کاربری که whitelist نیست /start می‌زنه (توی حالت دسترسی
    whitelist)، این تابع به همه‌ی ادمین‌ها یه پیام با دکمه‌ی تایید/رد
    می‌فرسته - تا لازم نباشه ادمین دستی بره /users رو چک کنه.
    """
    if not ADMIN_IDS:
        return

    uname = user.username or user.first_name or "بدون‌نام"
    text = (
        f"🔔 *درخواست دسترسی جدید*\n\n"
        f"شناسه: `{user.id}`\n"
        f"نام/یوزرنیم: {uname}\n\n"
        f"می‌خوای دسترسی بدی؟"
    )
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تایید کن", callback_data=f"approve_access:{user.id}"),
        InlineKeyboardButton("❌ رد کن", callback_data=f"reject_access:{user.id}"),
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"ارسال نوتیفیکیشن درخواست دسترسی به ادمین {admin_id} ناموفق بود: {e}")


# ---------- بررسی مسدودبودن (برای هندلر سراسری در bot.py) ----------

async def is_blocked(user_id: int) -> bool:
    return await db.is_user_blocked(user_id)
