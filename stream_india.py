"""
stream_india.py — Multi-Asset Market Data Pipeline

MOCK Mode: Generates correlated synthetic tick data for all 4 asset classes
           simultaneously at 10 ticks/second. Prices follow real financial
           correlations (equities are volatile, bonds are stable, gold
           inversely correlates with equity drops).

LIVE Mode:  Fetches real market data using yfinance every 2 seconds to avoid
            rate limits. Provides 15-minute delayed prices for NSE/BSE assets.
            Both modes push identical Redis key structures so the rest of the
            application never needs to know which mode is active.
"""

import config
import redis
import time
import random
import json
import logging
from database import DatabaseHandler

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("STREAMER")

# --- CONNECTIONS ---
db = DatabaseHandler()

try:
    if config.REDIS_URL:
        r = redis.from_url(config.REDIS_URL, decode_responses=True)
    else:
        r = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
        )
    r.ping()
    logger.info(f"✅ [REDIS] Connected to {config.REDIS_HOST}:{config.REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ [REDIS] Connection Failed: {e}")
    exit(1)


def push_to_redis(symbol: str, price: float, bid: float, ask: float, spread: float) -> None:
    """Batch push all price keys for one symbol to Redis atomically."""
    pipe = r.pipeline()
    pipe.set(f"price:{symbol}", round(price, 2))
    pipe.set(f"bid:{symbol}",   round(bid, 2))
    pipe.set(f"ask:{symbol}",   round(ask, 2))
    pipe.set(f"spread:{symbol}", round(spread, 2))
    pipe.execute()


def save_tick(symbol: str, price: float, bid: float, ask: float, volume: int) -> None:
    """Persist a market tick to PostgreSQL for history queries."""
    try:
        db.insert_tick(symbol, price, bid, ask, volume)
    except Exception as e:
        logger.warning(f"[DB] Tick insert failed for {symbol}: {e}")


def get_target_mode() -> str:
    """Reads the current mode toggle from Redis. Defaults to config if not set."""
    val = r.get("APP_MODE:USE_MOCK")
    if val is None:
        return "mock" if config.is_mock_mode() else "live"
    return "mock" if val == "true" else "live"


# =============================================================================
# MODE A — MOCK (Correlated Synthetic Simulator)
# =============================================================================

def run_mock_stream():
    logger.info("🤖 [MODE: MOCK] Starting Multi-Asset Correlated Simulator...")

    # Working price state for each asset — starts at configured base price
    prices = {symbol: cfg["base_price"] for symbol, cfg in config.ASSET_CONFIG.items()}

    tick_count = 0

    while True:
        if get_target_mode() == "live":
            logger.info("🤖 [MODE: MOCK] Mode switch detected. Shutting down Mock Stream...")
            break
            
        try:
            tick_count += 1
            
            # Fetch dynamic tickers from Redis
            dynamic_symbols = r.smembers("APP:DYNAMIC_TICKERS") or set()
            for ds in dynamic_symbols:
                if ds not in prices:
                    prices[ds] = 1000.0  # Safe default mock start

            # Combine static config and dynamic symbols for uniform looping
            # (If a dynamic symbol lacks config, mock handles it gracefully)
            all_symbols = list(config.SYMBOLS) + list(dynamic_symbols)

            # ---------------------------------------------------------------
            # 1. Generate a "market shock" for equity direction this tick
            #    This single random number drives correlation:
            #      - Equities move WITH the market shock
            #      - Gold moves AGAINST it (safe haven hedge)
            #      - Bonds move very slightly and independently
            # ---------------------------------------------------------------
            equity_shock = random.gauss(0, 1)  # standard normal: mean 0, std 1

            for symbol in all_symbols:
                cfg = config.ASSET_CONFIG.get(symbol, {"volatility": 15.0, "asset_class": "Equity", "base_price": 1000.0})
                vol = cfg["volatility"]
                asset_class = cfg["asset_class"]

                if asset_class == "Equity":
                    # Equities strongly track the equity shock
                    change = equity_shock * vol * random.uniform(0.8, 1.2)

                elif asset_class == "Commodity":
                    # Gold has an inverse correlation to equities (flight to safety)
                    # When equity_shock < 0 (market drops), gold tends to rise
                    gold_shock = -equity_shock * 0.6 + random.gauss(0, 0.4)
                    change = gold_shock * vol

                else:  # FixedIncome
                    # Bonds are mostly independent and very low volatility
                    change = random.gauss(0, vol)

                # Apply the change, and prevent prices going below a floor
                floor = cfg["base_price"] * 0.3
                prices[symbol] = max(floor, prices[symbol] + change)

                price = prices[symbol]

                # Simulate a realistic bid/ask spread for this asset class
                if asset_class == "Equity":
                    spread = random.uniform(0.50, 2.50)
                elif asset_class == "Commodity":
                    spread = random.uniform(1.00, 4.00)
                else:
                    spread = random.uniform(0.10, 0.50)

                bid = price - (spread / 2)
                ask = price + (spread / 2)
                volume = random.randint(50, 500)

                # Push to Redis and persist to DB
                push_to_redis(symbol, price, bid, ask, spread)

                # Only write to DB every 10th tick to reduce disk I/O
                if tick_count % 10 == 0:
                    save_tick(symbol, price, bid, ask, volume)

            # Log a summary row every 50 ticks (~5 seconds) to keep terminal clean
            if tick_count % 50 == 0:
                summary = " | ".join(
                    f"{s}: ₹{prices[s]:,.2f}" for s in all_symbols[:6] # Display up to 6
                )
                logger.info(f"[MOCK] {summary}{'...' if len(all_symbols) > 6 else ''}")

            time.sleep(config.TICK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("⛔ [STOP] Simulator stopped by user.")
            break
        except Exception as e:
            logger.error(f"[ERROR] {e}")
            time.sleep(1)


# =============================================================================
# MODE B — LIVE (Yahoo Finance / yfinance, 15-minute delayed)
# =============================================================================

def run_live_stream():
    try:
        import yfinance as yf
        import time as _time
    except ImportError:
        logger.error("❌ 'yfinance' not installed. Run: venv\\Scripts\\pip install yfinance")
        return

    logger.info("🌐 [MODE: LIVE] Starting yfinance Multi-Asset Stream (fast_info mode)...")

    # Pre-build Ticker base once
    base_symbol_to_ticker = {
        symbol: cfg["yf_ticker"]
        for symbol, cfg in config.ASSET_CONFIG.items()
    }
    logger.info(f"   Base Polling: {', '.join(base_symbol_to_ticker.values())} every ~{config.LIVE_FETCH_INTERVAL:.0f}s")

    while True:
        if get_target_mode() == "mock":
            logger.info("🌐 [MODE: LIVE] Mode switch detected. Shutting down Live Stream...")
            break
            
        try:
            # 1. Rebuild dict with dynamic components dynamically inserted
            dynamic_symbols = r.smembers("APP:DYNAMIC_TICKERS") or set()
            symbol_to_ticker = dict(base_symbol_to_ticker)
            for ds in dynamic_symbols:
                symbol_to_ticker[ds] = f"{ds}.NS"
                
            for symbol, yf_ticker in symbol_to_ticker.items():
                try:
                    # MUST re-instantiate Ticker inside the loop to bypass yfinance's fast_info cache
                    ticker_obj = yf.Ticker(yf_ticker)
                    info = ticker_obj.fast_info

                    price = float(info.last_price)
                    if price is None or price <= 0:
                        logger.warning(f"[LIVE] No valid price for {symbol} ({yf_ticker}).")
                        continue

                    # Use 52-week range to estimate a realistic spread for this asset
                    try:
                        fifty_two_week_range = float(info.fifty_two_week_high) - float(info.fifty_two_week_low)
                        spread_estimate = max(0.01, fifty_two_week_range * 0.0005)
                    except Exception:
                        spread_estimate = price * 0.0002  # fallback: 0.02% of price

                    bid = price - (spread_estimate / 2)
                    ask = price + (spread_estimate / 2)
                    volume = int(getattr(info, "three_month_average_volume", 0) or 0)

                    push_to_redis(symbol, price, bid, ask, spread_estimate)
                    save_tick(symbol, price, bid, ask, volume)

                    logger.info(f"[LIVE] {symbol} ({yf_ticker}): {price:,.4f}")

                except Exception as e:
                    logger.warning(f"[LIVE] Error fetching {symbol}: {e}")

                # Small delay between tickers to avoid rate-limiting
                _time.sleep(0.5)

            # Sleep between full cycles
            _time.sleep(config.LIVE_FETCH_INTERVAL)

        except KeyboardInterrupt:
            logger.info("⛔ [STOP] Live stream stopped by user.")
            break
        except Exception as e:
            logger.error(f"[ERROR] {e}")
            _time.sleep(10)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    logger.info("🚀 Market Data Streamer process started.")
    try:
        while True:
            mode = get_target_mode()
            if mode == "mock":
                run_mock_stream()
            else:
                run_live_stream()
            
            # Small delay between switches to avoid spinning if errors occur early
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Overall streamer process terminated by user.")