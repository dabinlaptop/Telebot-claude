# ربات تحلیل و سیگنال ارز دیجیتال

ربات تلگرامی تحلیل تکنیکال چند‌تایم‌فریمی (۱۵دقیقه / ۱ساعته / ۴ساعته) با
ترکیب ۴ اندیکاتور (RSI، MACD، EMA Crossover، Bollinger Bands) و سیستم
امتیازدهی وزن‌دار برای صدور سیگنال.

## قابلیت‌ها
- `/signal SYMBOL` — تحلیل آنی با جزئیات هر تایم‌فریم
- `/chart SYMBOL [timeframe]` — نمودار قیمت + اندیکاتورها (تصویر)
- `/price SYMBOL` — قیمت لحظه‌ای
- `/watch` `/unwatch` `/mywatchlist` — مدیریت واچ‌لیست شخصی
- `/autoscan on|off` — اعلان خودکار وقتی سیگنال یک نماد واچ‌شده تغییر می‌کنه
- `/top` — سیگنال سریع چند ارز پرطرفدار
- دیتای قیمت از Binance (رایگان، بدون نیاز به API Key)

## ۱. ساخت ربات در تلگرام
1. توی تلگرام به [@BotFather](https://t.me/BotFather) پیام بده.
2. دستور `/newbot` رو بزن و اسم و یوزرنیم دلخواه رو وارد کن.
3. توکنی که می‌ده رو کپی کن (چیزی شبیه `123456:ABC-DEF...`).

---

## 🚂 راه‌اندازی روی Railway (بدون نیاز به سرور شخصی)

پروژه از قبل آماده‌ی دیپلوی روی Railway هست (فایل‌های `Procfile` و
`railway.json` توش هست).

### مرحله ۱ — آپلود پروژه روی گیت‌هاب
Railway از روی یه ریپوی گیت‌هاب دیپلوی می‌کنه. اگه گیت‌هاب نداری:
1. یه ریپوی جدید (می‌تونه Private باشه) توی [github.com](https://github.com) بساز.
2. محتوای این پوشه رو داخلش آپلود کن (یا با گیت پوش کن، یا از طریق وب‌سایت گیت‌هاب فایل‌ها رو درگ-اند-دراپ کن).

> فایل `.gitignore` از قبل هست تا `.env` و دیتابیس محلی آپلود نشن.

### مرحله ۲ — ساخت پروژه در Railway
1. وارد [railway.app](https://railway.app) شو و با گیت‌هاب لاگین کن.
2. **New Project → Deploy from GitHub repo** رو بزن و ریپوی همین پروژه رو انتخاب کن.
3. Railway خودش تشخیص می‌ده پایتونیه و طبق `railway.json` دستور `python bot.py` رو اجرا می‌کنه.

### مرحله ۳ — تنظیم متغیرهای محیطی
توی پنل پروژه، برو به تب **Variables** و این‌ها رو اضافه کن:
- `BOT_TOKEN` = توکنی که از BotFather گرفتی
- `DB_PATH` = `/data/bot_database.db` (به دلیل مهم زیر)

### مرحله ۴ — اضافه کردن Volume برای دیتابیس (خیلی مهم ⚠️)
Railway هر بار که دوباره دیپلوی می‌کنی (مثلاً بعد از هر پوش گیت)، فایل‌سیستم
رو از صفر می‌سازه؛ یعنی اگه دیتابیس SQLite رو روی مسیر عادی نگه داری، با
هر دیپلوی جدید واچ‌لیست همه‌ی کاربرا پاک می‌شه. برای جلوگیری از این:
1. توی پروژه‌ی Railway برو به تب **Volumes**.
2. یه Volume جدید بساز و Mount Path رو بذار: `/data`
3. مطمئن شو `DB_PATH=/data/bot_database.db` توی Variables تنظیم شده (مرحله قبل).

با این کار دیتابیس روی دیسک دائمی ذخیره می‌شه و با ری‌دیپلوی از بین نمی‌ره.

### مرحله ۵ — بررسی لاگ‌ها
توی تب **Deployments → View Logs** می‌تونی ببینی ربات بالا اومده یا نه.
دنبال خط `ربات در حال اجراست (polling)...` بگرد.

همین! چون از `polling` استفاده می‌کنیم (نه webhook)، نیازی به دامنه یا
تنظیمات شبکه‌ی خاصی نیست و روی Railway مستقیم کار می‌کنه.

---

## نصب روی VPS شخصی (روش جایگزین)

اگه بعداً VPS شخصی هم داشتی، این روشه:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# آپلود یا کلون پروژه روی سرور، بعد:
cd crypto_signal_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

تنظیم توکن:

```bash
cp .env.example .env
nano .env   # BOT_TOKEN رو بذار توش
```

تست اجرا:

```bash
python bot.py
```

اگه پیام "ربات در حال اجراست" رو دیدی و توی تلگرام `/start` جواب داد، همه‌چی درسته.

### اجرای دائمی روی سرور (systemd)

یه سرویس بساز تا با ری‌استارت سرور هم بالا بیاد و کرش که کرد خودش دوباره اجرا بشه:

```bash
sudo nano /etc/systemd/system/crypto-bot.service
```

محتوا:

```ini
[Unit]
Description=Crypto Signal Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/crypto_signal_bot
ExecStart=/root/crypto_signal_bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

بعد:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-bot
sudo systemctl start crypto-bot

# چک کردن وضعیت و لاگ‌ها:
sudo systemctl status crypto-bot
journalctl -u crypto-bot -f
```

## تنظیمات قابل تغییر (`config.py`)
- `TIMEFRAMES` — تایم‌فریم‌ها و وزن هرکدوم در امتیاز نهایی
- `STRONG_SIGNAL_THRESHOLD` / `WEAK_SIGNAL_THRESHOLD` — آستانه‌ی صدور سیگنال
- `AUTO_SCAN_INTERVAL` — فاصله‌ی زمانی اسکن خودکار (ثانیه)
- `RSI_OVERSOLD` / `RSI_OVERBOUGHT` — آستانه‌های RSI
- `DEFAULT_SYMBOLS` — لیست پیش‌فرض دستور `/top`

## منطق سیگنال (خلاصه)
هر تایم‌فریم ۴ امتیاز جدا می‌گیره (RSI, MACD, EMA, Bollinger)، هرکدوم بین
-1 تا +1. این امتیاز در وزن تایم‌فریم (۱۵دقیقه=۱، ۱ساعته=۲، ۴ساعته=۳) ضرب
می‌شه. جمع همه‌ی این‌ها امتیاز نهایی رو می‌سازه که بر اساسش سیگنال
STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL تعیین می‌شه.

## توسعه‌های پیشنهادی بعدی
- اتصال به چند صرافی هم‌زمان برای میانگین‌گیری قیمت
- افزودن الگوهای کندل‌استیک (Engulfing، Hammer، ...)
- بک‌تست خودکار استراتژی روی داده‌ی تاریخی
- پنل وب برای مدیریت تنظیمات بدون دسترسی به سرور

## ⚠️ سلب مسئولیت
این ربات صرفاً یک ابزار تحلیل تکنیکاله و **توصیه‌ی مالی نیست**. بازار
ارز دیجیتال پرریسکه؛ همیشه با سرمایه‌ای که از دست دادنش برات قابل تحمله
معامله کن و مدیریت ریسک رو جدی بگیر.
