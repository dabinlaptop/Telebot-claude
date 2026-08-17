"""
موتور تحلیل حرفه‌ای تک‌تایم‌فریمی

روش کار:
هر اندیکاتور یه رأی وزن‌دار (bull/bear/neutral) میده. جمع امتزار وزن‌دار
جهت غالب رو مشخص می‌کنه و درصد اطمینان از نسبت |امتیاز کل| به حداکثر
امتیاز ممکن به دست میاد. فقط اندیکاتورهایی که هم‌جهت با سیگنال نهایی
هستن توی لیست «دلایل» نمایش داده می‌شن.

اندیکاتورها و وزن‌شون:
- EMA 12/26 Cross          وزن 2   (تقاطع کوتاه‌مدت/میان‌مدت)
- روند EMA50 (فیلتر روند)   وزن 1   (قیمت بالا/پایین EMA50)
- SMA 20/50 Trend          وزن 2   (روند میان‌مدت)
- MACD Cross               وزن 1
- MACD Histogram Momentum  وزن 1   (هیستوگرام در حال قوی‌تر شدنه یا ضعیف‌تر)
- RSI Zone                 وزن 1   (بالای ۵۵ صعودی، زیر ۴۵ نزولی، بینابین خنثی)
- موقعیت باند بولینگر       وزن 1   (نزدیکی به باند بالا/پایین)
- اسپایک حجم                وزن 1   (هم‌جهت با کندل آخر)
- روند OBV                 وزن 1   (جریان تجمعی پول - تاییدکننده‌ی مهم)
- الگوی کندل‌استیک          وزن 1

حداکثر امتیاز ممکن = 2+1+2+1+1+1+1+1+1+1 = 12

حد ضرر (SL): ترکیب ATR و آخرین Swing High/Low - هرکدوم منطقی‌تر و
نزدیک‌تر به ساختار قیمت بود انتخاب می‌شه (نه صرفاً یه ضریب ثابت).

تارگت‌های سود (TP1/TP2/TP3): بر پایه‌ی نسبت ریسک‌به‌ریوارد ۱:۱، ۱:۲، ۱:۳
نسبت به فاصله‌ی ورود تا حد ضرر (R-multiple) - روش استاندارد مدیریت ریسک
در معامله‌گری حرفه‌ای.
"""
from dataclasses import dataclass, field
import pandas as pd

SWING_LOOKBACK = 20          # تعداد کندل برای تشخیص آخرین سقف/کف
ATR_SL_MULT = 1.5            # ضریب پیش‌فرض ATR برای حد ضرر
MAX_STRUCTURE_SL_ATR_MULT = 3.0  # حداکثر فاصله‌ی مجاز SL ساختاری (بر حسب ATR) تا غیرمنطقی نشه
RR_TARGETS = [1.0, 2.0, 3.0]     # نسبت‌های ریسک‌به‌ریوارد برای TP1/TP2/TP3

ENTRY_PULLBACK_ATR_MULT = 0.3      # فاصله‌ی پیش‌فرض ورود پیشنهادی از قیمت فعلی (بر حسب ATR)
MAX_ENTRY_PULLBACK_ATR_MULT = 1.2  # حداکثر فاصله‌ی مجاز پولبک تا EMA12 (وگرنه غیرواقعی می‌شه)

MIN_CANDLES_FOR_ANALYSIS = 100

TIMEFRAME_LABELS_FA = {
    "15m": "۱۵ دقیقه",
    "1h": "۱ ساعته",
    "4h": "۴ ساعته",
    "1d": "روزانه",
}


def add_extended_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """محاسبه‌ی همه‌ی اندیکاتورهای لازم برای موتور حرفه‌ای"""
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, EMAIndicator, SMAIndicator
    from ta.volatility import AverageTrueRange, BollingerBands
    from ta.volume import OnBalanceVolumeIndicator

    close = df["close"]

    df["rsi"] = RSIIndicator(close=close, window=14).rsi()

    macd_calc = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd_calc.macd()
    df["macd_signal"] = macd_calc.macd_signal()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    df["sma20"] = SMAIndicator(close=close, window=20).sma_indicator()
    df["sma50"] = SMAIndicator(close=close, window=50).sma_indicator()
    df["ema12"] = EMAIndicator(close=close, window=12).ema_indicator()
    df["ema26"] = EMAIndicator(close=close, window=26).ema_indicator()
    df["ema50"] = EMAIndicator(close=close, window=50).ema_indicator()

    df["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=close, window=14).average_true_range()

    from ta.trend import ADXIndicator
    adx_calc = ADXIndicator(high=df["high"], low=df["low"], close=close, window=14)
    df["adx"] = adx_calc.adx()

    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()

    df["obv"] = OnBalanceVolumeIndicator(close=close, volume=df["volume"]).on_balance_volume()

    df["volume_sma"] = df["volume"].rolling(window=20).mean()

    return df


# ---------- تشخیص الگوی کندل‌استیک (سبک و مستقل، بدون نیاز به ta) ----------

def _detect_last_candle_pattern(df: pd.DataFrame) -> dict | None:
    """بررسی ۲ کندل آخر برای الگوهای پرکاربرد؛ خروجی {"name":.., "bias": 1|-1} یا None"""
    if len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]

    last_body = abs(last["close"] - last["open"])
    last_range = last["high"] - last["low"]
    prev_body = abs(prev["close"] - prev["open"])
    if last_range == 0:
        return None

    upper_wick = last["high"] - max(last["close"], last["open"])
    lower_wick = min(last["close"], last["open"]) - last["low"]
    last_bullish = last["close"] > last["open"]
    prev_bullish = prev["close"] > prev["open"]

    if prev_body > 0:
        if (not prev_bullish and last_bullish
                and last["close"] >= prev["open"] and last["open"] <= prev["close"]
                and last_body > prev_body):
            return {"name": "پوشای صعودی (Bullish Engulfing)", "bias": 1}
        if (prev_bullish and not last_bullish
                and last["open"] >= prev["close"] and last["close"] <= prev["open"]
                and last_body > prev_body):
            return {"name": "پوشای نزولی (Bearish Engulfing)", "bias": -1}

    if last_body > 0 and last_body / last_range < 0.35:
        if lower_wick > last_body * 2 and upper_wick < last_body * 0.5:
            return {"name": "چکش (Hammer)", "bias": 1}
        if upper_wick > last_body * 2 and lower_wick < last_body * 0.5:
            return {"name": "ستاره‌ی تیرانداز (Shooting Star)", "bias": -1}

    return None


# ---------- محاسبه‌ی نقطه‌ی ورود پیشنهادی (نه صرفاً قیمت لحظه‌ای) ----------

def _suggest_entry(price: float, atr: float, direction: str, ema12: float) -> tuple[float, str]:
    """
    به‌جای پیشنهاد قیمت لحظه‌ای به‌عنوان نقطه‌ی ورود (که یعنی خرید/فروش در
    همون لحظه، بدون فاصله از نوسان آنی)، یه نقطه‌ی ورود کمی منطقی‌تر
    پیشنهاد می‌ده: یا پولبک به EMA12 (اگه فاصله‌ش معقول بود)، یا حداقل
    یه فاصله‌ی کوچیک (۰.۳ ATR) از قیمت فعلی - تا در اوج/کف لحظه‌ای وارد نشی.
    """
    if direction == "BUY":
        buffer_entry = price - ENTRY_PULLBACK_ATR_MULT * atr
        if ema12 and 0 < (price - ema12) <= MAX_ENTRY_PULLBACK_ATR_MULT * atr:
            entry = max(buffer_entry, ema12)  # هرکدوم به قیمت نزدیک‌تره (احتمال پرشدن سفارش بیشتر)
            basis = f"پولبک به EMA12 (${ema12:,.4f})" if ema12 < 1 else f"پولبک به EMA12 (${ema12:,.2f})"
        else:
            entry = buffer_entry
            basis = f"{ENTRY_PULLBACK_ATR_MULT}× ATR پایین‌تر از قیمت فعلی (اجتناب از ورود در اوج لحظه‌ای)"
        return entry, basis

    if direction == "SELL":
        buffer_entry = price + ENTRY_PULLBACK_ATR_MULT * atr
        if ema12 and 0 < (ema12 - price) <= MAX_ENTRY_PULLBACK_ATR_MULT * atr:
            entry = min(buffer_entry, ema12)
            basis = f"پولبک به EMA12 (${ema12:,.4f})" if ema12 < 1 else f"پولبک به EMA12 (${ema12:,.2f})"
        else:
            entry = buffer_entry
            basis = f"{ENTRY_PULLBACK_ATR_MULT}× ATR بالاتر از قیمت فعلی (اجتناب از ورود در کف لحظه‌ای)"
        return entry, basis

    return price, None


# ---------- محاسبه‌ی سطوح ورود/حد ضرر/تارگت ----------

def _calc_levels(df: pd.DataFrame, price: float, atr: float, direction: str, ema12: float) -> dict:
    """
    محاسبه‌ی نقطه‌ی ورود پیشنهادی، حد ضرر (ترکیب ATR و Swing High/Low) و
    ۳ تارگت سود بر پایه‌ی R-multiple (نسبت به فاصله‌ی ورود تا حد ضرر)
    """
    recent = df.tail(SWING_LOOKBACK)
    swing_low = float(recent["low"].min())
    swing_high = float(recent["high"].max())

    entry, entry_basis = _suggest_entry(price, atr, direction, ema12)

    if direction == "BUY":
        atr_sl = entry - ATR_SL_MULT * atr
        structure_sl = swing_low - 0.3 * atr
        # اگه حد ضرر ساختاری منطقی‌تر (نزدیک‌تر به قیمت) و در بازه‌ی معقول بود، اون رو انتخاب کن
        if structure_sl < entry and (entry - structure_sl) <= MAX_STRUCTURE_SL_ATR_MULT * atr:
            sl = structure_sl
            sl_basis = "زیر آخرین کف قیمتی (Swing Low)"
        else:
            sl = atr_sl
            sl_basis = f"{ATR_SL_MULT}× ATR"
        risk = entry - sl
        tps = [entry + risk * rr for rr in RR_TARGETS]
    elif direction == "SELL":
        atr_sl = entry + ATR_SL_MULT * atr
        structure_sl = swing_high + 0.3 * atr
        if structure_sl > entry and (structure_sl - entry) <= MAX_STRUCTURE_SL_ATR_MULT * atr:
            sl = structure_sl
            sl_basis = "بالای آخرین سقف قیمتی (Swing High)"
        else:
            sl = atr_sl
            sl_basis = f"{ATR_SL_MULT}× ATR"
        risk = sl - entry
        tps = [entry - risk * rr for rr in RR_TARGETS]
    else:
        entry, entry_basis, sl, sl_basis, tps, risk = price, None, None, None, [], None

    return {
        "entry": entry, "entry_basis": entry_basis, "sl": sl, "sl_basis": sl_basis,
        "tps": tps, "risk": risk, "support": swing_low, "resistance": swing_high,
    }


# ---------- نتیجه‌ی نهایی ----------

@dataclass
class SingleTFResult:
    symbol: str
    timeframe: str
    price: float
    rsi: float
    macd: float
    macd_signal: float
    sma20: float
    sma50: float
    ema12: float
    ema26: float
    ema50: float
    atr: float
    adx: float
    score: float
    max_score: float
    direction: str  # "BUY" | "SELL" | "NEUTRAL"
    reasons: list = field(default_factory=list)
    pattern: dict | None = None
    entry: float = 0.0
    entry_basis: str = None
    sl: float = None
    sl_basis: str = None
    tps: list = field(default_factory=list)
    risk: float = None
    quote_volume_24h: float = 0.0
    price_change_24h_percent: float = 0.0
    liquidity_level: str = "نامشخص"

    @property
    def confidence_percent(self) -> int:
        if self.max_score == 0:
            return 0
        return int(min(abs(self.score) / self.max_score, 1.0) * 100)

    @property
    def risk_reward_text(self) -> str:
        return "۱:۱ / ۱:۲ / ۱:۳"


def _classify_liquidity(quote_volume_24h: float) -> str:
    if quote_volume_24h >= 50_000_000:
        return "بالا 🟢"
    if quote_volume_24h >= 5_000_000:
        return "متوسط 🟡"
    return "پایین 🔴 (ریسک اسپرد/لغزش قیمت بیشتر)"


def build_single_result(df: pd.DataFrame, symbol: str, timeframe: str) -> SingleTFResult:
    """df باید خروجی add_extended_indicators باشه (شامل حداقل ۵۰ کندل معتبر)"""
    last = df.iloc[-1]
    price = float(last["close"])
    atr = float(last["atr"]) if not pd.isna(last["atr"]) else 0.0

    pattern = _detect_last_candle_pattern(df)

    # هر آیتم: (وزن, حالت صعودی؟, متن دلیل صعودی, متن دلیل نزولی, دسته)
    # دسته‌ی "trend" یعنی این اندیکاتور صرفاً یه نمای دیگه از همون روند
    # قیمته (به‌شدت با بقیه‌ی دسته‌ی trend هم‌بسته‌ست) - این‌ها بعداً توی
    # پیام به یه خط ترکیبی خلاصه می‌شن تا لیست دلایل برای ارزهای مختلف
    # یکسان و تکراری به‌نظر نرسه. دسته‌ی "unique" یعنی سیگنال مستقل و
    # متمایزکننده‌ست (این‌ها همیشه جدا نمایش داده می‌شن).
    votes = []

    votes.append((2, last["ema12"] > last["ema26"], "کراس صعودی EMA 12/26", "کراس نزولی EMA 12/26", "trend"))

    if not pd.isna(last["ema50"]):
        votes.append((1, price > last["ema50"], "قیمت بالای EMA50 (روند صعودی)", "قیمت زیر EMA50 (روند نزولی)", "trend"))

    votes.append((2, last["sma20"] > last["sma50"], "روند صعودی SMA (20>50)", "روند نزولی SMA (20<50)", "trend"))

    votes.append((1, last["macd"] > last["macd_signal"], "کراس صعودی MACD", "کراس نزولی MACD", "trend"))

    if len(df) >= 4 and not df["macd_hist"].iloc[-3:].isna().any():
        hist_trend_up = df["macd_hist"].iloc[-1] > df["macd_hist"].iloc[-3]
        votes.append((1, hist_trend_up, "هیستوگرام MACD در حال تقویت", "هیستوگرام MACD در حال تضعیف", "trend"))

    rsi_val = float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0
    if rsi_val >= 55:
        votes.append((1, True, f"RSI در ناحیه‌ی صعودی ({rsi_val:.1f})", "", "unique"))
    elif rsi_val <= 45:
        votes.append((1, False, "", f"RSI در ناحیه‌ی نزولی ({rsi_val:.1f})", "unique"))
    # بین ۴۵ تا ۵۵: رأی نمی‌ده (خنثی)

    if not pd.isna(last["bb_upper"]) and not pd.isna(last["bb_lower"]):
        band_width = last["bb_upper"] - last["bb_lower"]
        if band_width > 0:
            dist_lower = abs(price - last["bb_lower"]) / band_width
            dist_upper = abs(price - last["bb_upper"]) / band_width
            if dist_lower < 0.15:
                votes.append((1, True, "قیمت نزدیک باند پایین بولینگر (اشباع فروش)", "", "unique"))
            elif dist_upper < 0.15:
                votes.append((1, False, "", "قیمت نزدیک باند بالای بولینگر (اشباع خرید)", "unique"))

    if not pd.isna(last["volume_sma"]) and last["volume_sma"] > 0 and len(df) >= 21:
        if last["volume"] >= last["volume_sma"] * 1.5:
            candle_bull = last["close"] > last["open"]
            votes.append((1, candle_bull, "اسپایک حجم هم‌جهت با کندل صعودی", "اسپایک حجم هم‌جهت با کندل نزولی", "unique"))

    if len(df) >= 15 and not df["obv"].iloc[-15:].isna().any():
        obv_trend_up = df["obv"].iloc[-1] > df["obv"].iloc[-15]
        votes.append((1, obv_trend_up, "روند صعودی OBV (تایید جریان پول خرید)", "روند نزولی OBV (تایید جریان پول فروش)", "unique"))

    if pattern:
        if pattern["bias"] > 0:
            votes.append((1, True, f"الگوی کندلی: {pattern['name']}", "", "unique"))
        elif pattern["bias"] < 0:
            votes.append((1, False, "", f"الگوی کندلی: {pattern['name']}", "unique"))

    score = 0.0
    max_score = 0.0
    for weight, is_bull, bull_text, bear_text, category in votes:
        max_score += weight
        if is_bull:
            score += weight
        else:
            score -= weight

    # آستانه: حداقل ۲۵٪ از حداکثر امتیاز فاصله از صفر لازمه تا سیگنال قطعی صادر بشه
    threshold = max_score * 0.25
    if score >= threshold:
        direction = "BUY"
    elif score <= -threshold:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    reasons = []
    if direction in ("BUY", "SELL"):
        matching_trend = []
        matching_unique = []
        for weight, is_bull, bull_text, bear_text, category in votes:
            matches_direction = (direction == "BUY" and is_bull) or (direction == "SELL" and not is_bull)
            if not matches_direction:
                continue
            text = bull_text if direction == "BUY" else bear_text
            if not text:
                continue
            if category == "trend":
                matching_trend.append(text)
            else:
                matching_unique.append(text)

        # اگه ۳ یا بیشتر اندیکاتور روندی هم‌جهت بودن (که خیلی وقت‌ها توی
        # بازار پرروند اتفاق می‌افته)، به‌جای تکرار تک‌تک، یه خط ترکیبی
        # می‌سازیم تا پیام برای ارزهای مختلف متمایزتر به‌نظر برسه و
        # اندیکاتورهای منحصربه‌فرد (RSI/OBV/حجم/الگو) بیشتر دیده بشن.
        if len(matching_trend) >= 3:
            dir_word = "صعودی" if direction == "BUY" else "نزولی"
            reasons.append(f"روند {dir_word} در {len(matching_trend)} اندیکاتور (EMA/SMA/MACD) تایید شد")
        else:
            reasons.extend(matching_trend)

        # دلایل منحصربه‌فرد رو اول لیست می‌ذاریم چون اطلاعات بیشتری دارن
        reasons = matching_unique + reasons

    adx_val = float(last["adx"]) if not pd.isna(last.get("adx", float("nan"))) else 0.0
    levels = _calc_levels(df, price, atr, direction, float(last["ema12"]) if not pd.isna(last["ema12"]) else None)

    return SingleTFResult(
        symbol=symbol,
        timeframe=timeframe,
        price=price,
        rsi=rsi_val,
        macd=float(last["macd"]) if not pd.isna(last["macd"]) else 0.0,
        macd_signal=float(last["macd_signal"]) if not pd.isna(last["macd_signal"]) else 0.0,
        sma20=float(last["sma20"]) if not pd.isna(last["sma20"]) else 0.0,
        sma50=float(last["sma50"]) if not pd.isna(last["sma50"]) else 0.0,
        ema12=float(last["ema12"]) if not pd.isna(last["ema12"]) else 0.0,
        ema26=float(last["ema26"]) if not pd.isna(last["ema26"]) else 0.0,
        ema50=float(last["ema50"]) if not pd.isna(last["ema50"]) else 0.0,
        atr=atr,
        adx=adx_val,
        score=score,
        max_score=max_score,
        direction=direction,
        reasons=reasons,
        pattern=pattern,
        entry=levels["entry"],
        entry_basis=levels["entry_basis"],
        sl=levels["sl"],
        sl_basis=levels["sl_basis"],
        tps=levels["tps"],
        risk=levels["risk"],
    )
