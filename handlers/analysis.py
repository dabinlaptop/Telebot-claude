from telegram import Update
from telegram.ext import ContextTypes
from exchange import ExchangeClient, normalize_symbol
from signals import analyze_symbol, SIGNAL_EMOJI, SIGNAL_FA
from indicators import add_indicators
from charts import generate_chart
import database as db


def _format_signal_message(result) -> str:
    emoji = SIGNAL_EMOJI[result.signal_type]
    fa = SIGNAL_FA[result.signal_type]

    lines = [
        f"{emoji} *{result.symbol}*",
        f"قیمت فعلی: `{result.current_price:,.4f}`",
        f"نتیجه: *{fa}*",
        f"امتیاز کل: `{result.total_score}` از `{result.max_possible_score}` (اطمینان ~{result.confidence_percent}%)",
        "",
        "📊 *جزئیات هر تایم‌فریم:*",
    ]
    for tf in result.timeframe_results:
        arrow = "↑" if tf.raw_score > 0 else ("↓" if tf.raw_score < 0 else "→")
        lines.append(
            f"• `{tf.timeframe}` {arrow} امتیاز خام: {tf.raw_score:+d} | RSI: {tf.rsi_value:.1f} | MACD hist: {tf.macd_hist:+.4f}"
        )
    lines.append("\n⚠️ توصیه مالی نیست — همیشه ریسک خودت رو مدیریت کن.")
    return "\n".join(lines)


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/signal BTCUSDT`", parse_mode="Markdown")
        return

    symbol = normalize_symbol(context.args[0])
    msg = await update.message.reply_text(f"⏳ در حال تحلیل {symbol} روی چند تایم‌فریم...")

    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await msg.edit_text(f"❌ نماد `{symbol}` روی صرافی پیدا نشد.", parse_mode="Markdown")
            return
        result = await analyze_symbol(client, symbol)
        await db.log_signal(symbol, result.signal_type, result.total_score, result.current_price)
        await msg.edit_text(_format_signal_message(result), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ خطا در تحلیل: {e}")
    finally:
        await client.close()


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "لطفاً نماد رو وارد کن. مثال: `/chart BTCUSDT` یا `/chart BTCUSDT 4h`",
            parse_mode="Markdown"
        )
        return

    symbol = normalize_symbol(context.args[0])
    timeframe = context.args[1] if len(context.args) > 1 else "1h"

    msg = await update.message.reply_text(f"⏳ در حال ساخت نمودار {symbol} ({timeframe})...")

    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await msg.edit_text(f"❌ نماد `{symbol}` پیدا نشد.", parse_mode="Markdown")
            return
        df = await client.fetch_ohlcv_df(symbol, timeframe, limit=100)
        df = add_indicators(df)
        chart_buf = generate_chart(df, symbol, timeframe)
        await update.message.reply_photo(photo=chart_buf)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ خطا در ساخت نمودار: {e}")
    finally:
        await client.close()


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/price BTCUSDT`", parse_mode="Markdown")
        return

    symbol = normalize_symbol(context.args[0])
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await update.message.reply_text(f"❌ نماد `{symbol}` پیدا نشد.", parse_mode="Markdown")
            return
        price = await client.fetch_ticker_price(symbol)
        await update.message.reply_text(f"💰 *{symbol}*: `{price:,.4f}` USDT", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")
    finally:
        await client.close()


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import DEFAULT_SYMBOLS
    msg = await update.message.reply_text("⏳ در حال تحلیل سریع ارزهای پرطرفدار...")

    client = ExchangeClient()
    lines = []
    try:
        for symbol in DEFAULT_SYMBOLS:
            try:
                result = await analyze_symbol(client, symbol)
                emoji = SIGNAL_EMOJI[result.signal_type]
                lines.append(f"{emoji} *{symbol}*: {SIGNAL_FA[result.signal_type]} (`{result.total_score}`)")
            except Exception:
                lines.append(f"⚠️ {symbol}: خطا در دریافت داده")
        await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    finally:
        await client.close()
