"""
market_data.py — Historical OHLCV Data Provider

Fetches candlestick (Open/High/Low/Close/Volume) data for all supported assets.

MOCK mode: Generates synthetic OHLCV candles from the existing tick data stored
           in PostgreSQL (groups ticks into 1-minute candles).

LIVE mode: Downloads real historical OHLCV data via yfinance (30 days of daily
           candles or 5 days of 1-minute intraday candles depending on range).
"""

import logging
import config
from database import DatabaseHandler

logger = logging.getLogger("MARKET_DATA")
db = DatabaseHandler()


def get_mock_candles(symbol: str, limit: int = 200) -> list[dict]:
    """
    Builds 1-minute OHLCV candles by aggregating raw tick data from PostgreSQL.
    Groups ticks by 1-minute buckets and computes O/H/L/C for each.
    """
    try:
        # Fetch raw ticks from DB — more ticks = more candles
        raw_ticks = db.get_recent_ticks(symbol, limit=limit * 10)
        if not raw_ticks:
            return []

        # Sort chronologically
        raw_ticks = sorted(raw_ticks, key=lambda r: r["time"])

        # Group into 1-minute buckets
        buckets: dict[int, list[float]] = {}
        for tick in raw_ticks:
            # Round timestamp down to the nearest minute
            ts = int(tick["time"].timestamp())
            minute_ts = (ts // 60) * 60
            price = float(tick["price"])
            buckets.setdefault(minute_ts, []).append(price)

        # Build OHLCV candles from each bucket
        candles = []
        for ts_minute, prices in sorted(buckets.items()):
            candles.append({
                "time":   ts_minute,
                "open":   round(prices[0],   2),
                "high":   round(max(prices),  2),
                "low":    round(min(prices),  2),
                "close":  round(prices[-1],   2),
                "volume": len(prices) * 100,  # proxy volume
            })

        return candles[-limit:]  # Return the most recent candles

    except Exception as e:
        logger.error(f"[MOCK CANDLES] Error for {symbol}: {e}")
        return []


def get_live_candles(symbol: str, days: int = 5) -> list[dict]:
    """
    Fetches real OHLCV data from yfinance.
    - Uses 1-minute interval for up to 7 days of recent data.
    - Falls back to daily candles for longer ranges.
    """
    try:
        import yfinance as yf

        cfg = config.ASSET_CONFIG.get(symbol)
        if not cfg:
            logger.warning(f"[LIVE CANDLES] Unknown symbol: {symbol}")
            return []

        yf_ticker = cfg["yf_ticker"]
        ticker = yf.Ticker(yf_ticker)

        # 1-min bars are only available for ≤7 days on yfinance
        if days <= 5:
            hist = ticker.history(period=f"{days}d", interval="1m", auto_adjust=True)
        else:
            hist = ticker.history(period=f"{min(days, 60)}d", interval="1d", auto_adjust=True)

        if hist.empty:
            logger.warning(f"[LIVE CANDLES] No data for {symbol} ({yf_ticker})")
            return []

        candles = []
        for ts, row in hist.iterrows():
            # yfinance returns timezone-aware timestamps; convert to Unix int
            unix_ts = int(ts.timestamp())
            candles.append({
                "time":   unix_ts,
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row.get("Volume", 0)),
            })

        logger.info(f"[LIVE CANDLES] {symbol}: {len(candles)} candles loaded from yfinance")
        return candles

    except Exception as e:
        logger.error(f"[LIVE CANDLES] Error for {symbol}: {e}")
        return []


def get_candles(symbol: str, days: int = 5) -> list[dict]:
    """
    Main entry point. Automatically uses MOCK or LIVE based on config.
    Always returns a list of candle dicts with time/open/high/low/close/volume keys.
    """
    if symbol not in config.SYMBOLS:
        logger.warning(f"[CANDLES] Invalid symbol: {symbol}")
        return []

    if config.is_mock_mode():
        return get_mock_candles(symbol, limit=300)
    else:
        return get_live_candles(symbol, days=days)
