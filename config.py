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
