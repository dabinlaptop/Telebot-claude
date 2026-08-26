from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
import database as db

WELCOME_TEXT = """
🤖 *به ربات تحلیل و سیگنال ارز دیجیتال خوش اومدی!*

📋 *دستورات:*
`/signal BTCUSDT` — اول تایم‌فریم رو انتخاب می‌کنی، بعد تحلیل کامل با
سیگنال خرید/فروش، درصد اطمینان، نقطه ورود، حد ضرر/سود (SL/TP) و نمودار
چند اندیکاتوره (EMA, SMA, RSI, MACD) دریافت می‌کنی. سیگنال با روند
تایم‌فریم بالاتر هم مقایسه می‌شه، اگه واگرایی RSI/قیمت (سیگنال بازگشتی
قوی) پیدا بشه بهش اشاره می‌شه، و همبستگی با بیت‌کوین هم چک می‌شه (تا
بفهمی سیگنال واقعاً مال خود اون ارزه یا صرفاً داره دنبال بازار می‌ره).
`/setrisk موجودی درصد‌ریسک` — مثال: `/setrisk 1000 2` (موجودی ۱۰۰۰
دلار، ۲٪ ریسک هر معامله). بعدش زیر هر سیگنال، حجم پوزیشن پیشنهادی
خودکار محاسبه و نمایش داده می‌شه.
`/myrisk` — نمایش تنظیمات ریسک فعلی‌ت
`/mystats` — آمار عملکرد سیگنال‌هایی که تاییدشون کردی (چندتا به تارگت
رسیدن، چندتا به حد ضرر خوردن) — هر ۱۰ دقیقه خودکار چک و به‌روزت می‌کنه
`/mysignals` — لیست سیگنال‌های فعالی که پیگیریشون رو تایید کردی؛ هر
کدوم رو هر وقت خواستی می‌تونی از لیست حذف کنی
`/backtest BTCUSDT [تایم‌فریم] [تعداد کندل]` — همین موتور سیگنال رو
روی داده‌ی تاریخی شبیه‌سازی می‌کنه و آمار عملکرد (نرخ برد، میانگین R،
Profit Factor) + نمودار منحنی تجمعی بهت می‌ده — تا قبل از اعتماد به
سیگنال‌ها، ببینی این استراتژی روی گذشته چطور بوده
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
⭐ افزودن به واچ‌لیست، 💰 قیمت لحظه‌ای، و (اگه سیگنال قطعی بود) 📌 پیگیری
این سیگنال — با این دکمه از من می‌پرسی که وضعیتش رو برات دنبال کنم یا نه.

⚠️ این ربات صرفاً یک ابزار تحلیل تکنیکاله و توصیه‌ی مالی نیست.
"""

PENDING_APPROVAL_TEXT = """
⏳ *سلام! درخواست دسترسی‌ت ثبت شد.*

این ربات فعلاً فقط برای کاربران تاییدشده در دسترسه. ادمین باید دسترسیت
رو تایید کنه؛ بعدش می‌تونی از همه‌ی امکانات استفاده کنی.

اگه فکر می‌کنی باید بهت دسترسی داده بشه، با ادمین ربات هماهنگ کن.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    custom_message = await db.get_setting("custom_welcome_message", "")

    access_mode = await db.get_setting("access_mode", "open")
    is_pending = (
        access_mode == "whitelist"
        and user.id not in ADMIN_IDS
        and not await db.is_whitelisted(user.id)
    )

    if is_pending:
        # کاربرِ منتظرِ تایید فقط پیام خوش‌آمدگویی سفارشی (اگه ادمین
        # تنظیم کرده باشه) رو می‌بینه، نه لیست کامل دستورات - چون هنوز
        # دسترسی نداره. اگه ادمین پیامی تنظیم نکرده، از متن پیش‌فرض
        # «منتظر تایید» استفاده می‌شه.
        text = custom_message if custom_message else PENDING_APPROVAL_TEXT
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    text = f"📢 {custom_message}\n\n{WELCOME_TEXT}" if custom_message else WELCOME_TEXT
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
