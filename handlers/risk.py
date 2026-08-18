from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database as db


async def setrisk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ثبت موجودی فرضی و درصد ریسک هر معامله، برای محاسبه‌ی خودکار حجم
    پوزیشن روی هر سیگنال بعدی.
    استفاده: /setrisk <موجودی> <درصد‌ریسک>   مثال: /setrisk 1000 2
    """
    if len(context.args) != 2:
        await update.message.reply_text(
            "استفاده: `/setrisk موجودی درصد‌ریسک`\nمثال: `/setrisk 1000 2` "
            "(یعنی موجودی ۱۰۰۰ دلار، حداکثر ۲٪ ریسک هر معامله)",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        balance = float(context.args[0])
        risk_percent = float(context.args[1])
    except ValueError:
        await update.message.reply_text("موجودی و درصد ریسک باید عدد باشن. مثال: `/setrisk 1000 2`", parse_mode=ParseMode.MARKDOWN)
        return

    if balance <= 0:
        await update.message.reply_text("موجودی باید بزرگ‌تر از صفر باشه.")
        return
    if not (0 < risk_percent <= 100):
        await update.message.reply_text("درصد ریسک باید بین ۰ تا ۱۰۰ باشه.")
        return
    if risk_percent > 10:
        await update.message.reply_text(
            f"⚠️ {risk_percent}% ریسک برای هر معامله خیلی بالاست (استاندارد حرفه‌ای معمولاً ۱-۲٪ هست). "
            f"ثبت شد ولی پیشنهاد می‌کنم کمترش کنی."
        )

    user_id = update.effective_user.id
    await db.set_user_risk(user_id, balance, risk_percent)
    await update.message.reply_text(
        f"✅ تنظیم شد: موجودی ${balance:,.0f} — ریسک {risk_percent}% هر معامله "
        f"(معادل ${balance * risk_percent / 100:,.2f} در هر سیگنال)\n\n"
        f"از این به بعد، حجم پوزیشن پیشنهادی خودکار زیر هر سیگنال نمایش داده می‌شه."
    )


async def myrisk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = await db.get_user_risk(user_id)
    if not settings:
        await update.message.reply_text(
            "هنوز تنظیمات ریسک ثبت نکردی. با `/setrisk موجودی درصد‌ریسک` شروع کن.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    await update.message.reply_text(
        f"📐 تنظیمات فعلی:\nموجودی: ${settings['account_balance']:,.0f}\n"
        f"ریسک هر معامله: {settings['risk_percent']}% "
        f"(${settings['account_balance'] * settings['risk_percent'] / 100:,.2f})"
    )


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آمار عملکرد سیگنال‌هایی که این کاربر از /signal گرفته (چندتا به TP رسیدن، چندتا SL خوردن)"""
    user_id = update.effective_user.id
    stats = await db.get_user_performance_stats(user_id)

    if stats["closed"] == 0 and stats["open"] == 0:
        await update.message.reply_text(
            "هنوز سیگنالی برات ثبت نشده. بعد از گرفتن اولین سیگنال از `/signal`، "
            "می‌تونی وضعیتش رو اینجا پیگیری کنی."
        )
        return

    lines = ["📊 *آمار عملکرد سیگنال‌های تو:*", ""]
    if stats["win_rate"] is not None:
        lines.append(f"نرخ برد: *{stats['win_rate']:.0f}%* ({stats['wins']} برد / {stats['losses']} باخت)")
    else:
        lines.append("هنوز هیچ سیگنالی به TP یا SL نرسیده (همه در حال پایشن).")

    lines.append(f"🟢 برخورد به تارگت: {stats['wins']}")
    lines.append(f"🔴 برخورد به حد ضرر: {stats['losses']}")
    lines.append(f"⏳ در حال پایش (باز): {stats['open']}")

    breakdown = stats["breakdown"]
    detail_map = {
        "TP1_HIT": "رسیده به TP1", "TP2_HIT": "رسیده به TP2", "TP3_HIT": "رسیده به TP3",
        "SL_HIT": "خورده به SL", "OPEN": "باز",
    }
    detail_lines = [f"• {detail_map.get(k, k)}: {v}" for k, v in breakdown.items() if k in detail_map]
    if detail_lines:
        lines += ["", "جزئیات:"] + detail_lines

    lines.append("\nℹ️ وضعیت هر سیگنال به‌صورت خودکار هر ۱۰ دقیقه چک می‌شه و اگه به TP/SL برسه، بهت پیام می‌دم.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
