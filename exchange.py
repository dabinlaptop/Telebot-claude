"""
لایه ارتباط با صرافی (Binance) از طریق ccxt
فقط از endpoint های عمومی استفاده می‌شه - نیازی به API Key نیست
"""
import ccxt.async_support as ccxt
import pandas as pd
from config import EXCHANGE_ID


class ExchangeClient:
    def __init__(self):
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        self.exchange = exchange_class({"enableRateLimit": True})

    async def close(self):
        await self.exchange.close()

    async def fetch_ohlcv_df(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """
        دریافت کندل‌ها و تبدیل به DataFrame
        ستون‌ها: timestamp, open, high, low, close, volume
        پاکسازی دفاعی: مرتب‌سازی زمانی، حذف ردیف‌های تکراری/نامعتبر، و
        محدود کردن به آخرین `limit` کندل معتبر - تا یه ردیف خراب باعث
        کش‌اومدن کل محور زمان نمودار نشه.
        """
        raw = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
        df = df[(df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        df = df.tail(limit).reset_index(drop=True)
        return df

    async def fetch_ticker_price(self, symbol: str) -> float:
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker["last"]

    async def validate_symbol(self, symbol: str) -> bool:
        """چک می‌کنه که نماد روی صرافی وجود داره یا نه"""
        try:
            if not self.exchange.markets:
                await self.exchange.load_markets()
            return symbol in self.exchange.markets
        except Exception:
            return False

    async def load_markets(self):
        await self.exchange.load_markets()

    async def fetch_top_movers(self, top_n: int = 5, min_quote_volume: float = 3_000_000) -> dict:
        """
        برگردوندن پرطرفدارترین ارزهای صعودی و نزولی بر اساس تغییر ۲۴ساعته
        فقط جفت‌های USDT با حجم معاملات کافی در نظر گرفته می‌شن تا نویز حذف بشه.
        خروجی: {"gainers": [...], "losers": [...]}
        """
        tickers = await self.exchange.fetch_tickers()
        usdt_pairs = []
        for symbol, t in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            quote_volume = t.get("quoteVolume") or 0
            change = t.get("percentage")
            if change is None or quote_volume < min_quote_volume:
                continue
            usdt_pairs.append({
                "symbol": symbol,
                "change": change,
                "price": t.get("last"),
                "quote_volume": quote_volume,
            })

        gainers = sorted(usdt_pairs, key=lambda x: x["change"], reverse=True)[:top_n]
        losers = sorted(usdt_pairs, key=lambda x: x["change"])[:top_n]
        return {"gainers": gainers, "losers": losers}


def normalize_symbol(user_input: str) -> str:
    """
    تبدیل ورودی کاربر به فرمت استاندارد ccxt
    مثال: btcusdt -> BTC/USDT ، BTC -> BTC/USDT
    """
    s = user_input.strip().upper().replace("-", "").replace("_", "")
    if "/" in s:
        return s
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT"
    # اگه فقط اسم کوین رو داد (مثل BTC) پیش‌فرض USDT رو می‌ذاریم
    return f"{s}/USDT"
