"""
تولید نمودار حرفه‌ای قیمت (کندل‌استیک واقعی) + حجم + RSI + MACD
به‌صورت تصویر PNG برای ارسال در تلگرام.

نکته‌ی مهم درباره‌ی عرض میله‌ها: چون محور X تاریخ/زمانه، عرض میله‌ها
(کندل، حجم، هیستوگرام MACD) به‌صورت `pandas.Timedelta` محاسبه می‌شه -
نه یه عدد شناور دستی - چون matplotlib خودش واحد صحیح رو از روی
Timedelta تشخیص می‌ده و مستقل از بازه‌ی کلی نمودار درست کار می‌کنه.
(نسخه‌ی قبلی این عرض رو با یه ضریب ثابت روی کل بازه‌ی زمانی حساب
می‌کرد که باعث می‌شد میله‌ها به‌جای جدا بودن، توی هم ادغام بشن.)
"""
import matplotlib
matplotlib.use("Agg")  # بدون نیاز به نمایشگر
import matplotlib.pyplot as plt
import pandas as pd
import io

BG_COLOR = "#0f1117"
GRID_COLOR = "#242832"
TEXT_COLOR = "#cccccc"
UP_COLOR = "#22c55e"
DOWN_COLOR = "#ef4444"

SUPPORT_RESISTANCE_LOOKBACK = 30  # تعداد کندل برای تشخیص آخرین سقف/کف قابل توجه


def _candle_width(df: pd.DataFrame) -> pd.Timedelta:
    """فاصله‌ی معمول بین کندل‌ها رو پیدا می‌کنه تا عرض میله‌ها متناسب باشه"""
    diffs = df["timestamp"].diff().dropna()
    if len(diffs) == 0:
        return pd.Timedelta(hours=1)
    return diffs.median()


def _style_axes(*axes):
    for ax in axes:
        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.6)
        for spine in ax.spines.values():
            spine.set_color("#333333")


def _draw_level_line(ax, x_end, x_margin_end, price: float, color: str, label: str):
    """رسم خط افقی سطح (ورود/SL/TP/حمایت/مقاومت) با برچسب خوانا داخل یه جعبه‌ی رنگی"""
    ax.axhline(price, color=color, linewidth=1, alpha=0.9, zorder=3)
    ax.annotate(
        f" {label} ",
        xy=(x_margin_end, price),
        xytext=(4, 0),
        textcoords="offset points",
        va="center",
        ha="left",
        fontsize=7,
        color="#0f1117",
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.2", facecolor=color, edgecolor="none", alpha=0.95),
        clip_on=False,
        zorder=5,
    )


def generate_extended_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    levels: dict | None = None,
) -> io.BytesIO:
    """
    نمودار مخصوص تحلیل تک‌تایم‌فریمی: کندل‌استیک واقعی + EMA12/26 +
    SMA20/50 + حمایت/مقاومت، حجم، RSI، MACD.
    df باید خروجی add_extended_indicators (از single_analysis.py) باشه.
    levels (اختیاری): {"entry": float, "sl": float, "tps": [float, float, float]}
    """
    df = df.reset_index(drop=True)
    candle_width = _candle_width(df)
    bar_width = candle_width * 0.7  # کمی باریک‌تر از فاصله‌ی کندل‌ها تا میله‌ها به‌هم نچسبن

    fig, (ax_price, ax_volume, ax_rsi, ax_macd) = plt.subplots(
        4, 1, figsize=(11, 10.5), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 0.8, 1, 1]}
    )
    fig.patch.set_facecolor(BG_COLOR)
    _style_axes(ax_price, ax_volume, ax_rsi, ax_macd)

    x = df["timestamp"]
    is_up = df["close"] >= df["open"]
    candle_colors = [UP_COLOR if up else DOWN_COLOR for up in is_up]

    # --- کندل‌استیک واقعی (بدنه + سایه) ---
    ax_price.vlines(x, df["low"], df["high"], color=candle_colors, linewidth=0.8, zorder=2)
    body_bottom = df[["open", "close"]].min(axis=1)
    body_height = (df["open"] - df["close"]).abs().clip(lower=body_bottom * 0.0002)  # حداقل ارتفاع قابل‌دیدن
    ax_price.bar(x, body_height, bottom=body_bottom, width=bar_width, color=candle_colors, zorder=2)

    # --- میانگین‌های متحرک ---
    ax_price.plot(x, df["ema12"], color="#60a5fa", linewidth=1.1, label="EMA12", zorder=3)
    ax_price.plot(x, df["ema26"], color="#f97316", linewidth=1.1, label="EMA26", zorder=3)
    ax_price.plot(x, df["sma20"], color="#eab308", linewidth=1, linestyle="--", label="SMA20", zorder=3)
    ax_price.plot(x, df["sma50"], color="#a855f7", linewidth=1, linestyle="--", label="SMA50", zorder=3)

    # --- حمایت / مقاومت (بر پایه‌ی آخرین سقف و کف قابل‌توجه) ---
    recent = df.tail(SUPPORT_RESISTANCE_LOOKBACK)
    resistance = float(recent["high"].max())
    support = float(recent["low"].min())

    x_start = x.iloc[0]
    x_end = x.iloc[-1]
    x_margin_end = x_end + candle_width * 3  # فضای خالی سمت راست برای برچسب‌ها
    for ax in (ax_price, ax_volume, ax_rsi, ax_macd):
        ax.set_xlim(x_start - candle_width, x_margin_end + candle_width * 4)

    ax_price.axhline(resistance, color="#94a3b8", linewidth=0.9, linestyle=":", alpha=0.8, zorder=2)
    ax_price.axhline(support, color="#94a3b8", linewidth=0.9, linestyle=":", alpha=0.8, zorder=2)
    ax_price.text(x_start, resistance, " Resistance ", color="#94a3b8", fontsize=7, va="bottom", ha="left")
    ax_price.text(x_start, support, " Support ", color="#94a3b8", fontsize=7, va="top", ha="left")

    # --- خطوط ورود / حد ضرر / تارگت‌ها ---
    if levels:
        if levels.get("entry") is not None:
            _draw_level_line(ax_price, x_end, x_margin_end, levels["entry"], "#eab308", "Entry")
        if levels.get("sl") is not None:
            _draw_level_line(ax_price, x_end, x_margin_end, levels["sl"], "#ef4444", "SL")
        for i, tp in enumerate(levels.get("tps") or [], start=1):
            _draw_level_line(ax_price, x_end, x_margin_end, tp, "#22c55e", f"TP{i}")

    # --- سطوح فیبوناچی رتریسمنت (نازک و کم‌رنگ، فقط برای زمینه) ---
    if levels and levels.get("fib_levels"):
        for fib_ratio, fib_price in levels["fib_levels"].items():
            ax_price.axhline(fib_price, color="#c084fc", linewidth=0.5, linestyle=":", alpha=0.45, zorder=1)
            ax_price.text(x_start, fib_price, f" fib {fib_ratio:.3f} ", color="#c084fc", fontsize=6, va="bottom", ha="left", alpha=0.8)

    ax_price.set_title(f"{symbol} — {timeframe}", color="white", fontsize=13, fontweight="bold", pad=12)
    legend = ax_price.legend(
        loc="upper left", fontsize=7.5, facecolor=BG_COLOR, labelcolor="white",
        ncol=4, framealpha=0.7, edgecolor=GRID_COLOR
    )

    # --- حجم ---
    vol_colors = [UP_COLOR if up else DOWN_COLOR for up in is_up]
    ax_volume.bar(x, df["volume"], color=vol_colors, width=bar_width, alpha=0.85)
    if "volume_sma" in df.columns:
        ax_volume.plot(x, df["volume_sma"], color="#eab308", linewidth=0.9)
    ax_volume.set_ylabel("Volume", color=TEXT_COLOR, fontsize=8)

    # --- RSI ---
    ax_rsi.plot(x, df["rsi"], color="#a855f7", linewidth=1.1)
    ax_rsi.axhline(70, color=DOWN_COLOR, linewidth=0.7, linestyle="--", alpha=0.7)
    ax_rsi.axhline(50, color="#666666", linewidth=0.5, linestyle=":")
    ax_rsi.axhline(30, color=UP_COLOR, linewidth=0.7, linestyle="--", alpha=0.7)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", color=TEXT_COLOR, fontsize=8)

    # --- MACD ---
    if "macd_hist" in df.columns:
        macd_hist = df["macd_hist"]
    else:
        macd_hist = df["macd"] - df["macd_signal"]
    hist_colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in macd_hist.fillna(0)]
    ax_macd.bar(x, macd_hist, color=hist_colors, width=bar_width)
    ax_macd.plot(x, df["macd"], color="#60a5fa", linewidth=0.9, label="MACD")
    ax_macd.plot(x, df["macd_signal"], color="#f59e0b", linewidth=0.9, label="Signal")
    ax_macd.legend(loc="upper left", fontsize=7, facecolor=BG_COLOR, labelcolor="white", framealpha=0.7)
    ax_macd.set_ylabel("MACD", color=TEXT_COLOR, fontsize=8)

    fig.autofmt_xdate(rotation=25)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_backtest_chart(trades: list, symbol: str, timeframe: str) -> io.BytesIO:
    """
    نمودار منحنی تجمعی R-multiple (Equity Curve) بک‌تست - نشون می‌ده
    اگه هر معامله دقیقاً ۱ واحد ریسک (مثلاً ۱٪ حساب) بود، سرمایه‌ی فرضی
    (بر حسب واحد R) در طول زمان چطور تغییر می‌کرد.
    """
    resolved = [t for t in trades if t.exit_reason != "STILL_OPEN"]

    fig, (ax_equity, ax_bars) = plt.subplots(
        2, 1, figsize=(10, 6), gridspec_kw={"height_ratios": [2, 1]}
    )
    fig.patch.set_facecolor(BG_COLOR)
    for ax in (ax_equity, ax_bars):
        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)

    if not resolved:
        ax_equity.text(0.5, 0.5, "No trades found", color=TEXT_COLOR,
                        ha="center", va="center", transform=ax_equity.transAxes, fontsize=12)
    else:
        cumulative = []
        total = 0.0
        for t in resolved:
            total += t.r_multiple
            cumulative.append(total)

        trade_numbers = list(range(1, len(resolved) + 1))
        line_color = UP_COLOR if cumulative[-1] >= 0 else DOWN_COLOR
        ax_equity.plot(trade_numbers, cumulative, color=line_color, linewidth=1.8, marker="o", markersize=3)
        ax_equity.axhline(0, color=TEXT_COLOR, linewidth=0.6, linestyle="--", alpha=0.5)
        ax_equity.set_title(f"{symbol} — {timeframe} — Backtest Equity Curve (Cumulative R)", color="white", fontsize=12, fontweight="bold")
        ax_equity.set_ylabel("Cumulative R", color=TEXT_COLOR, fontsize=9)

        bar_colors = [UP_COLOR if t.r_multiple > 0 else DOWN_COLOR for t in resolved]
        ax_bars.bar(trade_numbers, [t.r_multiple for t in resolved], color=bar_colors)
        ax_bars.axhline(0, color=TEXT_COLOR, linewidth=0.6, alpha=0.5)
        ax_bars.set_ylabel("R per trade", color=TEXT_COLOR, fontsize=9)
        ax_bars.set_xlabel("Trade #", color=TEXT_COLOR, fontsize=9)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
