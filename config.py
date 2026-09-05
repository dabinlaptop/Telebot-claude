"""
تنظیمات اصلی ربات
مقادیر حساس (توکن و ...) از فایل .env خونده می‌شن
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- تلگرام ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --- دیتابیس ---
DB_PATH = os.getenv("DB_PATH", "bot_database.db")

# --- صرافی ---
EXCHANGE_ID = "binance"  # از طریق ccxt - نیازی به API Key برای دیتای قیمت نیست

# --- تایم‌فریم‌ها و وزن هرکدوم در امتیاز نهایی ---
# وزن بیشتر یعنی تاثیر بیشتر در تصمیم نهایی (روند بزرگ‌تر مهم‌تره)
TIMEFRAMES = {
    "15m": {"weight": 1, "candles": 100},
    "1h": {"weight": 2, "candles": 100},
    "4h": {"weight": 3, "candles": 100},
}

# --- تنظیمات اندیکاتورها ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_FAST = 9
EMA_SLOW = 21

BB_PERIOD = 20
BB_STD = 2

# --- آستانه‌ی امتیاز برای صدور سیگنال ---
# حداکثر امتیاز ممکن = مجموع وزن‌ها * تعداد مولفه‌های امتیازدهی (6) = (1+2+3)*6 = 36
# مولفه‌ها: RSI, MACD, EMA Crossover, Bollinger, Volume Spike, Candlestick Pattern
STRONG_SIGNAL_THRESHOLD = 18   # امتیاز >= این عدد => سیگنال قوی
WEAK_SIGNAL_THRESHOLD = 9      # امتیاز >= این عدد => سیگنال ضعیف

# --- زمان‌بندی اسکن خودکار (ثانیه) ---
AUTO_SCAN_INTERVAL = 15 * 60  # هر ۱۵ دقیقه واچ‌لیست کاربرا رو چک کن

# --- لیست ارزهای پیش‌فرض قابل تحلیل سریع ---
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]

# --- محدودیت واچ‌لیست هر کاربر ---
MAX_WATCHLIST_PER_USER = 15

# --- ادمین‌ها (شناسه عددی تلگرام، جدا شده با کاما در .env) ---
# مثال در .env: ADMIN_IDS=111111111,222222222
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# --- فیلتر هم‌راستایی چند‌تایم‌فریمی (برای موتور /signal) ---
# قبل از صدور سیگنال، روند تایم‌فریم بالاتر هم چک می‌شه (فقط هشدار می‌ده، مانع صدور سیگنال نمی‌شه)
HIGHER_TIMEFRAME_MAP = {
    "1m": "15m",
    "5m": "1h",
    "15m": "1h",
    "30m": "4h",
    "1h": "4h",
    "4h": "1d",
    "1d": "1w",
    "1w": None,  # بالاترین تایم‌فریمه، چیزی برای مقایسه نیست
}

# --- واگرایی RSI/قیمت ---
DIVERGENCE_LOOKBACK = 30   # تعداد کندل برای جستجوی واگرایی
DIVERGENCE_PIVOT_WINDOW = 2  # تعداد کندل هر طرف برای تشخیص سقف/کف محلی

# --- همبستگی با بیت‌کوین ---
BTC_SYMBOL = "BTC/USDT"
BTC_CORRELATION_LOOKBACK = 30       # تعداد کندل برای محاسبه‌ی همبستگی
BTC_HIGH_CORRELATION_THRESHOLD = 0.75  # بالاتر از این یعنی «صرفاً دنبال بازار»

# --- مدیریت ریسک پیش‌فرض (اگه کاربر با /setrisk چیزی تنظیم نکرده باشه) ---
DEFAULT_RISK_PERCENT = 2.0  # درصد پیش‌فرض ریسک هر معامله از موجودی فرضی

# --- پایش خودکار عملکرد سیگنال‌ها ---
SIGNAL_PERFORMANCE_CHECK_INTERVAL = 10 * 60  # هر ۱۰ دقیقه وضعیت سیگنال‌های باز رو چک کن
MAX_OPEN_SIGNALS_PER_CHECK = 200  # سقف تعداد سیگنال باز در هر دور بررسی (جلوگیری از بار زیاد روی API)

# --- پنل وب مدیریت تنظیمات ---
# این‌ها رو توی .env تنظیم کن؛ پیش‌فرض‌های زیر فقط برای جلوگیری از کرش
# محیط توسعه‌ست - حتماً روی پروداکشن عوضشون کن
WEB_PANEL_USERNAME = os.getenv("WEB_PANEL_USERNAME", "admin")
WEB_PANEL_PASSWORD = os.getenv("WEB_PANEL_PASSWORD", "")
WEB_PANEL_ENABLED = os.getenv("WEB_PANEL_ENABLED", "true").lower() in ("1", "true", "yes")
# Railway خودش این متغیر رو ست می‌کنه؛ لوکال دیفالت 8000
WEB_PANEL_PORT = int(os.getenv("PORT", "8000"))

# --- فیبوناچی (تاییدکننده‌ی SL/TP) ---
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIBONACCI_LOOKBACK = 30            # تعداد کندل برای تشخیص Swing High/Low مرجع فیبوناچی
FIBONACCI_TOLERANCE_ATR_MULT = 0.3  # فاصله‌ی مجاز (بر حسب ATR) تا SL/ورود "نزدیک" یه سطح فیبوناچی حساب بشه

# --- تشخیص رژیم نوسان (بر پایه‌ی صدک ATR نسبت به تاریخچه‌ی خودش) ---
VOLATILITY_LOOKBACK = 100          # تعداد کندل برای محاسبه‌ی صدک ATR
VOLATILITY_HIGH_PERCENTILE = 80    # بالای این صدک یعنی نوسان «بالا»
VOLATILITY_EXTREME_PERCENTILE = 95  # بالای این صدک یعنی نوسان «شدید»
VOLATILITY_HIGH_RISK_MULT = 0.5     # توی نوسان بالا، حجم پوزیشن پیشنهادی رو در این ضریب ضرب کن
VOLATILITY_EXTREME_RISK_MULT = 0.25  # توی نوسان شدید

# --- عمق اردربوک (فشار خرید/فروش لحظه‌ای) ---
ORDER_BOOK_DEPTH_LEVELS = 20        # تعداد سطح قیمتی هر طرف (bid/ask) که بررسی می‌شه
ORDER_BOOK_IMBALANCE_THRESHOLD = 0.60  # بالای این نسبت یعنی فشار قابل‌توجه یه طرف

# --- حرکت خودکار SL به نقطه‌ی سربه‌سر بعد از TP1 ---
BREAKEVEN_AFTER_TP1 = True

# --- بک‌تست پیشرو (Walk-Forward) ---
WALK_FORWARD_SEGMENTS = 4           # داده‌ی تاریخی به این تعداد بازه‌ی مساوی تقسیم می‌شه

# --- فاندامنتال (منابع رایگان) ---
FUNDAMENTALS_ENABLED = True
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/"
FUNDAMENTALS_CACHE_TTL_COIN = 30 * 60     # اطلاعات هر کوین: هر ۳۰ دقیقه تازه‌سازی کن
FUNDAMENTALS_CACHE_TTL_MARKET = 15 * 60   # ترس‌وطمع/دامیننس: هر ۱۵ دقیقه

# --- تحلیل فراداده (Meta-Analytics) ---
# MIN_SAMPLES_FOR_CONFIDENCE توی analytics.py تعریف شده (نه اینجا) چون
# فقط همون‌جا استفاده می‌شه

# --- بکاپ خودکار دیتابیس ---
# پیش‌فرض: کنار خودِ فایل دیتابیس، توی یه پوشه‌ی backups/ - یعنی اگه
# DB_PATH روی Volume دائمی Railway باشه (مثل /data/bot_database.db)،
# بکاپ‌ها هم خودکار روی همون دیسک دائمی ذخیره می‌شن، نه دیسک موقت
BACKUP_DIR = os.getenv(
    "BACKUP_DIR",
    os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", "backups")
)
BACKUP_INTERVAL_HOURS = float(os.getenv("BACKUP_INTERVAL_HOURS", "6"))
BACKUP_INTERVAL_SECONDS = int(BACKUP_INTERVAL_HOURS * 3600)
BACKUP_MAX_COUNT = int(os.getenv("BACKUP_MAX_COUNT", "14"))  # حداکثر تعداد بکاپ نگه‌داشته‌شده (رول می‌شه)
