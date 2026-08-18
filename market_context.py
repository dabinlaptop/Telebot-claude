"""
تحلیل‌های زمینه‌ای که مستقل از موتور اصلی سیگنال هستن ولی روی اعتبار
سیگنال تاثیر می‌ذارن:
1) هم‌راستایی با روند تایم‌فریم بالاتر (Multi-Timeframe Alignment)
2) همبستگی با بیت‌کوین (BTC Correlation) - برای اینکه بفهمی سیگنال یه
   آلت‌کوین واقعاً مال خودشه یا صرفاً داره دنبال کل بازار می‌ره
"""
import pandas as pd
from config import HIGHER_TIMEFRAME_MAP, BTC_SYMBOL, BTC_CORRELATION_LOOKBACK, BTC_HIGH_CORRELATION_THRESHOLD


def _quick_trend_direction(df: pd.DataFrame) -> str:
    """
    تشخیص سریع جهت روند یه تایم‌فریم با ۲ اندیکاتور ساده (بدون نیاز به
    کل موتور سیگنال) - فقط برای چک هم‌راستایی، نه صدور سیگنال مستقل.
    """
    from ta.trend import EMAIndicator, SMAIndicator

    close = df["close"]
    ema12 = EMAIndicator(close=close, window=12).ema_indicator()
    ema26 = EMAIndicator(close=close, window=26).ema_indicator()
    sma20 = SMAIndicator(close=close, window=20).sma_indicator()
    sma50 = SMAIndicator(close=close, window=50).sma_indicator()

    bull_votes = 0
    total = 0
    if not pd.isna(ema12.iloc[-1]) and not pd.isna(ema26.iloc[-1]):
        total += 1
        if ema12.iloc[-1] > ema26.iloc[-1]:
            bull_votes += 1
    if not pd.isna(sma20.iloc[-1]) and not pd.isna(sma50.iloc[-1]):
        total += 1
        if sma20.iloc[-1] > sma50.iloc[-1]:
            bull_votes += 1

    if total == 0:
        return "NEUTRAL"
    if bull_votes == total:
        return "BUY"
    if bull_votes == 0:
        return "SELL"
    return "NEUTRAL"


async def check_higher_timeframe_alignment(client, symbol: str, timeframe: str, signal_direction: str) -> dict | None:
    """
    خروجی: {"higher_tf": "4h", "higher_tf_direction": "BUY"/"SELL"/"NEUTRAL", "aligned": bool}
    یا None اگه تایم‌فریم بالاتری برای مقایسه وجود نداشته باشه (مثلاً روزانه)
    """
    higher_tf = HIGHER_TIMEFRAME_MAP.get(timeframe)
    if not higher_tf or signal_direction == "NEUTRAL":
        return None

    try:
        df = await client.fetch_ohlcv_df(symbol, higher_tf, limit=60)
    except Exception:
        return None

    if len(df) < 26:
        return None

    higher_direction = _quick_trend_direction(df)
    aligned = (higher_direction == signal_direction) or (higher_direction == "NEUTRAL")

    return {
        "higher_tf": higher_tf,
        "higher_tf_direction": higher_direction,
        "aligned": aligned,
    }


async def check_btc_correlation(client, symbol: str, timeframe: str) -> dict | None:
    """
    محاسبه‌ی همبستگی بازدهی این ارز با بیت‌کوین روی همین تایم‌فریم.
    خروجی: {"correlation": float, "high_correlation": bool} یا None اگه
    خود نماد BTC/USDT بود یا داده کافی نبود.
    """
    if symbol == BTC_SYMBOL:
        return None

    try:
        btc_df = await client.fetch_ohlcv_df(BTC_SYMBOL, timeframe, limit=BTC_CORRELATION_LOOKBACK + 5)
        symbol_df = await client.fetch_ohlcv_df(symbol, timeframe, limit=BTC_CORRELATION_LOOKBACK + 5)
    except Exception:
        return None

    if len(btc_df) < 10 or len(symbol_df) < 10:
        return None

    n = min(len(btc_df), len(symbol_df), BTC_CORRELATION_LOOKBACK)
    btc_returns = btc_df["close"].tail(n).pct_change().dropna()
    symbol_returns = symbol_df["close"].tail(n).pct_change().dropna()

    m = min(len(btc_returns), len(symbol_returns))
    if m < 5:
        return None

    corr = float(btc_returns.tail(m).reset_index(drop=True).corr(symbol_returns.tail(m).reset_index(drop=True)))
    if pd.isna(corr):
        return None

    return {
        "correlation": corr,
        "high_correlation": corr >= BTC_HIGH_CORRELATION_THRESHOLD,
    }
