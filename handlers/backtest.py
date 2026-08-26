from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from exchange import ExchangeClient, normalize_symbol
from backtest import (
    run_backtest, DEFAULT_BACKTEST_CANDLES, MAX_BACKTEST_CANDLES, MIN_BACKTEST_CANDLES,
)
from single_analysis import TIMEFRAME_LABELS_FA
from charts import generate_backtest_chart
import database as db

EXIT_REASON_FA = {
    "SL": "خورد به حد ضرر",
    "TP3": "رسید به TP3",
    "TP2_TIMEOUT": "تا پایان دوره فقط تا TP2 رسید",
    "TP1_TIMEOUT": "تا پایان دوره فقط تا TP1 رسید",
    "TIMEOUT": "بدون رسیدن به هیچ سطحی، دوره تموم شد",
    "STILL_OPEN": "هنوز باز (داده تموم شد) — توی آمار حساب نشده",
}


def _fmt_price(value) -> str:
    if value is None:
        return "-"
    value = float(value)
    if value == 0:
        return "0"
    if value < 0.01:
        return f"{value:,.6f}"
    if value < 1:
        return f"{value:,.4f}"
    return f"{value:,.2f}"


def _format_backtest_result(result) -> str:
    tf_label = TIMEFRAME_LABELS_FA.get(result.timeframe, result.timeframe)
    date_from = str(result.date_from)[:10] if result.date_from is not None else "-"
    date_to = str(result.date_to)[:10] if result.date_to is not None else "-"

    lines = [
        f"📊 *بک‌تست {result.symbol} — {tf_label}*",
        f"بازه: {date_from} تا {date_to} ({result.candles_tested} کندل)",
        "",
    ]

    if result.total_trades == 0:
        lines.append("توی این بازه هیچ سیگنال قطعی‌ای (BUY/SELL) صادر نشد — یعنی بازار توی این محدوده اکثراً رنج/خنثی بوده یا اندیکاتورها هم‌جهت نشدن.")
        if result.still_open_count:
            lines.append(f"\n({result.still_open_count} معامله هنوز باز مونده بود چون داده تموم شد - توی آمار حساب نشده)")
        return "\n".join(lines)

    win_rate = result.win_rate
    avg_r = result.avg_r
    pf = result.profit_factor

    lines += [
        f"🔢 تعداد معاملات: *{result.total_trades}*" + (f" (+{result.still_open_count} هنوز باز)" if result.still_open_count else ""),
        f"✅ برد: {result.wins} | ❌ باخت: {result.losses}",
        f"📈 نرخ برد: *{win_rate:.1f}%*" if win_rate is not None else "📈 نرخ برد: -",
        f"⚖️ میانگین R هر معامله: *{avg_r:+.2f}*" if avg_r is not None else "",
        f"💰 مجموع R: *{result.total_r:+.2f}*",
        f"🎯 Profit Factor: *{pf:.2f}*" if pf is not None else "🎯 Profit Factor: بی‌نهایت (بدون ضرر)",
        f"📉 بیشترین باخت‌های پیاپی: {result.max_consecutive_losses}",
        "",
        "📋 چند معامله‌ی آخر:",
    ]
    for t in result.trades[-5:]:
        reason_fa = EXIT_REASON_FA.get(t.exit_reason, t.exit_reason)
        dir_emoji = "🟢" if t.direction == "BUY" else "🔴"
        lines.append(f"{dir_emoji} {t.direction} @ ${_fmt_price(t.entry)} → {reason_fa} (R={t.r_multiple:+.2f})")

    lines += [
        "",
        "⚠️ *روش‌شناسی*: ورود فرضی با قیمت باز شدن کندل بعد از سیگنال؛ اگه "
        "توی یه کندل هم SL و هم TP لمس بشن، محافظه‌کارانه فرض می‌کنیم SL "
        "اول خورده. این یه شبیه‌سازی روی داده‌ی گذشته‌ست، نه تضمین عملکرد آینده.",
    ]
    return "\n".join(l for l in lines if l is not None)


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "استفاده: `/backtest SYMBOL [تایم‌فریم] [تعداد کندل]`\n"
            f"مثال: `/backtest BTCUSDT 4h 300`\n\n"
            f"تایم‌فریم پیش‌فرض: `1h` — تعداد کندل پیش‌فرض: `{DEFAULT_BACKTEST_CANDLES}` "
            f"(بین {MIN_BACKTEST_CANDLES} تا {MAX_BACKTEST_CANDLES})",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = normalize_symbol(context.args[0])
    timeframe = context.args[1] if len(context.args) > 1 else "1h"

    candles = DEFAULT_BACKTEST_CANDLES
    if len(context.args) > 2:
        if not context.args[2].isdigit():
            await update.message.reply_text("تعداد کندل باید عدد باشه.")
            return
        candles = int(context.args[2])
        candles = max(MIN_BACKTEST_CANDLES, min(MAX_BACKTEST_CANDLES, candles))

    msg = await update.message.reply_text(
        f"⏳ در حال بک‌تست {symbol} روی {TIMEFRAME_LABELS_FA.get(timeframe, timeframe)} "
        f"با {candles} کندل تاریخی... (چند ثانیه طول می‌کشه)"
    )

    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await msg.edit_text(f"❌ نماد `{symbol}` روی صرافی پیدا نشد.", parse_mode=ParseMode.MARKDOWN)
            return

        df = await client.fetch_ohlcv_df(symbol, timeframe, limit=candles)
        if len(df) < MIN_BACKTEST_CANDLES:
            await msg.edit_text(
                f"⚠️ فقط {len(df)} کندل تاریخچه در دسترسه (حداقل {MIN_BACKTEST_CANDLES} تا لازمه). "
                f"یه تایم‌فریم کوچیک‌تر یا نماد پرسابقه‌تر امتحان کن.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        confidence_threshold = await db.get_float_setting("confidence_threshold_fraction", 0.25)
        atr_sl_mult = await db.get_float_setting("atr_sl_mult", 1.5)
        rr_targets_raw = await db.get_setting("rr_targets")
        rr_targets = None
        if rr_targets_raw:
            try:
                rr_targets = [float(x.strip()) for x in rr_targets_raw.split(",")]
            except ValueError:
                rr_targets = None

        result = run_backtest(
            df, symbol, timeframe,
            confidence_threshold_fraction=confidence_threshold,
            atr_sl_mult=atr_sl_mult, rr_targets=rr_targets,
        )

        text = _format_backtest_result(result)
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

        if result.total_trades > 0:
            chart_buf = generate_backtest_chart(result.trades, symbol, timeframe)
            await update.message.reply_photo(photo=chart_buf)

    except Exception as e:
        await msg.edit_text(f"❌ خطا در بک‌تست: {e}")
    finally:
        await client.close()
