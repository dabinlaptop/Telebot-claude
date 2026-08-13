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

    return df
