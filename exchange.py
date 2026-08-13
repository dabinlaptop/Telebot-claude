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
        """
        raw = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
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
