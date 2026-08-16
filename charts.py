"""
تولید نمودار قیمت + RSI + MACD به‌صورت تصویر PNG
برای ارسال در تلگرام
"""
import matplotlib
matplotlib.use("Agg")  # بدون نیاز به نمایشگر
import matplotlib.pyplot as plt
import pandas as pd
import io


def generate_chart(df: pd.DataFrame, symbol: str, timeframe: str) -> io.BytesIO:
    """
    df باید از قبل شامل ستون‌های اندیکاتور باشه (خروجی add_indicators)
    خروجی: بافر بایتی تصویر PNG آماده ارسال
    """
    fig, (ax_price, ax_volume, ax_rsi, ax_macd) = plt.subplots(
        4, 1, figsize=(10, 9.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 0.8, 1, 1]}
    )
    fig.patch.set_facecolor("#0f1117")
    for ax in (ax_price, ax_volume, ax_rsi, ax_macd):
        ax.set_facecolor("#0f1117")
        ax.tick_params(colors="#cccccc", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#333333")

    x = df["timestamp"]

    # --- نمودار قیمت + EMA + Bollinger ---
    ax_price.plot(x, df["close"], color="#e6e6e6", linewidth=1.2, label="Close")
    ax_price.plot(x, df["ema_fast"], color="#22c55e", linewidth=1, label="EMA Fast")
    ax_price.plot(x, df["ema_slow"], color="#f97316", linewidth=1, label="EMA Slow")
    ax_price.plot(x, df["bb_upper"], color="#3b82f6", linewidth=0.8, alpha=0.6, linestyle="--")
    ax_price.plot(x, df["bb_lower"], color="#3b82f6", linewidth=0.8, alpha=0.6, linestyle="--")
    ax_price.fill_between(x, df["bb_lower"], df["bb_upper"], color="#3b82f6", alpha=0.05)
    ax_price.set_title(f"{symbol} — {timeframe}", color="white", fontsize=12, fontweight="bold")
    ax_price.legend(loc="upper left", fontsize=7, facecolor="#0f1117", labelcolor="white")

    # --- Volume ---
    bar_width = 0.0006 * (x.max() - x.min()).total_seconds()
    vol_colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(df["close"], df["open"])]
    ax_volume.bar(x, df["volume"], color=vol_colors, width=bar_width, alpha=0.8)
    if "volume_sma" in df.columns:
        ax_volume.plot(x, df["volume_sma"], color="#eab308", linewidth=0.8)
    ax_volume.set_ylabel("Volume", color="#cccccc", fontsize=8)

    # --- RSI ---
    ax_rsi.plot(x, df["rsi"], color="#a855f7", linewidth=1)
    ax_rsi.axhline(70, color="#ef4444", linewidth=0.7, linestyle="--")
    ax_rsi.axhline(30, color="#22c55e", linewidth=0.7, linestyle="--")
    ax_rsi.set_ylabel("RSI", color="#cccccc", fontsize=8)

    # --- MACD ---
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df["macd_hist"].fillna(0)]
    ax_macd.bar(x, df["macd_hist"], color=colors, width=bar_width)
    ax_macd.plot(x, df["macd"], color="#3b82f6", linewidth=0.8)
    ax_macd.plot(x, df["macd_signal"], color="#f59e0b", linewidth=0.8)
    ax_macd.set_ylabel("MACD", color="#cccccc", fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_extended_chart(df: pd.DataFrame, symbol: str, timeframe: str, levels: dict | None = None) -> io.BytesIO:
    """
    نمودار مخصوص تحلیل تک‌تایم‌فریمی: قیمت + EMA12/26 + SMA20/50، حجم،
    RSI و MACD. df باید خروجی add_extended_indicators (از single_analysis.py) باشه.
    levels (اختیاری): {"entry": float, "sl": float, "tps": [float, float, float]}
    اگه داده بشه، خطوط ورود/حد ضرر/تارگت‌ها روی پنل قیمت رسم می‌شن.
    """
    fig, (ax_price, ax_volume, ax_rsi, ax_macd) = plt.subplots(
        4, 1, figsize=(10, 9.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 0.8, 1, 1]}
    )
    fig.patch.set_facecolor("#0f1117")
    for ax in (ax_price, ax_volume, ax_rsi, ax_macd):
        ax.set_facecolor("#0f1117")
        ax.tick_params(colors="#cccccc", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#333333")

    x = df["timestamp"]
    bar_width = 0.0006 * (x.max() - x.min()).total_seconds()

    # --- قیمت + میانگین‌های متحرک ---
    ax_price.plot(x, df["close"], color="#e6e6e6", linewidth=1.2, label="Close")
    ax_price.plot(x, df["ema12"], color="#22c55e", linewidth=1, label="EMA12")
    ax_price.plot(x, df["ema26"], color="#f97316", linewidth=1, label="EMA26")
    ax_price.plot(x, df["sma20"], color="#3b82f6", linewidth=1, linestyle="--", label="SMA20")
    ax_price.plot(x, df["sma50"], color="#a855f7", linewidth=1, linestyle="--", label="SMA50")
    if "bb_upper" in df.columns and "bb_lower" in df.columns:
        ax_price.plot(x, df["bb_upper"], color="#64748b", linewidth=0.6, alpha=0.5, linestyle=":")
        ax_price.plot(x, df["bb_lower"], color="#64748b", linewidth=0.6, alpha=0.5, linestyle=":")

    # --- خطوط ورود / حد ضرر / تارگت‌ها ---
    if levels:
        x_start = x.iloc[0]
        x_end = x.iloc[-1]
        if levels.get("entry") is not None:
            ax_price.axhline(levels["entry"], color="#eab308", linewidth=1, linestyle="-")
            ax_price.text(x_end, levels["entry"], " ورود", color="#eab308", fontsize=7, va="center")
        if levels.get("sl") is not None:
            ax_price.axhline(levels["sl"], color="#ef4444", linewidth=1, linestyle="-")
            ax_price.text(x_end, levels["sl"], " SL", color="#ef4444", fontsize=7, va="center")
        for i, tp in enumerate(levels.get("tps") or [], start=1):
            ax_price.axhline(tp, color="#22c55e", linewidth=0.8, linestyle="--", alpha=0.8)
            ax_price.text(x_end, tp, f" TP{i}", color="#22c55e", fontsize=7, va="center")

    ax_price.set_title(f"{symbol} — {timeframe}", color="white", fontsize=12, fontweight="bold")
    ax_price.legend(loc="upper left", fontsize=7, facecolor="#0f1117", labelcolor="white", ncol=3)

    # --- حجم ---
    vol_colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(df["close"], df["open"])]
    ax_volume.bar(x, df["volume"], color=vol_colors, width=bar_width, alpha=0.8)
    ax_volume.set_ylabel("Volume", color="#cccccc", fontsize=8)

    # --- RSI ---
    ax_rsi.plot(x, df["rsi"], color="#a855f7", linewidth=1)
    ax_rsi.axhline(70, color="#ef4444", linewidth=0.7, linestyle="--")
    ax_rsi.axhline(50, color="#666666", linewidth=0.5, linestyle=":")
    ax_rsi.axhline(30, color="#22c55e", linewidth=0.7, linestyle="--")
    ax_rsi.set_ylabel("RSI", color="#cccccc", fontsize=8)

    # --- MACD ---
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df["macd_hist"].fillna(0)]
    ax_macd.bar(x, df["macd_hist"], color=colors, width=bar_width)
    ax_macd.plot(x, df["macd"], color="#3b82f6", linewidth=0.8)
    ax_macd.plot(x, df["macd_signal"], color="#f59e0b", linewidth=0.8)
    ax_macd.set_ylabel("MACD", color="#cccccc", fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
