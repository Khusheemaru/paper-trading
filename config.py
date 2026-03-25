import os
from dotenv import load_dotenv
from typing import List, Dict

# Load secrets from .env
load_dotenv()

# =============================================================================
#  DATA SOURCE TOGGLE
#  Set USE_MOCK_DATA=True  -> Fast, correlated synthetic simulator (100ms ticks)
#  Set USE_MOCK_DATA=False -> Real market data via yfinance (2s delay, 15min delayed)
# =============================================================================
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "TRUE").lower() == "true"
DATA_SOURCE = "mock" if USE_MOCK_DATA else "live"

# Tick interval in seconds for the mock simulator
TICK_INTERVAL = float(os.getenv("TICK_INTERVAL", "0.1"))
# Interval in seconds for the live yfinance fetcher (2s to avoid IP bans)
LIVE_FETCH_INTERVAL = float(os.getenv("LIVE_FETCH_INTERVAL", "2.0"))

# =============================================================================
#  MULTI-ASSET CONFIG
#  Each asset has:
#    - yf_ticker: Yahoo Finance ticker string (used in LIVE mode)
#    - base_price: Starting price for the mock simulator
#    - volatility: How much the price swings each tick in MOCK mode
#    - asset_class: Used by Portfolio Analytics for risk modeling
# =============================================================================
ASSET_CONFIG: Dict[str, dict] = {
    "NIFTY": {
        "yf_ticker": "^NSEI",
        "base_price": 24500.0,
        "volatility": 15.0,   # High - equity index
        "asset_class": "Equity",
    },
    "RELIANCE": {
        "yf_ticker": "RELIANCE.NS",
        "base_price": 2950.0,
        "volatility": 8.0,    # High - individual stock
        "asset_class": "Equity",
    },
    "GOLD": {
        "yf_ticker": "GC=F",
        "base_price": 6200.0,
        "volatility": 4.0,    # Medium - commodity
        "asset_class": "Commodity",
    },
    "BONDS": {
        "yf_ticker": "^TNX",    # US 10Y Treasury Yield (proxy for bond price)
        "base_price": 450.0,
        "volatility": 0.8,    # Low - fixed income
        "asset_class": "FixedIncome",
    },
}

SYMBOLS: List[str] = list(ASSET_CONFIG.keys())
PRIMARY_SYMBOL = SYMBOLS[0]  # "NIFTY" - used as default when a specific symbol is not requested

# =============================================================================
#  DEFAULT ACCOUNT SETTINGS
# =============================================================================
DEFAULT_INITIAL_CAPITAL = float(os.getenv("DEFAULT_INITIAL_CAPITAL", "1000000"))  # ₹10,00,000

# =============================================================================
#  DATABASE (PostgreSQL)
# =============================================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "algo_trading")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = os.getenv("DB_PORT", "5432")

# =============================================================================
#  IN-MEMORY CACHE (Redis)
# =============================================================================
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# =============================================================================
#  AUTHENTICATION (JWT)
# =============================================================================
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# =============================================================================
#  LOGGING
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# =============================================================================
#  HELPERS
# =============================================================================
def is_mock_mode() -> bool:
    return USE_MOCK_DATA

def get_asset_config(symbol: str) -> dict:
    """Returns the config for a given symbol, raising KeyError if unknown."""
    if symbol not in ASSET_CONFIG:
        raise KeyError(f"Unknown symbol: {symbol}. Valid symbols: {SYMBOLS}")
    return ASSET_CONFIG[symbol]