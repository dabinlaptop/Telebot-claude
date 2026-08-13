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
    fig, (ax_price, ax_rsi, ax_macd) = plt.subplots(
        3, 1, figsize=(10, 8), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1]}
    )
    fig.patch.set_facecolor("#0f1117")
    for ax in (ax_price, ax_rsi, ax_macd):
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

    # --- RSI ---
    ax_rsi.plot(x, df["rsi"], color="#a855f7", linewidth=1)
    ax_rsi.axhline(70, color="#ef4444", linewidth=0.7, linestyle="--")
    ax_rsi.axhline(30, color="#22c55e", linewidth=0.7, linestyle="--")
    ax_rsi.set_ylabel("RSI", color="#cccccc", fontsize=8)

    # --- MACD ---
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df["macd_hist"].fillna(0)]
    ax_macd.bar(x, df["macd_hist"], color=colors, width=0.0006 * (x.max() - x.min()).total_seconds())
    ax_macd.plot(x, df["macd"], color="#3b82f6", linewidth=0.8)
    ax_macd.plot(x, df["macd_signal"], color="#f59e0b", linewidth=0.8)
    ax_macd.set_ylabel("MACD", color="#cccccc", fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
