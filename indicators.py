"""
indicators.py — Pure Technical Indicator Functions

Design Principles:
- Stateless: no DB access, no Redis, no global state
- Deterministic: identical input → identical output (required by HedgeBot's simulation contract)
- Boundary-safe: returns None when insufficient data (engine must handle this gracefully)
- Extensible: add new indicators by registering in INDICATOR_REGISTRY

Used by strategy_engine.py to evaluate user-defined rule conditions.
Compatible with Python 3.11+.
"""

import math
from typing import Dict, List, Optional, Union

# Type alias for a price series (chronological, oldest first)
PriceSeries = List[float]
IndicatorResult = Optional[Union[float, Dict[str, float]]]


# =============================================================================
# Simple Moving Average
# =============================================================================

def sma(prices: PriceSeries, period: int) -> Optional[float]:
    """
    Simple Moving Average of the last `period` prices.

    Args:
        prices: Chronological price list (oldest → newest)
        period: Lookback window

    Returns:
        Float SMA value, or None if len(prices) < period
    """
    if len(prices) < period or period <= 0:
        return None
    window = prices[-period:]
    return round(sum(window) / period, 4)


# =============================================================================
# Exponential Moving Average
# =============================================================================

def ema(prices: PriceSeries, period: int) -> Optional[float]:
    """
    Exponential Moving Average using the standard k=2/(period+1) multiplier.
    Seeds from the SMA of the first `period` values.

    Args:
        prices: Chronological price list (oldest → newest)
        period: Lookback window

    Returns:
        Float EMA value, or None if len(prices) < period
    """
    if len(prices) < period or period <= 0:
        return None

    k = 2.0 / (period + 1)
    # Seed: SMA of the first `period` data points
    ema_val = sum(prices[:period]) / period
    # Apply EMA smoothing to remaining prices
    for price in prices[period:]:
        ema_val = price * k + ema_val * (1.0 - k)
    return round(ema_val, 4)


# =============================================================================
# Relative Strength Index (Wilder's Smoothing)
# =============================================================================

def rsi(prices: PriceSeries, period: int = 14) -> Optional[float]:
    """
    Relative Strength Index using Wilder's exponential smoothing method.
    Standard definition: requires period + 1 price points minimum.

    Args:
        prices: Chronological price list (oldest → newest)
        period: RSI lookback period (default 14)

    Returns:
        Float RSI in range [0, 100], or None if insufficient data
    """
    if len(prices) < period + 1 or period <= 0:
        return None

    # Price changes (deltas)
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Seed: simple average of first `period` gains / losses
    seed_gains  = [max(c, 0.0) for c in changes[:period]]
    seed_losses = [abs(min(c, 0.0)) for c in changes[:period]]

    avg_gain = sum(seed_gains)  / period
    avg_loss = sum(seed_losses) / period

    # Wilder's smoothing for all subsequent deltas
    for change in changes[period:]:
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0.0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 4)


# =============================================================================
# MACD (Moving Average Convergence Divergence)
# =============================================================================

def macd(
    prices: PriceSeries,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Optional[Dict[str, float]]:
    """
    MACD indicator: MACD line, Signal line, Histogram.

    Args:
        prices:        Chronological price series
        fast_period:   Fast EMA period (default 12)
        slow_period:   Slow EMA period (default 26)
        signal_period: Signal line EMA period (default 9)

    Returns:
        Dict { "macd": float, "signal": float, "histogram": float }
        or None if insufficient data
    """
    if len(prices) < slow_period + signal_period or slow_period <= fast_period:
        return None

    # Build a MACD line series (one point per price after slow_period warmup)
    macd_series: List[float] = []
    for i in range(slow_period, len(prices) + 1):
        f = ema(prices[:i], fast_period)
        s = ema(prices[:i], slow_period)
        if f is not None and s is not None:
            macd_series.append(f - s)

    if len(macd_series) < signal_period:
        return None

    current_macd = macd_series[-1]
    signal_line  = ema(macd_series, signal_period)

    if signal_line is None:
        return None

    histogram = current_macd - signal_line
    return {
        "macd":      round(current_macd, 4),
        "signal":    round(signal_line,  4),
        "histogram": round(histogram,    4),
    }


# =============================================================================
# Bollinger Bands
# =============================================================================

def bollinger_bands(
    prices: PriceSeries,
    period: int = 20,
    num_std: float = 2.0,
) -> Optional[Dict[str, float]]:
    """
    Bollinger Bands: upper, middle (SMA), lower bands.

    Args:
        prices:  Chronological price series
        period:  SMA period (default 20)
        num_std: Standard deviation multiplier (default 2.0)

    Returns:
        Dict { "upper": float, "middle": float, "lower": float }
        or None if insufficient data
    """
    if len(prices) < period or period <= 0:
        return None

    window = prices[-period:]
    middle = sum(window) / period
    # Population standard deviation (consistent with most charting software)
    variance = sum((p - middle) ** 2 for p in window) / period
    std_dev  = math.sqrt(variance)

    return {
        "upper":  round(middle + num_std * std_dev, 4),
        "middle": round(middle,                      4),
        "lower":  round(middle - num_std * std_dev,  4),
    }


# =============================================================================
# Indicator Registry — extensibility point
# =============================================================================

# Maps the indicator name (as stored in rules_json) to its callable.
# To add a new indicator: implement the function above, then register it here.
INDICATOR_REGISTRY: Dict[str, callable] = {
    "SMA":  sma,
    "EMA":  ema,
    "RSI":  rsi,
    "MACD": macd,
    "BB":   bollinger_bands,
}


def compute_indicator(
    name: str,
    prices: PriceSeries,
    **kwargs,
) -> IndicatorResult:
    """
    Generic dispatcher called by strategy_engine.py.

    Maps rule condition indicator names to functions and invokes them.
    kwargs are passed directly to the underlying function (e.g. period=14).

    Examples:
        compute_indicator("RSI",  prices, period=14)         → 32.5
        compute_indicator("SMA",  prices, period=200)        → 24100.0
        compute_indicator("MACD", prices)                    → {"macd": ..., "signal": ..., "histogram": ...}
        compute_indicator("BB",   prices, period=20)         → {"upper": ..., "middle": ..., "lower": ...}

    Raises:
        ValueError: if `name` is not in INDICATOR_REGISTRY
    """
    func = INDICATOR_REGISTRY.get(name.upper())
    if func is None:
        raise ValueError(
            f"Unknown indicator: '{name}'. "
            f"Available: {sorted(INDICATOR_REGISTRY.keys())}"
        )
    return func(prices, **kwargs)


def get_min_required_prices(name: str, **kwargs) -> int:
    """
    Returns the minimum number of price points needed for an indicator
    to return a non-None result. Used by the strategy engine to skip
    evaluation cycles when history is too short.

    Examples:
        get_min_required_prices("RSI", period=14)  → 15
        get_min_required_prices("SMA", period=200) → 200
        get_min_required_prices("MACD")            → 35  (26 + 9)
    """
    n = name.upper()
    if n == "RSI":
        period = kwargs.get("period", 14)
        return period + 1
    elif n in ("SMA", "EMA", "BB"):
        return kwargs.get("period", 20)
    elif n == "MACD":
        slow   = kwargs.get("slow_period",   26)
        signal = kwargs.get("signal_period",  9)
        return slow + signal
    # Conservative fallback for unknown future indicators
    return kwargs.get("period", 30)
