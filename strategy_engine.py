"""
strategy_engine.py — Algorithmic Strategy Evaluation Worker (Phase 3)

Evaluation Cycle : 1-minute candle close (detected via UTC minute boundary).
Trade Constraint  : Max 1 pending order per strategy (idempotency guard).
                    BUY also blocked if user already has an open position.
Indicator Source  : candles_1m table — close prices extracted as PriceSeries.
Auto-Journaling   : Records strategy_id + entry_reason on every triggered order.

Supported Rule DSL (rules_json):
  {
    "symbol":       "NIFTY",          ← required: which asset to trade
    "condition":    { ... },          ← logical tree (see below)
    "action":       "BUY",            ← "BUY" or "SELL"
    "quantity_pct": 50,               ← % of available cash/position to use
    "order_mode":   "MARKET"          ← "MARKET" or "BRACKET"
  }

Condition tree:
  Leaf  : { "indicator": "RSI", "period": 14, "operator": "<", "value": 30 }
  AND   : { "AND": [cond1, cond2] }
  OR    : { "OR":  [cond1, cond2] }

Compare against indicator RHS (instead of literal):
  { "indicator": "PRICE", "operator": ">", "compare_to": "SMA", "compare_period": 200 }

MACD / Bollinger sub-field access:
  { "indicator": "MACD", "field": "histogram", "operator": ">", "value": 0 }
"""

import time
import logging
from datetime import datetime, timezone
from typing import List, Optional

from psycopg2.extras import RealDictCursor

import config
from database import DatabaseHandler
from indicators import compute_indicator

logger = logging.getLogger("STRATEGY_ENGINE")
db = DatabaseHandler()

EVAL_INTERVAL = 5        # seconds between candle-close boundary checks
MIN_CANDLES   = 220      # max lookback depth (covers SMA 200 + warmup)
SUPPORTED_OPS = {"<", ">", "<=", ">=", "==", "!="}


# ──────────────────────────────────────────────────────────────────────────────
# Candle Data
# ──────────────────────────────────────────────────────────────────────────────

def _get_close_prices(symbol: str, limit: int = MIN_CANDLES) -> List[float]:
    """Fetch the last `limit` 1-minute close prices from candles_1m (oldest → newest)."""
    candles = db.get_candles(symbol, limit=limit)
    return [float(c["close"]) for c in candles if c.get("close") is not None]


def _current_minute() -> int:
    """UTC minute value used as a candle-close boundary detector."""
    return datetime.now(timezone.utc).replace(second=0, microsecond=0).minute


# ──────────────────────────────────────────────────────────────────────────────
# Idempotency Guards
# ──────────────────────────────────────────────────────────────────────────────

def _strategy_has_pending_order(user_id: int, strategy_id: int, symbol: str) -> bool:
    """
    Returns True if this strategy already has a 'pending' order for this symbol.
    Prevents the same signal from spawning duplicate orders on consecutive ticks.
    Fails closed (returns True) on DB error so we never double-execute.
    """
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM orders
                WHERE user_id    = %s
                  AND strategy_id = %s
                  AND symbol      = %s
                  AND status      = 'pending'
                LIMIT 1
            """, (user_id, strategy_id, symbol))
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"[STRAT] Idempotency DB check failed: {e}")
        return True  # fail closed
    finally:
        db.return_connection(conn)


# ──────────────────────────────────────────────────────────────────────────────
# DSL Evaluator
# ──────────────────────────────────────────────────────────────────────────────

def _apply_operator(lhs: float, op: str, rhs: float) -> bool:
    if op == "<":  return lhs < rhs
    if op == ">":  return lhs > rhs
    if op == "<=": return lhs <= rhs
    if op == ">=": return lhs >= rhs
    if op == "==": return abs(lhs - rhs) < 1e-4
    if op == "!=": return abs(lhs - rhs) >= 1e-4
    raise ValueError(f"Unsupported operator: '{op}'")


def _resolve_rhs(rule: dict, prices: List[float], current_price: float) -> Optional[float]:
    """
    Resolve the right-hand side of a condition to a float.

    Formats:
      Literal   : {"value": 30}
      Price     : {"compare_to": "PRICE"}
      Indicator : {"compare_to": "SMA", "compare_period": 200}
                  {"compare_to": "MACD", "compare_field": "histogram"}
    """
    if "value" in rule:
        return float(rule["value"])

    compare_to = rule.get("compare_to", "").upper()
    if not compare_to:
        raise ValueError(f"Rule missing 'value' or 'compare_to': {rule}")

    if compare_to == "PRICE":
        return current_price

    kwargs = {}
    if "compare_period" in rule:
        kwargs["period"] = int(rule["compare_period"])

    result = compute_indicator(compare_to, prices, **kwargs)
    if result is None:
        return None  # insufficient data

    if isinstance(result, dict):
        field = rule.get("compare_field")
        if not field:
            raise ValueError(f"'{compare_to}' returns a dict — specify 'compare_field'.")
        return float(result[field])

    return float(result)


def _evaluate_leaf(rule: dict, prices: List[float], current_price: float) -> bool:
    """
    Evaluate one atomic condition leaf.

    Full rule format:
      {
        "indicator":      "RSI",      # or "PRICE" for raw price
        "period":         14,         # indicator param (int)
        "field":          None,       # sub-field for MACD/BB ("macd","signal","histogram","upper","lower","middle")
        "operator":       "<",        # comparison operator
        "value":          30,         # literal RHS  — OR —
        "compare_to":     "SMA",      # indicator/PRICE for RHS
        "compare_period": 200,        # RHS indicator param
        "compare_field":  None        # RHS sub-field for dict indicators
      }
    """
    indicator = rule.get("indicator", "").upper()
    op        = rule.get("operator", "")

    if op not in SUPPORTED_OPS:
        raise ValueError(f"Unsupported operator '{op}'.")

    # ── Left-hand side ──
    if indicator == "PRICE":
        lhs = current_price
    else:
        kwargs = {}
        if "period" in rule:
            kwargs["period"] = int(rule["period"])

        result = compute_indicator(indicator, prices, **kwargs)
        if result is None:
            return False  # not enough data — don't trigger

        if isinstance(result, dict):
            field = rule.get("field")
            if not field:
                raise ValueError(f"'{indicator}' returns a dict — specify 'field'.")
            lhs = float(result[field])
        else:
            lhs = float(result)

    # ── Right-hand side ──
    rhs = _resolve_rhs(rule, prices, current_price)
    if rhs is None:
        return False  # RHS indicator has insufficient data

    return _apply_operator(lhs, op, rhs)


def _evaluate_condition(condition: dict, prices: List[float], current_price: float, depth: int = 0) -> bool:
    """Recursively evaluates the JSON condition tree against market data."""
    if depth > 10:
        raise ValueError("Strategy DSL condition tree too deep (max 10 levels)")

    if "AND" in condition:
        return all(_evaluate_condition(c, prices, current_price, depth + 1) for c in condition["AND"])
    if "OR" in condition:
        return any(_evaluate_condition(c, prices, current_price, depth + 1) for c in condition["OR"])

    return _evaluate_leaf(condition, prices, current_price)


# ──────────────────────────────────────────────────────────────────────────────
# Order Execution
# ──────────────────────────────────────────────────────────────────────────────

def _tag_order_with_strategy(order_id: int, strategy_id: int, entry_reason: str) -> None:
    """Backfill strategy_id + entry_reason on a freshly executed MARKET order."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE orders
                SET strategy_id = %s, entry_reason = %s
                WHERE id = %s
            """, (strategy_id, entry_reason, order_id))
            conn.commit()
    except Exception as e:
        logger.warning(f"[STRAT] Failed to tag order #{order_id}: {e}")
    finally:
        db.return_connection(conn)


def _execute_strategy_signal(
    strategy: dict,
    symbol: str,
    side: str,
    current_price: float,
) -> None:
    """
    Place an order triggered by a strategy signal.

    - Determines quantity from portfolio cash (BUY) or open position size (SELL).
    - Tags the order with strategy_id and entry_reason.
    - Auto-creates a trade journal entry on fill.
    """
    user_id      = strategy["user_id"]
    strategy_id  = strategy["id"]
    rules        = strategy["rules_json"]
    order_mode   = rules.get("order_mode", "MARKET").upper()
    qty_pct      = float(rules.get("quantity_pct", 100))
    entry_reason = f"Strategy '{strategy['name']}': {side} signal @ {current_price:.2f}"

    try:
        if side == "BUY":
            portfolio = db.get_portfolio(user_id, symbol)
            if not portfolio:
                logger.warning(f"[STRAT] No portfolio for user {user_id} / {symbol}.")
                return
            budget   = float(portfolio["cash_available"]) * (qty_pct / 100.0)
            quantity = max(1, int(budget / current_price)) if current_price > 0 else 0
            if quantity <= 0:
                logger.warning(f"[STRAT] Insufficient budget for {symbol} — skipping BUY.")
                return

        else:  # SELL
            position = db.get_position(user_id, symbol)
            if not position or int(position.get("quantity", 0)) <= 0:
                logger.info(f"[STRAT] SELL signal for {symbol} but no open position — skipping.")
                return
            quantity = int(position["quantity"])

        if order_mode == "MARKET":
            result   = db.execute_market_order(
                user_id  = user_id,
                symbol   = symbol,
                side     = side,
                quantity = quantity,
                price    = current_price,
            )
            order_id = result.get("order_id")
            trade_id = result.get("trade_id")

            if order_id:
                _tag_order_with_strategy(order_id, strategy_id, entry_reason)
            if trade_id:
                db.create_trade_journal(trade_id=trade_id, entry_reason=entry_reason)

        else:
            # Pending advanced orders (BRACKET etc.)
            db.create_order(
                user_id        = user_id,
                symbol         = symbol,
                order_type     = side.lower(),
                quantity       = quantity,
                price          = current_price,
                execution_mode = order_mode,
                strategy_id    = strategy_id,
                entry_reason   = entry_reason,
            )

        logger.info(
            f"[STRAT] ✅ '{strategy['name']}' → {order_mode} {side} "
            f"{quantity} {symbol} @ {current_price:.2f}"
        )

    except ValueError as e:
        logger.warning(f"[STRAT] Signal skipped for strategy {strategy_id}: {e}")
    except Exception as e:
        logger.error(f"[STRAT] Execution error for strategy {strategy_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Per-Symbol Batch Evaluator
# ──────────────────────────────────────────────────────────────────────────────

def _evaluate_strategies_for_symbol(symbol: str, strategies: List[dict]) -> None:
    """
    Evaluate all strategies watching `symbol` using a single shared candle fetch.

    Fetched once per symbol per candle — not once per strategy — for efficiency.
    """
    prices = _get_close_prices(symbol)
    if not prices:
        logger.debug(f"[STRAT] No candle data for {symbol} — skipping symbol.")
        return

    current_price = prices[-1]

    for strategy in strategies:
        strategy_id = strategy["id"]
        user_id     = strategy["user_id"]
        rules       = strategy["rules_json"]

        try:
            condition = rules.get("condition")
            action    = rules.get("action", "").upper()

            if not condition or action not in ("BUY", "SELL"):
                logger.warning(f"[STRAT] Strategy {strategy_id}: invalid rules (missing condition/action).")
                continue

            # Guard 1: No duplicate pending orders from this strategy
            if _strategy_has_pending_order(user_id, strategy_id, symbol):
                logger.debug(f"[STRAT] Strategy {strategy_id} already has pending order — skipped.")
                continue

            # Guard 2: BUY blocked if position already open (any strategy, same symbol)
            if action == "BUY":
                pos = db.get_position(user_id, symbol)
                if pos and int(pos.get("quantity", 0)) > 0:
                    logger.debug(f"[STRAT] Strategy {strategy_id}: existing position blocks BUY on {symbol}.")
                    continue

            # Evaluate the rule tree
            triggered = _evaluate_condition(condition, prices, current_price)

            if triggered:
                logger.info(
                    f"[STRAT] 🔔 '{strategy['name']}' (ID:{strategy_id}) "
                    f"→ {action} {symbol} @ {current_price:.2f}"
                )
                _execute_strategy_signal(strategy, symbol, action, current_price)

        except Exception as e:
            logger.error(f"[STRAT] Error evaluating strategy {strategy_id}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────────────────────────────────────

def run_strategy_engine_sync() -> None:
    """
    Main background loop. Runs in a dedicated daemon thread.

    Fires evaluation once per 1-minute candle close (UTC minute boundary).
    Groups all active strategies by symbol to minimise candle DB queries.
    """
    logger.info("⚙️  [STRATEGY ENGINE] Running — evaluating at each 1-minute candle close")
    last_evaluated_minute: int = -1

    while True:
        try:
            current_min = _current_minute()

            if current_min != last_evaluated_minute:
                last_evaluated_minute = current_min

                all_strategies = db.get_active_strategies()
                if not all_strategies:
                    time.sleep(EVAL_INTERVAL)
                    continue

                # Group by symbol — fetch candles once per symbol
                by_symbol: dict[str, list] = {}
                for strat in all_strategies:
                    sym = strat["rules_json"].get("symbol", "").upper()
                    if sym in config.SYMBOLS:
                        by_symbol.setdefault(sym, []).append(strat)
                    else:
                        logger.warning(
                            f"[STRAT] Strategy {strat['id']} ('{strat['name']}'): "
                            f"missing or unsupported symbol '{sym}' — skipped."
                        )

                for symbol, strategies in by_symbol.items():
                    _evaluate_strategies_for_symbol(symbol, strategies)

        except Exception as e:
            logger.error(f"[STRAT] Unexpected loop error: {e}")

        time.sleep(EVAL_INTERVAL)
