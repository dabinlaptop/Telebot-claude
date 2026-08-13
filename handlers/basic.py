from telegram import Update
from telegram.ext import ContextTypes
import database as db

WELCOME_TEXT = """
🤖 *به ربات تحلیل و سیگنال ارز دیجیتال خوش اومدی!*

این ربات با تحلیل هم‌زمان چند تایم‌فریم (۱۵دقیقه، ۱ساعته، ۴ساعته) و ترکیب
چند اندیکاتور (RSI, MACD, EMA Crossover, Bollinger Bands) بهت سیگنال می‌ده.

📋 *دستورات:*
`/signal BTCUSDT` — تحلیل آنی یک ارز
`/chart BTCUSDT` — نمودار قیمت + اندیکاتورها
`/price BTCUSDT` — قیمت لحظه‌ای
`/watch BTCUSDT` — اضافه کردن به واچ‌لیست (سیگنال خودکار)
`/unwatch BTCUSDT` — حذف از واچ‌لیست
`/mywatchlist` — نمایش واچ‌لیست
`/autoscan on` یا `/autoscan off` — فعال/غیرفعال کردن اسکن خودکار
`/top` — سیگنال سریع چند ارز پرطرفدار
`/help` — نمایش همین راهنما

⚠️ این ربات صرفاً یک ابزار تحلیل تکنیکاله و توصیه‌ی مالی نیست.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username or user.first_name)
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
