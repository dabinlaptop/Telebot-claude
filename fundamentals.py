"""
لایه‌ی فاندامنتال سبک - از منابع کاملاً رایگان (بدون نیاز به API Key)

منابع:
- CoinGecko: رنک بازار، مارکت‌کپ، درصد عرضه‌ی در گردش
- Alternative.me: شاخص ترس و طمع کل بازار کریپتو (Fear & Greed Index)
- CoinGecko /global: درصد دامیننس بیت‌کوین

⚠️ این‌ها API های رایگان عمومی‌ان و ریت‌لیمیت محدودی دارن (مخصوصاً
CoinGecko رایگان، حدود ۱۰-۳۰ درخواست در دقیقه). برای همین یه کش
حافظه‌ای ساده (TTL-based) داریم تا اگه چند کاربر هم‌زمان یه نماد رو
بخوان، فقط یه‌بار واقعاً درخواست بزنیم. اگه هر کدوم از این سرویس‌ها در
دسترس نبود یا خطا داد، به‌جای کرش کردن، فقط None برمی‌گردونیم - چون
فاندامنتال صرفاً زمینه‌ی کمکیه، نباید کل سیگنال رو خراب کنه.
"""
import time
import logging
import httpx

from config import (
    COINGECKO_BASE_URL, FEAR_GREED_URL,
    FUNDAMENTALS_CACHE_TTL_COIN, FUNDAMENTALS_CACHE_TTL_MARKET,
)

logger = logging.getLogger(__name__)

_cache: dict = {}
_coin_id_cache: dict = {}

REQUEST_TIMEOUT = 6.0


def _cache_get(key: str, ttl: int):
    entry = _cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > ttl:
        return None
    return value


def _cache_set(key: str, value):
    _cache[key] = (time.time(), value)


async def _find_coingecko_id(base_symbol: str) -> str | None:
    """مثال: 'BTC' -> 'bitcoin'. نتیجه رو دائمی کش می‌کنیم (تغییر نمی‌کنه)."""
    base_symbol = base_symbol.upper()
    if base_symbol in _coin_id_cache:
        return _coin_id_cache[base_symbol]

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{COINGECKO_BASE_URL}/search", params={"query": base_symbol})
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        logger.warning(f"CoinGecko search failed for {base_symbol}: {e}")
        return None

    coins = data.get("coins", [])
    if not coins:
        return None

    exact_matches = [c for c in coins if c.get("symbol", "").upper() == base_symbol]
    candidates = exact_matches if exact_matches else coins
    candidates = [c for c in candidates if c.get("market_cap_rank") is not None]
    if not candidates:
        candidates = exact_matches or coins

    best = min(candidates, key=lambda c: c.get("market_cap_rank") or 999999) if candidates else coins[0]
    coin_id = best.get("id")
    _coin_id_cache[base_symbol] = coin_id
    return coin_id


async def get_coin_fundamentals(symbol: str) -> dict | None:
    """
    symbol مثل 'BTC/USDT' - فقط بخش base (BTC) استفاده می‌شه.
    خروجی: {"rank": int, "market_cap": float, "circulating_supply_pct": float|None, "name": str}
    """
    base = symbol.split("/")[0]
    cache_key = f"coin:{base}"
    cached = _cache_get(cache_key, FUNDAMENTALS_CACHE_TTL_COIN)
    if cached is not None:
        return cached

    coin_id = await _find_coingecko_id(base)
    if not coin_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                f"{COINGECKO_BASE_URL}/coins/{coin_id}",
                params={
                    "localization": "false", "tickers": "false", "market_data": "true",
                    "community_data": "false", "developer_data": "false", "sparkline": "false",
                }
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        logger.warning(f"CoinGecko coin data fetch failed for {coin_id}: {e}")
        return None

    market_data = data.get("market_data", {})
    market_cap = (market_data.get("market_cap") or {}).get("usd")
    circulating = market_data.get("circulating_supply")
    total = market_data.get("total_supply") or market_data.get("max_supply")
    circulating_pct = (circulating / total * 100) if (circulating and total) else None

    result = {
        "name": data.get("name", base),
        "rank": data.get("market_cap_rank"),
        "market_cap": market_cap,
        "circulating_supply_pct": circulating_pct,
    }
    _cache_set(cache_key, result)
    return result


async def get_fear_greed_index() -> dict | None:
    """خروجی: {"value": int 0-100, "classification": str فارسی‌شده}"""
    cache_key = "fear_greed"
    cached = _cache_get(cache_key, FUNDAMENTALS_CACHE_TTL_MARKET)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(FEAR_GREED_URL, params={"limit": 1})
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return None

    entries = data.get("data") or []
    if not entries:
        return None

    value = int(entries[0]["value"])
    classification_map = {
        "Extreme Fear": "ترس شدید 😱", "Fear": "ترس 😨", "Neutral": "خنثی 😐",
        "Greed": "طمع 🤑", "Extreme Greed": "طمع شدید 🚀",
    }
    classification_en = entries[0].get("value_classification", "")
    classification_fa = classification_map.get(classification_en, classification_en)

    result = {"value": value, "classification": classification_fa}
    _cache_set(cache_key, result)
    return result


async def get_btc_dominance() -> float | None:
    """درصد سهم بیت‌کوین از کل مارکت‌کپ بازار کریپتو"""
    cache_key = "btc_dominance"
    cached = _cache_get(cache_key, FUNDAMENTALS_CACHE_TTL_MARKET)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{COINGECKO_BASE_URL}/global")
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception as e:
        logger.warning(f"BTC dominance fetch failed: {e}")
        return None

    try:
        dominance = float(data["data"]["market_cap_percentage"]["btc"])
    except (KeyError, TypeError, ValueError):
        return None

    _cache_set(cache_key, dominance)
    return dominance


async def get_market_fundamentals() -> dict:
    """ترکیب شاخص ترس‌وطمع + دامیننس بیت‌کوین - هر بخشی که خطا بده None می‌مونه."""
    fear_greed = await get_fear_greed_index()
    btc_dominance = await get_btc_dominance()
    return {"fear_greed": fear_greed, "btc_dominance": btc_dominance}
