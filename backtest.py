"""
بک‌تست خودکار موتور سیگنال روی داده‌ی تاریخی

روش کار:
اندیکاتورها یه‌بار روی کل دیتافریم محاسبه می‌شن (چون همه‌شون علّی/causal
هستن - یعنی مقدارشون در هر لحظه فقط به داده‌ی تا همون لحظه بستگی داره،
نه آینده؛ برای اطمینان بیشتر، برای صدور سیگنال در هر نقطه فقط از
df.iloc[:i+1] استفاده می‌شه، یعنی موتور اصلاً نمی‌تونه به کندل‌های بعدی
دسترسی داشته باشه). سپس برای هر کندل i (بعد از دوره‌ی warmup):
- موتور signal رو دقیقاً با همون منطق زنده‌ی /signal صدا می‌زنیم
- اگه سیگنال قطعی (BUY/SELL) بود، فرض می‌کنیم ورود در کندل بعدی (i+1)
  با قیمت باز شدنش (Open) انجام می‌شه - این روش استاندارد و محافظه‌کارانه‌ست
  (نه با قیمت دقیق پیشنهادی که ممکنه اصلاً پر نشه)
- بعد کندل‌به‌کندل جلو می‌ریم تا ببینیم اول به SL می‌خوریم یا به TP ها
- تا وقتی این معامله باز نشده، سیگنال جدید حساب نمی‌کنیم (بدون هم‌پوشانی)

فرض محافظه‌کارانه: اگه توی یه کندل، هم SL و هم یه TP لمس بشن (چون از
روی کندل‌های OHLC نمی‌شه ترتیب دقیق داخل کندل رو فهمید)، SL رو مقدم
فرض می‌کنیم - یعنی بک‌تست به‌جای خوش‌بینانه، بدبینانه/محافظه‌کارانه‌ست.
"""
from dataclasses import dataclass, field
import pandas as pd

from single_analysis import add_extended_indicators, build_single_result

DEFAULT_WARMUP_CANDLES = 60      # قبل از این تعداد کندل، اندیکاتورها (مخصوصاً SMA50) هنوز معتبر نیستن
DEFAULT_MAX_HOLD_CANDLES = 60    # حداکثر تعداد کندلی که یه معامله باز می‌مونه قبل از timeout
DEFAULT_BACKTEST_CANDLES = 300
MAX_BACKTEST_CANDLES = 500
MIN_BACKTEST_CANDLES = 120


@dataclass
class BacktestTrade:
    entry_index: int
    entry_time: object
    exit_time: object
    direction: str
    entry: float
    sl: float
    tps: list
    exit_price: float
    exit_reason: str  # "SL" | "TP3" | "TP2_TIMEOUT" | "TP1_TIMEOUT" | "TIMEOUT" | "STILL_OPEN"
    r_multiple: float
    confidence: int


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    candles_tested: int
    date_from: object
    date_to: object
    trades: list = field(default_factory=list)

    @property
    def resolved_trades(self) -> list:
        """معاملاتی که واقعاً به نتیجه رسیدن (نه STILL_OPEN که هنوز دیتاش تموم نشده)"""
        return [t for t in self.trades if t.exit_reason != "STILL_OPEN"]

    @property
    def total_trades(self) -> int:
        return len(self.resolved_trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.resolved_trades if t.r_multiple > 0)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.resolved_trades if t.r_multiple <= 0)

    @property
    def win_rate(self):
        return (self.wins / self.total_trades * 100) if self.total_trades else None

    @property
    def total_r(self) -> float:
        return sum(t.r_multiple for t in self.resolved_trades)

    @property
    def avg_r(self):
        return (self.total_r / self.total_trades) if self.total_trades else None

    @property
    def profit_factor(self):
        gains = sum(t.r_multiple for t in self.resolved_trades if t.r_multiple > 0)
        losses = abs(sum(t.r_multiple for t in self.resolved_trades if t.r_multiple < 0))
        if losses == 0:
            return None  # تقسیم بر صفر - یعنی هیچ ضرری نبوده (خیلی به‌ندرت پیش میاد)
        return gains / losses

    @property
    def max_consecutive_losses(self) -> int:
        streak, worst = 0, 0
        for t in self.resolved_trades:
            if t.r_multiple <= 0:
                streak += 1
                worst = max(worst, streak)
            else:
                streak = 0
        return worst

    @property
    def still_open_count(self) -> int:
        return sum(1 for t in self.trades if t.exit_reason == "STILL_OPEN")


def _simulate_trade(df: pd.DataFrame, entry_idx: int, direction: str, entry: float,
                     sl: float, tps: list, max_hold: int) -> tuple:
    """
    شبیه‌سازی یه معامله از کندل entry_idx به بعد.
    خروجی: (r_multiple, exit_reason, exit_price, exit_time, exit_index)
    """
    n = len(df)
    end_idx = min(entry_idx + max_hold, n - 1)
    risk = abs(entry - sl)
    if risk == 0:
        return 0.0, "STILL_OPEN", entry, df.iloc[entry_idx]["timestamp"], entry_idx

    best_level = 0  # 0=هیچی، 1=TP1، 2=TP2

    for j in range(entry_idx, end_idx + 1):
        row = df.iloc[j]
        low, high = float(row["low"]), float(row["high"])

        if direction == "BUY":
            hit_sl = low <= sl
            hit_tp3 = high >= tps[2]
            hit_tp2 = high >= tps[1]
            hit_tp1 = high >= tps[0]
        else:  # SELL
            hit_sl = high >= sl
            hit_tp3 = low <= tps[2]
            hit_tp2 = low <= tps[1]
            hit_tp1 = low <= tps[0]

        # فرض محافظه‌کارانه: اگه SL و TP توی یه کندل با هم لمس بشن، SL مقدمه
        if hit_sl:
            return -1.0, "SL", sl, row["timestamp"], j
        if hit_tp3:
            return 3.0, "TP3", tps[2], row["timestamp"], j
        if hit_tp2:
            best_level = max(best_level, 2)
        elif hit_tp1:
            best_level = max(best_level, 1)

    # به پایان دوره‌ی نگهداری رسیدیم بدون برخورد به SL یا TP3
    last_row = df.iloc[end_idx]
    is_data_end = end_idx == n - 1

    if best_level == 2:
        r = abs(tps[1] - entry) / risk
        return r, ("STILL_OPEN" if is_data_end else "TP2_TIMEOUT"), tps[1], last_row["timestamp"], end_idx
    if best_level == 1:
        r = abs(tps[0] - entry) / risk
        return r, ("STILL_OPEN" if is_data_end else "TP1_TIMEOUT"), tps[0], last_row["timestamp"], end_idx

    # نه SL نه هیچ TP - مارک‌تومارکت با آخرین قیمت بسته‌شدن
    last_close = float(last_row["close"])
    signed_r = (last_close - entry) / risk if direction == "BUY" else (entry - last_close) / risk
    reason = "STILL_OPEN" if is_data_end else "TIMEOUT"
    return signed_r, reason, last_close, last_row["timestamp"], end_idx


def run_backtest(
    df: pd.DataFrame, symbol: str, timeframe: str,
    confidence_threshold_fraction: float = None, atr_sl_mult: float = None, rr_targets: list = None,
    warmup: int = DEFAULT_WARMUP_CANDLES, max_hold: int = DEFAULT_MAX_HOLD_CANDLES,
) -> BacktestResult:
    """
    df باید کندل‌های خام (بدون اندیکاتور) و مرتب‌شده بر اساس زمان باشه.
    اندیکاتورها یه‌بار این‌جا (وکتورایز، سریع) محاسبه می‌شن.
    """
    df = add_extended_indicators(df.copy()).reset_index(drop=True)
    n = len(df)
    trades = []

    i = warmup
    while i < n - 1:
        sub_df = df.iloc[:i + 1]
        result = build_single_result(
            sub_df, symbol, timeframe,
            confidence_threshold_fraction=confidence_threshold_fraction,
            atr_sl_mult=atr_sl_mult, rr_targets=rr_targets,
        )

        if result.direction == "NEUTRAL" or not result.tps or result.sl is None:
            i += 1
            continue

        entry_idx = i + 1
        if entry_idx >= n:
            break

        entry_price = float(df.iloc[entry_idx]["open"])
        r, reason, exit_price, exit_time, exit_idx = _simulate_trade(
            df, entry_idx, result.direction, entry_price, result.sl, result.tps, max_hold
        )

        trades.append(BacktestTrade(
            entry_index=entry_idx,
            entry_time=df.iloc[entry_idx]["timestamp"],
            exit_time=exit_time,
            direction=result.direction,
            entry=entry_price,
            sl=result.sl,
            tps=result.tps,
            exit_price=exit_price,
            exit_reason=reason,
            r_multiple=round(r, 3),
            confidence=result.confidence_percent,
        ))

        # تا وقتی این معامله باز بوده، سیگنال جدید حساب نمی‌کنیم (بدون هم‌پوشانی)
        i = exit_idx + 1

    return BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        candles_tested=n,
        date_from=df.iloc[0]["timestamp"] if n else None,
        date_to=df.iloc[-1]["timestamp"] if n else None,
        trades=trades,
    )
