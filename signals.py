"""
موتور تولید سیگنال
منطق: برای هر تایم‌فریم، ۴ اندیکاتور بررسی می‌شن و هرکدوم امتیاز -1 (نزولی)
تا +1 (صعودی) می‌گیرن. این امتیاز در وزن تایم‌فریم ضرب می‌شه و جمع کل
تعیین‌کننده‌ی سیگنال نهاییه. این کار باعث می‌شه سیگنال‌های هم‌جهت در چند
تایم‌فریم اعتبار بیشتری بگیرن (Confluence).
"""
from dataclasses import dataclass, field
import pandas as pd
from config import (
    TIMEFRAMES, RSI_OVERSOLD, RSI_OVERBOUGHT,
    STRONG_SIGNAL_THRESHOLD, WEAK_SIGNAL_THRESHOLD
)
from indicators import add_indicators
from exchange import ExchangeClient


@dataclass
class TimeframeResult:
    timeframe: str
    weight: int
    rsi_score: int
    macd_score: int
    ema_score: int
    bb_score: int
    rsi_value: float
    macd_hist: float
    close_price: float

    @property
    def raw_score(self) -> int:
        return self.rsi_score + self.macd_score + self.ema_score + self.bb_score

    @property
    def weighted_score(self) -> int:
        return self.raw_score * self.weight


@dataclass
class SignalResult:
    symbol: str
    total_score: int
    max_possible_score: int
    signal_type: str
    current_price: float
    timeframe_results: list = field(default_factory=list)

    @property
    def confidence_percent(self) -> int:
        """درصد اطمینان نسبت به حداکثر امتیاز ممکن"""
        if self.max_possible_score == 0:
            return 0
        return int(abs(self.total_score) / self.max_possible_score * 100)


def _score_rsi(rsi_value: float) -> int:
    if pd.isna(rsi_value):
        return 0
    if rsi_value <= RSI_OVERSOLD:
        return 1  # اشباع فروش -> احتمال برگشت صعودی
    if rsi_value >= RSI_OVERBOUGHT:
        return -1  # اشباع خرید -> احتمال برگشت نزولی
    return 0


def _score_macd(macd_line: float, signal_line: float) -> int:
    if pd.isna(macd_line) or pd.isna(signal_line):
        return 0
    return 1 if macd_line > signal_line else -1


def _score_ema(ema_fast: float, ema_slow: float) -> int:
    if pd.isna(ema_fast) or pd.isna(ema_slow):
        return 0
    return 1 if ema_fast > ema_slow else -1


def _score_bb(close: float, bb_upper: float, bb_lower: float, bb_mid: float) -> int:
    if pd.isna(bb_upper) or pd.isna(bb_lower):
        return 0
    # نزدیک باند پایین -> فروش‌رفته، احتمال برگشت صعودی
    dist_to_lower = abs(close - bb_lower)
    dist_to_upper = abs(close - bb_upper)
    band_width = bb_upper - bb_lower
    if band_width == 0:
        return 0
    if dist_to_lower / band_width < 0.15:
        return 1
    if dist_to_upper / band_width < 0.15:
        return -1
    return 0


def _classify(total_score: int) -> str:
    if total_score >= STRONG_SIGNAL_THRESHOLD:
        return "STRONG_BUY"
    if total_score >= WEAK_SIGNAL_THRESHOLD:
        return "BUY"
    if total_score <= -STRONG_SIGNAL_THRESHOLD:
        return "STRONG_SELL"
    if total_score <= -WEAK_SIGNAL_THRESHOLD:
        return "SELL"
    return "NEUTRAL"


async def analyze_symbol(client: ExchangeClient, symbol: str) -> SignalResult:
    """تحلیل کامل یک نماد روی همه‌ی تایم‌فریم‌های تنظیم‌شده"""
    timeframe_results = []
    total_weighted_score = 0
    max_possible = 0
    last_close = 0.0

    for tf, cfg in TIMEFRAMES.items():
        weight = cfg["weight"]
        candles = cfg["candles"]

        df = await client.fetch_ohlcv_df(symbol, tf, limit=candles)
        df = add_indicators(df)
        last_row = df.iloc[-1]
        last_close = float(last_row["close"])

        rsi_score = _score_rsi(last_row["rsi"])
        macd_score = _score_macd(last_row["macd"], last_row["macd_signal"])
        ema_score = _score_ema(last_row["ema_fast"], last_row["ema_slow"])
        bb_score = _score_bb(last_row["close"], last_row["bb_upper"], last_row["bb_lower"], last_row["bb_mid"])

        tf_result = TimeframeResult(
            timeframe=tf,
            weight=weight,
            rsi_score=rsi_score,
            macd_score=macd_score,
            ema_score=ema_score,
            bb_score=bb_score,
            rsi_value=float(last_row["rsi"]) if not pd.isna(last_row["rsi"]) else 0.0,
            macd_hist=float(last_row["macd_hist"]) if not pd.isna(last_row["macd_hist"]) else 0.0,
            close_price=last_close,
        )
        timeframe_results.append(tf_result)
        total_weighted_score += tf_result.weighted_score
        max_possible += weight * 4  # ۴ اندیکاتور، هرکدوم حداکثر امتیاز ۱

    signal_type = _classify(total_weighted_score)

    return SignalResult(
        symbol=symbol,
        total_score=total_weighted_score,
        max_possible_score=max_possible,
        signal_type=signal_type,
        current_price=last_close,
        timeframe_results=timeframe_results,
    )


SIGNAL_EMOJI = {
    "STRONG_BUY": "🟢🟢",
    "BUY": "🟢",
    "NEUTRAL": "⚪️",
    "SELL": "🔴",
    "STRONG_SELL": "🔴🔴",
}

SIGNAL_FA = {
    "STRONG_BUY": "سیگنال خرید قوی",
    "BUY": "سیگنال خرید",
    "NEUTRAL": "خنثی / بدون سیگنال واضح",
    "SELL": "سیگنال فروش",
    "STRONG_SELL": "سیگنال فروش قوی",
}
