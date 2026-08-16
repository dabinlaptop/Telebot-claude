from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from exchange import ExchangeClient, normalize_symbol
from signals import analyze_symbol, SIGNAL_EMOJI, SIGNAL_FA
from single_analysis import (
    add_extended_indicators, build_single_result, TIMEFRAME_LABELS_FA,
    MIN_CANDLES_FOR_ANALYSIS, RR_TARGETS
)
from charts import generate_chart, generate_extended_chart
import database as db


# ---------- کیبوردهای شیشه‌ای ----------

def _timeframe_keyboard(symbol: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("۱۵ دقیقه", callback_data=f"tf:{symbol}:15m"),
            InlineKeyboardButton("۱ ساعته", callback_data=f"tf:{symbol}:1h"),
        ],
        [
            InlineKeyboardButton("۴ ساعته", callback_data=f"tf:{symbol}:4h"),
            InlineKeyboardButton("روزانه", callback_data=f"tf:{symbol}:1d"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _result_keyboard(symbol: str, timeframe: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"tf:{symbol}:{timeframe}"),
            InlineKeyboardButton("⏱ تغییر تایم‌فریم", callback_data=f"chtf:{symbol}"),
        ],
        [
            InlineKeyboardButton("⭐ افزودن به واچ‌لیست", callback_data=f"watch:{symbol}"),
            InlineKeyboardButton("💰 قیمت لحظه‌ای", callback_data=f"price:{symbol}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# ---------- فرمت‌دهی ----------

def _fmt_price(value) -> str:
    """دقت اعشار رو متناسب با بزرگی قیمت تنظیم می‌کنه (کوین‌های ریزقیمت دقت بیشتری لازم دارن)"""
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


DIRECTION_META = {
    "BUY": {"emoji": "🟢", "fa": "سیگنال خرید (BUY)", "compass": "📈 LONG"},
    "SELL": {"emoji": "🔴", "fa": "سیگنال فروش (SELL)", "compass": "📉 SHORT"},
    "NEUTRAL": {"emoji": "⚪️", "fa": "سیگنال خنثی (NEUTRAL)", "compass": "↔️ بدون موقعیت"},
}


def _format_single_result(result) -> str:
    meta = DIRECTION_META[result.direction]
    tf_label = TIMEFRAME_LABELS_FA.get(result.timeframe, result.timeframe)
    reason_icon = "✅" if result.direction == "BUY" else "❌"
    change_arrow = "📈" if result.price_change_24h_percent >= 0 else "📉"

    lines = [
        f"{meta['emoji']} {meta['fa']}",
        f"🕰 تایم‌فریم: {tf_label}",
        f"📊 اطمینان: {result.confidence_percent}% (امتیاز {result.score:+.1f} از {result.max_score:.0f})",
        f"🧭 جهت: {meta['compass']}",
        "",
        f"💰 قیمت فعلی: ${_fmt_price(result.price)}",
        f"💧 نقدینگی (۲۴س): ${result.quote_volume_24h:,.0f} — {result.liquidity_level}",
        f"{change_arrow} تغییر ۲۴ساعته: {result.price_change_24h_percent:+.2f}%",
        "",
        "📊 اندیکاتورها:",
        f"• RSI: {result.rsi:.2f}",
        f"• MACD: {result.macd:.5f}",
        f"• SMA20: ${_fmt_price(result.sma20)} | SMA50: ${_fmt_price(result.sma50)}",
        f"• EMA12: ${_fmt_price(result.ema12)} | EMA26: ${_fmt_price(result.ema26)} | EMA50: ${_fmt_price(result.ema50)}",
        f"• ATR: ${_fmt_price(result.atr)}",
    ]

    if result.pattern:
        lines.append(f"• 🕯 الگوی کندلی: {result.pattern['name']}")

    if result.direction != "NEUTRAL":
        lines += [
            "",
            f"🎯 نقطه ورود: ${_fmt_price(result.entry)}",
            "",
            f"🛡 حد ضرر (SL): ${_fmt_price(result.sl)}",
            f"   بر پایه: {result.sl_basis}",
            "",
            "🎯 تارگت‌های سود:",
        ]
        for i, (tp, rr) in enumerate(zip(result.tps, RR_TARGETS), start=1):
            lines.append(f"• TP{i} (۱:{rr:.0f}): ${_fmt_price(tp)}")

    if result.reasons:
        lines += ["", "📋 دلایل:"]
        for text in result.reasons:
            lines.append(f"{reason_icon} {text}")
    else:
        lines += ["", "📋 اندیکاتورها به‌قدر کافی هم‌جهت نبودن، سیگنال قطعی وجود نداره."]

    lines.append("\n⚠️ توصیه مالی نیست — همیشه مدیریت ریسک و حجم پوزیشن با خودته.")
    return "\n".join(lines)


# ---------- منطق مشترک تحلیل تک‌تایم‌فریمی (توسط دستور و کال‌بک استفاده می‌شه) ----------

async def run_single_timeframe_signal(symbol: str, timeframe: str):
    """
    خروجی: (متن پیام, بافر تصویر نمودار, کیبورد) یا (None, None, None) اگه نماد نامعتبر بود
    """
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            return None, None, None

        df = await client.fetch_ohlcv_df(symbol, timeframe, limit=MIN_CANDLES_FOR_ANALYSIS)
        df = add_extended_indicators(df)
        result = build_single_result(df, symbol, timeframe)

        # اطلاعات نقدینگی و تغییر ۲۴ساعته از تیکر صرافی
        try:
            ticker = await client.exchange.fetch_ticker(symbol)
            result.quote_volume_24h = float(ticker.get("quoteVolume") or 0.0)
            result.price_change_24h_percent = float(ticker.get("percentage") or 0.0)
            result.liquidity_level = _classify_liquidity(result.quote_volume_24h)
        except Exception:
            pass

        await db.log_signal(symbol, result.direction, result.confidence_percent, result.price)

        text = _format_single_result(result)
        levels = {"entry": result.entry, "sl": result.sl, "tps": result.tps} if result.direction != "NEUTRAL" else None
        chart_buf = generate_extended_chart(df, symbol, timeframe, levels=levels)
        keyboard = _result_keyboard(symbol, timeframe)
        return text, chart_buf, keyboard
    finally:
        await client.close()


def _classify_liquidity(quote_volume_24h: float) -> str:
    if quote_volume_24h >= 50_000_000:
        return "بالا 🟢"
    if quote_volume_24h >= 5_000_000:
        return "متوسط 🟡"
    return "پایین 🔴 (ریسک اسپرد/لغزش قیمت بیشتر)"


# ---------- دستورات ----------

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/signal BTCUSDT`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = normalize_symbol(context.args[0])
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await update.message.reply_text(f"❌ نماد `{symbol}` روی صرافی پیدا نشد.", parse_mode=ParseMode.MARKDOWN)
            return
    finally:
        await client.close()

    await update.message.reply_text(
        f"⏱ برای «{symbol}» کدوم تایم‌فریم رو تحلیل کنم؟",
        reply_markup=_timeframe_keyboard(symbol)
    )


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "لطفاً نماد رو وارد کن. مثال: `/chart BTCUSDT` یا `/chart BTCUSDT 4h`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = normalize_symbol(context.args[0])
    timeframe = context.args[1] if len(context.args) > 1 else "1h"
    await _send_basic_chart(update.message, symbol, timeframe)


async def _send_basic_chart(message, symbol: str, timeframe: str):
    msg = await message.reply_text(f"⏳ در حال ساخت نمودار {symbol} ({timeframe})...")
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            await msg.edit_text(f"❌ نماد `{symbol}` پیدا نشد.", parse_mode=ParseMode.MARKDOWN)
            return
        df = await client.fetch_ohlcv_df(symbol, timeframe, limit=100)
        df = add_extended_indicators(df)
        chart_buf = generate_extended_chart(df, symbol, timeframe)
        await message.reply_photo(photo=chart_buf)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ خطا در ساخت نمودار: {e}")
    finally:
        await client.close()


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("لطفاً نماد رو وارد کن. مثال: `/price BTCUSDT`", parse_mode=ParseMode.MARKDOWN)
        return
    symbol = normalize_symbol(context.args[0])
    text = await _get_price_text(symbol)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def _get_price_text(symbol: str) -> str:
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            return f"❌ نماد `{symbol}` پیدا نشد."
        price = await client.fetch_ticker_price(symbol)
        return f"💰 *{symbol}*: `${_fmt_price(price)}`"
    except Exception as e:
        return f"❌ خطا: {e}"
    finally:
        await client.close()


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مرور سریع چندتایم‌فریمی چند ارز پرطرفدار - برای دید کلی، نه تصمیم معاملاتی دقیق"""
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
        lines.append("\nℹ️ برای تحلیل دقیق با نقطه ورود/SL/TP از `/signal SYMBOL` استفاده کن.")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    finally:
        await client.close()


async def gainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پرسودترین و پرضررترین ارزهای ۲۴ساعت گذشته (با فیلتر نقدینگی حداقلی)"""
    msg = await update.message.reply_text("⏳ در حال دریافت لیست بازار...")
    client = ExchangeClient()
    try:
        movers = await client.fetch_top_movers(top_n=5)
        lines = ["📈 *بیشترین رشد ۲۴ساعته:*"]
        for m in movers["gainers"]:
            lines.append(f"🟢 `{m['symbol']}` `{m['change']:+.2f}%` — قیمت: `${_fmt_price(m['price'])}`")
        lines.append("\n📉 *بیشترین افت ۲۴ساعته:*")
        for m in movers["losers"]:
            lines.append(f"🔴 `{m['symbol']}` `{m['change']:+.2f}%` — قیمت: `${_fmt_price(m['price'])}`")
        lines.append("\nℹ️ فقط جفت‌های با حجم معاملات کافی (نقدینگی بالاتر) نمایش داده می‌شن.")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await msg.edit_text(f"❌ خطا در دریافت لیست بازار: {e}")
    finally:
        await client.close()
