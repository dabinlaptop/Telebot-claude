"""
محاسبه اندیکاتورهای تکنیکال روی دیتافریم کندل‌ها
از کتابخونه‌ی ta استفاده می‌کنیم
"""
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands
from config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    EMA_FAST, EMA_SLOW, BB_PERIOD, BB_STD
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """تمام اندیکاتورها رو به دیتافریم اضافه می‌کنه و همون رو برمی‌گردونه"""
    close = df["close"]

    # RSI
    rsi = RSIIndicator(close=close, window=RSI_PERIOD)
    df["rsi"] = rsi.rsi()

    # MACD
    macd = MACD(close=close, window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # EMA Crossover
    df["ema_fast"] = EMAIndicator(close=close, window=EMA_FAST).ema_indicator()
    df["ema_slow"] = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator()

    # Bollinger Bands
    bb = BollingerBands(close=close, window=BB_PERIOD, window_dev=BB_STD)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()

    # میانگین حجم برای تشخیص اسپایک حجم
    df["volume_sma"] = df["volume"].rolling(window=20).mean()

    return df


# --- تشخیص الگوهای کندل‌استیک ---
# هر تابع کندل آخر (و در صورت نیاز، کندل قبلی) رو بررسی می‌کنه
# و اسم فارسی الگو رو در صورت تشخیص برمی‌گردونه، وگرنه None

def _body(row) -> float:
    return abs(row["close"] - row["open"])


def _range(row) -> float:
    return row["high"] - row["low"]


def _is_bullish(row) -> bool:
    return row["close"] > row["open"]


def detect_candlestick_patterns(df: pd.DataFrame) -> list[dict]:
    """
    بررسی ۲-۳ کندل آخر و برگردوندن لیست الگوهای شناسایی‌شده
    خروجی: [{"name": "پوشا صعودی", "bias": 1}, ...]
    bias: 1 = صعودی، -1 = نزولی
    """
    if len(df) < 3:
        return []

    patterns = []
    last = df.iloc[-1]
    prev = df.iloc[-2]

    last_body = _body(last)
    last_range = _range(last)
    prev_body = _body(prev)

    if last_range == 0:
        return []

    upper_wick = last["high"] - max(last["close"], last["open"])
    lower_wick = min(last["close"], last["open"]) - last["low"]

    # --- پوشای صعودی / نزولی (Engulfing) ---
    if prev_body > 0:
        if (not _is_bullish(prev) and _is_bullish(last)
                and last["close"] >= prev["open"] and last["open"] <= prev["close"]
                and last_body > prev_body):
            patterns.append({"name": "پوشای صعودی (Bullish Engulfing)", "bias": 1})
        elif (_is_bullish(prev) and not _is_bullish(last)
                and last["open"] >= prev["close"] and last["close"] <= prev["open"]
                and last_body > prev_body):
            patterns.append({"name": "پوشای نزولی (Bearish Engulfing)", "bias": -1})

    # --- چکش / چکش معکوس (Hammer / Inverted Hammer) ---
    if last_body > 0 and last_body / last_range < 0.35:
        if lower_wick > last_body * 2 and upper_wick < last_body * 0.5:
            # چکش (Hammer) - سایه‌ی پایین بلند، صرف‌نظر از رنگ کندل، سیگنال برگشت صعودیه
            patterns.append({"name": "چکش (Hammer)", "bias": 1})
        elif upper_wick > last_body * 2 and lower_wick < last_body * 0.5:
            patterns.append({"name": "ستاره‌ی تیرانداز (Shooting Star)", "bias": -1})

    # --- دوجی (Doji) — بلاتکلیفی بازار ---
    if last_body / last_range < 0.1:
        patterns.append({"name": "دوجی (Doji - بلاتکلیفی)", "bias": 0})

    return patterns


def pattern_score(patterns: list[dict]) -> int:
    """جمع bias الگوهای شناسایی‌شده، محدود به بازه‌ی [-1, 1]"""
    if not patterns:
        return 0
    total = sum(p["bias"] for p in patterns)
    return max(-1, min(1, total))


def volume_score(df: pd.DataFrame) -> int:
    """
    اسپایک حجم رو به‌عنوان تاییدکننده‌ی جهت کندل آخر در نظر می‌گیره.
    اگه حجم کندل آخر حداقل ۱.۵ برابر میانگین ۲۰ کندل باشه و کندل صعودی/نزولی
    بود، امتیاز هم‌جهت می‌ده. حجم بدون کندل قوی، سیگنال نمی‌سازه.
    """
    if len(df) < 21:
        return 0
    last = df.iloc[-1]
    avg_volume = df["volume_sma"].iloc[-1]
    if pd.isna(avg_volume) or avg_volume == 0:
        return 0
    if last["volume"] < avg_volume * 1.5:
        return 0
    return 1 if _is_bullish(last) else -1
