from telegram import Update
from telegram.ext import ContextTypes
import database as db

WELCOME_TEXT = """
🤖 *به ربات تحلیل و سیگنال ارز دیجیتال خوش اومدی!*

📋 *دستورات:*
`/signal BTCUSDT` — اول تایم‌فریم رو انتخاب می‌کنی، بعد تحلیل کامل با
سیگنال خرید/فروش، درصد اطمینان، حد ضرر/سود (SL/TP) و نمودار چند
اندیکاتوره (EMA, SMA, RSI, MACD) دریافت می‌کنی.
`/chart BTCUSDT` — فقط نمودار (بدون متن تحلیل)
`/price BTCUSDT` — قیمت لحظه‌ای
`/gainers` — بیشترین رشد/افت ۲۴ساعته بازار
`/watch BTCUSDT` — اضافه کردن به واچ‌لیست (سیگنال خودکار پس‌زمینه)
`/unwatch BTCUSDT` — حذف از واچ‌لیست
`/mywatchlist` — نمایش واچ‌لیست
`/autoscan on` یا `/autoscan off` — فعال/غیرفعال کردن اسکن خودکار
`/top` — مرور سریع چند ارز پرطرفدار (چندتایم‌فریمی، برای دید کلی)
`/help` — نمایش همین راهنما

زیر هر پیام سیگنال دکمه داری برای: 🔄 بروزرسانی، ⏱ تغییر تایم‌فریم،
⭐ افزودن به واچ‌لیست و 💰 قیمت لحظه‌ای.

⚠️ این ربات صرفاً یک ابزار تحلیل تکنیکاله و توصیه‌ی مالی نیست.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username or user.first_name)
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
