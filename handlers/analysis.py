from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from exchange import ExchangeClient, normalize_symbol
from signals import analyze_symbol, SIGNAL_EMOJI, SIGNAL_FA
from single_analysis import (
    add_extended_indicators, build_single_result, TIMEFRAME_LABELS_FA,
    MIN_CANDLES_FOR_ANALYSIS, MIN_CANDLES_REQUIRED
)
from charts import generate_extended_chart
from market_context import check_higher_timeframe_alignment, check_btc_correlation
from fundamentals import get_coin_fundamentals, get_market_fundamentals
import database as db


# ---------- کیبوردهای شیشه‌ای ----------

def _timeframe_keyboard(symbol: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("۱ دقیقه", callback_data=f"tf:{symbol}:1m"),
            InlineKeyboardButton("۵ دقیقه", callback_data=f"tf:{symbol}:5m"),
        ],
        [
            InlineKeyboardButton("۱۵ دقیقه", callback_data=f"tf:{symbol}:15m"),
            InlineKeyboardButton("۳۰ دقیقه", callback_data=f"tf:{symbol}:30m"),
        ],
        [
            InlineKeyboardButton("۱ ساعته", callback_data=f"tf:{symbol}:1h"),
            InlineKeyboardButton("۴ ساعته", callback_data=f"tf:{symbol}:4h"),
        ],
        [
            InlineKeyboardButton("روزانه", callback_data=f"tf:{symbol}:1d"),
            InlineKeyboardButton("هفتگی", callback_data=f"tf:{symbol}:1w"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _result_keyboard(symbol: str, timeframe: str, pending_id: int = None) -> InlineKeyboardMarkup:
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
    if pending_id is not None:
        buttons.append([
            InlineKeyboardButton("📌 پیگیری این سیگنال", callback_data=f"track:{pending_id}"),
            InlineKeyboardButton("❌ پیگیری نکن", callback_data=f"notrack:{pending_id}"),
        ])
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


def _calc_position_size(risk_settings: dict, entry: float, sl: float, volatility_risk_mult: float = 1.0) -> dict | None:
    """
    با داشتن موجودی فرضی و درصد ریسک کاربر (از /setrisk)، حجم پوزیشن رو
    محاسبه می‌کنه: مقدار ریسک دلاری = موجودی × درصد ریسک؛ حجم = ریسک ÷
    فاصله‌ی ورود تا حد ضرر (روش استاندارد مدیریت ریسک با % ثابت).

    اگه بازار توی رژیم نوسان بالا/شدید باشه (volatility_risk_mult < 1)،
    مقدار ریسک دلاری رو خودکار کمتر می‌کنیم - چون نوسان بیشتر یعنی
    فاصله‌ی SL هم معمولاً بزرگ‌تره، ولی این جدا از اون، یه لایه‌ی احتیاط
    اضافه‌ست: توی بازار پرنوسان، حتی با همون % ریسک همیشگی، بهتره
    حجم واقعی رو کمتر بگیری.
    """
    if not risk_settings or not entry or not sl:
        return None
    balance = risk_settings["account_balance"]
    risk_percent = risk_settings["risk_percent"]
    risk_amount = balance * risk_percent / 100 * volatility_risk_mult
    per_unit_risk = abs(entry - sl)
    if per_unit_risk <= 0:
        return None
    units = risk_amount / per_unit_risk
    position_value = units * entry
    return {
        "risk_amount": risk_amount,
        "units": units,
        "position_value": position_value,
        "risk_percent": risk_percent,
        "balance": balance,
        "volatility_adjusted": volatility_risk_mult < 1.0,
    }


def _format_single_result(result, higher_tf_info: dict = None, btc_corr_info: dict = None,
                           position_size: dict = None, order_book_info: dict = None,
                           coin_fundamentals: dict = None, market_fundamentals: dict = None) -> str:
    meta = DIRECTION_META[result.direction]
    tf_label = TIMEFRAME_LABELS_FA.get(result.timeframe, result.timeframe)
    reason_icon = "✅" if result.direction == "BUY" else "❌"
    change_arrow = "📈" if result.price_change_24h_percent >= 0 else "📉"

    if result.adx >= 25:
        trend_strength = f"قوی 💪 ({result.adx:.0f})"
    elif result.adx >= 15:
        trend_strength = f"متوسط ({result.adx:.0f})"
    else:
        trend_strength = f"ضعیف/رنج ({result.adx:.0f})"

    lines = [
        f"💎 {result.symbol}",
        f"{meta['emoji']} {meta['fa']}",
        f"🕰 تایم‌فریم: {tf_label}",
        f"📊 اطمینان: {result.confidence_percent}% (امتیاز {result.score:+.1f} از {result.max_score:.0f})",
        f"🧭 جهت: {meta['compass']}",
        f"💪 قدرت روند (ADX): {trend_strength}",
        f"🌪 نوسان بازار: {result.volatility_level}" + (f" (صدک {result.volatility_percentile:.0f})" if result.volatility_percentile is not None else ""),
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

    context_lines = []
    if higher_tf_info:
        htf_label = TIMEFRAME_LABELS_FA.get(higher_tf_info["higher_tf"], higher_tf_info["higher_tf"])
        if higher_tf_info["aligned"]:
            context_lines.append(f"✅ هم‌جهت با روند تایم‌فریم {htf_label}")
        else:
            opp = "صعودی" if higher_tf_info["higher_tf_direction"] == "BUY" else "نزولی"
            context_lines.append(f"⚠️ روند تایم‌فریم {htf_label} مخالفه ({opp}) — احتیاط بیشتر")

    if btc_corr_info:
        corr_pct = btc_corr_info["correlation"] * 100
        if btc_corr_info["high_correlation"]:
            context_lines.append(f"🔗 همبستگی بالا با BTC ({corr_pct:.0f}%) — ممکنه این سیگنال صرفاً دنبال‌کننده‌ی بازار باشه، نه قدرت مستقل این ارز")
        else:
            context_lines.append(f"🔓 همبستگی پایین با BTC ({corr_pct:.0f}%) — حرکت نسبتاً مستقل از بازار کلی")

    if order_book_info:
        bid_pct = order_book_info["bid_ratio"] * 100
        from config import ORDER_BOOK_IMBALANCE_THRESHOLD
        if order_book_info["bid_ratio"] >= ORDER_BOOK_IMBALANCE_THRESHOLD:
            context_lines.append(f"📚 اردربوک: فشار خرید بیشتر ({bid_pct:.0f}% حجم سفارش‌ها)")
        elif order_book_info["bid_ratio"] <= (1 - ORDER_BOOK_IMBALANCE_THRESHOLD):
            context_lines.append(f"📚 اردربوک: فشار فروش بیشتر ({100-bid_pct:.0f}% حجم سفارش‌ها)")
        else:
            context_lines.append(f"📚 اردربوک: نسبتاً متعادل (خرید {bid_pct:.0f}%)")

    if result.fib_confirmation:
        context_lines.append(f"🔢 حد ضرر {result.fib_confirmation} — اعتبار بیشتر")

    if context_lines:
        lines += ["", "🌐 زمینه‌ی بازار:"] + [f"• {c}" for c in context_lines]

    fundamental_lines = []
    if coin_fundamentals:
        rank_txt = f"#{coin_fundamentals['rank']}" if coin_fundamentals.get("rank") else "نامشخص"
        fundamental_lines.append(f"رنک بازار: {rank_txt}")
        if coin_fundamentals.get("circulating_supply_pct") is not None:
            fundamental_lines.append(f"عرضه‌ی در گردش: {coin_fundamentals['circulating_supply_pct']:.0f}% از کل")
    if market_fundamentals:
        fg = market_fundamentals.get("fear_greed")
        if fg:
            fundamental_lines.append(f"شاخص ترس‌وطمع بازار: {fg['value']} ({fg['classification']})")
        dom = market_fundamentals.get("btc_dominance")
        if dom is not None:
            fundamental_lines.append(f"دامیننس بیت‌کوین: {dom:.1f}%")

    if fundamental_lines:
        lines += ["", "🏛 فاندامنتال:"] + [f"• {f}" for f in fundamental_lines]

    if result.direction != "NEUTRAL":
        lines += [
            "",
            f"🎯 نقطه ورود پیشنهادی: ${_fmt_price(result.entry)}",
        ]
        if result.entry_basis:
            lines.append(f"   بر پایه: {result.entry_basis}")
        lines += [
            "",
            f"🛡 حد ضرر (SL): ${_fmt_price(result.sl)}",
            f"   بر پایه: {result.sl_basis}",
            "",
            "🎯 تارگت‌های سود:",
        ]
        for i, tp in enumerate(result.tps, start=1):
            rr = abs(tp - result.entry) / result.risk if result.risk else 0
            lines.append(f"• TP{i} (۱:{rr:.1f}): ${_fmt_price(tp)}")
        lines.append("ℹ️ بعد از رسیدن به TP1، حد ضرر خودکار به نقطه‌ی سربه‌سر منتقل می‌شه (اگه پیگیریش کنی).")

        if position_size:
            vol_note = " (به‌خاطر نوسان بالای بازار، حجم کاهش داده شد ⚠️)" if position_size.get("volatility_adjusted") else ""
            lines += [
                "",
                f"📐 حجم پوزیشن پیشنهادی (ریسک {position_size['risk_percent']:.1f}% از ${position_size['balance']:,.0f}){vol_note}:",
                f"• مقدار: {position_size['units']:,.4f} واحد (~${position_size['position_value']:,.2f})",
                f"• ریسک دلاری: ${position_size['risk_amount']:,.2f}",
            ]
        else:
            lines += ["", "ℹ️ برای محاسبه‌ی خودکار حجم پوزیشن، از `/setrisk موجودی درصد‌ریسک` استفاده کن (مثال: `/setrisk 1000 2`)"]

    if result.reasons:
        lines += ["", "📋 دلایل:"]
        for text in result.reasons:
            lines.append(f"{reason_icon} {text}")
    else:
        lines += ["", "📋 اندیکاتورها به‌قدر کافی هم‌جهت نبودن، سیگنال قطعی وجود نداره."]

    lines.append("\n⚠️ توصیه مالی نیست — همیشه مدیریت ریسک و حجم پوزیشن با خودته.")
    if result.direction != "NEUTRAL":
        lines.append("📌 اگه می‌خوای نتیجه‌ی این سیگنال رو پیگیری کنم (برای آمار `/mystats`)، دکمه‌ی زیر رو بزن.")
    return "\n".join(lines)


# ---------- منطق مشترک تحلیل تک‌تایم‌فریمی (توسط دستور و کال‌بک استفاده می‌شه) ----------

async def run_single_timeframe_signal(symbol: str, timeframe: str, user_id: int = None):
    """
    خروجی: (متن پیام, بافر تصویر نمودار, کیبورد)
    اگه نماد نامعتبر بود: (None, None, None)
    اگه نماد معتبر بود ولی داده‌ی تاریخی کافی نداشت (مثلاً یه کوین تازه
    روی تایم‌فریم هفتگی): (متن هشدار, None, None) - یعنی chart_buf رو
    نساز و نفرست، چون بر پایه‌ی اندیکاتورهای ناقص گمراه‌کننده می‌شه
    """
    client = ExchangeClient()
    try:
        if not await client.validate_symbol(symbol):
            return None, None, None

        df = await client.fetch_ohlcv_df(symbol, timeframe, limit=MIN_CANDLES_FOR_ANALYSIS)

        if len(df) < MIN_CANDLES_REQUIRED:
            tf_label = TIMEFRAME_LABELS_FA.get(timeframe, timeframe)
            warn_text = (
                f"⚠️ برای `{symbol}` روی تایم‌فریم {tf_label} فقط {len(df)} کندل تاریخچه "
                f"در دسترسه (حداقل {MIN_CANDLES_REQUIRED} تا لازمه تا اندیکاتورها معتبر باشن).\n\n"
                f"یه تایم‌فریم کوچیک‌تر امتحان کن یا از «⏱ تغییر تایم‌فریم» استفاده کن."
            )
            return warn_text, None, None

        df = add_extended_indicators(df)

        # تنظیمات قابل تغییر از پنل وب (اگه ادمین چیزی تغییر نداده باشه، مقادیر پیش‌فرض استفاده می‌شن)
        confidence_threshold = await db.get_float_setting("confidence_threshold_fraction", 0.25)
        atr_sl_mult = await db.get_float_setting("atr_sl_mult", 1.5)
        rr_targets_raw = await db.get_setting("rr_targets")
        rr_targets = None
        if rr_targets_raw:
            try:
                rr_targets = [float(x.strip()) for x in rr_targets_raw.split(",")]
            except ValueError:
                rr_targets = None

        result = build_single_result(
            df, symbol, timeframe,
            confidence_threshold_fraction=confidence_threshold,
            atr_sl_mult=atr_sl_mult, rr_targets=rr_targets
        )

        try:
            ticker = await client.exchange.fetch_ticker(symbol)
            result.quote_volume_24h = float(ticker.get("quoteVolume") or 0.0)
            result.price_change_24h_percent = float(ticker.get("percentage") or 0.0)
            result.liquidity_level = _classify_liquidity(result.quote_volume_24h)
        except Exception:
            pass

        higher_tf_info = None
        btc_corr_info = None
        order_book_info = None
        if result.direction != "NEUTRAL":
            try:
                higher_tf_info = await check_higher_timeframe_alignment(client, symbol, timeframe, result.direction)
            except Exception:
                pass
            try:
                btc_corr_info = await check_btc_correlation(client, symbol, timeframe)
            except Exception:
                pass
            try:
                from config import ORDER_BOOK_DEPTH_LEVELS
                order_book_info = await client.fetch_order_book_imbalance(symbol, depth=ORDER_BOOK_DEPTH_LEVELS)
            except Exception:
                pass

        # فاندامنتال (منابع رایگان، best-effort - اگه در دسترس نبود، فقط حذف می‌شه از پیام)
        coin_fundamentals = None
        market_fundamentals = None
        from config import FUNDAMENTALS_ENABLED
        if FUNDAMENTALS_ENABLED:
            try:
                coin_fundamentals = await get_coin_fundamentals(symbol)
            except Exception:
                pass
            try:
                market_fundamentals = await get_market_fundamentals()
            except Exception:
                pass

        position_size = None
        if user_id is not None and result.direction != "NEUTRAL":
            risk_settings = await db.get_user_risk(user_id)
            position_size = _calc_position_size(risk_settings, result.entry, result.sl, result.volatility_risk_mult)

        await db.log_signal(symbol, result.direction, result.confidence_percent, result.price)

        # به‌جای ثبت خودکار برای پایش، فقط یه رکورد موقت می‌سازیم و از
        # کاربر با دکمه می‌پرسیم که واقعاً می‌خواد پیگیریش کنه یا نه
        pending_id = None
        if user_id is not None and result.direction != "NEUTRAL":
            pending_id = await db.create_pending_signal(
                user_id, symbol, timeframe, result.direction, result.entry, result.sl, result.tps
            )

        text = _format_single_result(
            result, higher_tf_info, btc_corr_info, position_size,
            order_book_info, coin_fundamentals, market_fundamentals
        )
        levels = None
        if result.direction != "NEUTRAL":
            levels = {"entry": result.entry, "sl": result.sl, "tps": result.tps}
            if result.support is not None and result.resistance is not None:
                from config import FIBONACCI_LEVELS
                diff = result.resistance - result.support
                if diff > 0:
                    levels["fib_levels"] = {f: result.resistance - diff * f for f in FIBONACCI_LEVELS}
        chart_buf = generate_extended_chart(df, symbol, timeframe, levels=levels)
        keyboard = _result_keyboard(symbol, timeframe, pending_id=pending_id)
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
