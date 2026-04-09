"""
order_engine.py — Advanced Order Execution Engine (Phase 2)

State Machine:
    PENDING ──► TRIGGERED ──► FILLED (='executed' in DB)
                         └──► CANCELLED

Supported Execution Modes:
    LIMIT    — Standard limit order (BUY ≤ price, SELL ≥ price).
    OCO      — One-Cancels-Other pair linked via oco_group_id.
    TRAILING — Trailing stop-loss; watermark tracked in Redis, persisted in DB.
    BRACKET  — Entry leg; TP+SL children activate only after this fills.

Backward Compatibility:
    run_limit_order_engine_sync() is preserved as an alias so server.py
    does not require changes for the basic startup wiring.
"""

import threading
import time
import logging
from enum import Enum
from typing import Optional

import redis as redis_lib
from psycopg2.extras import RealDictCursor

import config
from database import DatabaseHandler

logger = logging.getLogger("ORDER_ENGINE")
db     = DatabaseHandler()

# ── Redis connection (identical pattern to limit_order_engine.py) ──────────────
if config.REDIS_URL:
    _redis = redis_lib.from_url(config.REDIS_URL, decode_responses=True)
else:
    _redis = redis_lib.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        decode_responses=True,
    )

POLL_INTERVAL = 0.5  # seconds


# ──────────────────────────────────────────────────────────────────────────────
# State Machine Enums
# ──────────────────────────────────────────────────────────────────────────────

class OrderState(str, Enum):
    PENDING   = "pending"
    FILLED    = "executed"    # DB string for the FILLED state
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    MARKET   = "MARKET"
    LIMIT    = "LIMIT"
    OCO      = "OCO"
    TRAILING = "TRAILING"
    BRACKET  = "BRACKET"


# ──────────────────────────────────────────────────────────────────────────────
# Redis Key Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _tsl_key(order_id: int) -> str:
    """Redis key for a trailing stop-loss watermark."""
    return f"tsl:watermark:{order_id}"


def _get_latest_price(symbol: str) -> float:
    """Pull the latest tick price for a symbol from Redis. Returns 0.0 on miss."""
    try:
        raw = _redis.get(f"price:{symbol}")
        if raw:
            return float(raw)
    except Exception as e:
        logger.warning(f"[ENGINE] Redis price read failed for {symbol}: {e}")
    return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Cold-Start Recovery
# ──────────────────────────────────────────────────────────────────────────────

def _restore_tsl_watermarks() -> None:
    """
    On engine startup, seed Redis with watermark_price from DB for all
    pending TRAILING orders. Avoids scanning market_ticks — DB is the
    single source of truth for watermarks.
    """
    conn = db.get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, watermark_price FROM orders
                WHERE status = 'pending'
                  AND execution_mode = 'TRAILING'
                  AND watermark_price IS NOT NULL
            """)
            rows = cur.fetchall()
            for row in rows:
                _redis.set(_tsl_key(row['id']), str(row['watermark_price']))
            logger.info(f"[ENGINE] ✅ Restored {len(rows)} TSL watermark(s) from DB into Redis")
    except Exception as e:
        logger.error(f"[ENGINE] ❌ TSL watermark restore failed: {e}")
    finally:
        db.return_connection(conn)


# ──────────────────────────────────────────────────────────────────────────────
# DB Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_active_orders_for_symbol(symbol: str) -> list[dict]:
    """
    Fetch all orders that the engine should evaluate this tick.

    Inclusion rules:
    - status = 'pending'
    - execution_mode IN (LIMIT, OCO, TRAILING, BRACKET)
    - Standalone orders (parent_order_id IS NULL) are always included.
    - Bracket children (parent_order_id IS NOT NULL) are ONLY included when
      their parent BRACKET entry has status = 'executed' (FILLED).
    """
    conn = db.get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT o.*
                FROM orders o
                WHERE o.symbol = %s
                  AND o.status = 'pending'
                  AND o.execution_mode IN ('LIMIT', 'OCO', 'TRAILING', 'BRACKET')
                  AND (
                      o.parent_order_id IS NULL
                      OR EXISTS (
                          SELECT 1 FROM orders p
                          WHERE p.id = o.parent_order_id
                            AND p.execution_mode = 'BRACKET'
                            AND p.status = 'executed'
                      )
                  )
                ORDER BY o.created_at ASC
            """, (symbol,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"[ENGINE] DB active-order query failed: {e}")
        return []
    finally:
        db.return_connection(conn)


def _persist_tsl_watermark(order_id: int, watermark: float) -> None:
    """
    Write an updated TSL watermark to Redis first (fast path),
    then persist to DB (recovery source of truth).
    """
    _redis.set(_tsl_key(order_id), str(watermark))
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET watermark_price = %s WHERE id = %s AND status = 'pending'",
                (watermark, order_id)
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"[ENGINE] TSL DB persist failed for order #{order_id}: {e}")
    finally:
        db.return_connection(conn)


def _cancel_order_safe(order_id: int, reason: str = "") -> None:
    """Cancel a single pending order. No-op if already non-pending."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = 'cancelled' WHERE id = %s AND status = 'pending'",
                (order_id,)
            )
            conn.commit()
        if reason:
            logger.warning(f"[ENGINE] ⚠️  Order #{order_id} cancelled: {reason}")
    except Exception as e:
        logger.error(f"[ENGINE] Cancel failed for order #{order_id}: {e}")
    finally:
        db.return_connection(conn)


# ──────────────────────────────────────────────────────────────────────────────
# Core Execution Path
# ──────────────────────────────────────────────────────────────────────────────

def _execute_order(order: dict, market_price: float) -> bool:
    """
    Common fill path for all order types.

    Delegates entirely to execute_market_order() which:
      - Acquires a SELECT FOR UPDATE row lock on the order.
      - Validates status = 'pending' before doing anything.
      - Atomically cancels OCO siblings via parent_order_id AND oco_group_id.
      - Updates position and portfolio cash in the same transaction.

    Returns True on successful fill, False otherwise.
    """
    try:
        db.execute_market_order(
            user_id            = order["user_id"],
            symbol             = order["symbol"],
            side               = order["order_type"].upper(),
            quantity           = order["quantity"],
            price              = market_price,
            is_limit_execution = True,
            existing_order_id  = order["id"],
        )
        logger.info(
            f"[ENGINE] ✅ {order['execution_mode']} {order['order_type'].upper()} FILLED: "
            f"{order['symbol']} @ {market_price:.2f}  (order #{order['id']})"
        )
        return True
    except ValueError as e:
        # Insufficient funds / holdings — cancel gracefully
        _cancel_order_safe(order["id"], reason=str(e))
        return False
    except Exception as e:
        logger.error(f"[ENGINE] ❌ Execution error for order #{order['id']}: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Per-Mode Handlers
# ──────────────────────────────────────────────────────────────────────────────

def _process_limit_or_oco(order: dict, market_price: float) -> None:
    """
    LIMIT and OCO share identical price-trigger semantics.
    Atomic sibling cancellation for OCO is handled inside execute_market_order
    via oco_group_id and parent_order_id — no extra logic needed here.
    """
    side        = order["order_type"].upper()
    limit_price = float(order["price"])

    triggered = (
        (side == "BUY"  and market_price <= limit_price) or
        (side == "SELL" and market_price >= limit_price)
    )
    if not triggered:
        return

    logger.info(
        f"[ENGINE] 🔔 {order['execution_mode']} {side} triggered: "
        f"{order['symbol']}  limit={limit_price:.2f}  market={market_price:.2f}"
    )
    _execute_order(order, market_price)


def _process_trailing_sl(order: dict, market_price: float) -> None:
    """
    Trailing Stop-Loss state machine.

    For a SELL trailing SL (protecting a long):
      - Watermark moves UP when price rises (locks in profits).
      - Triggers when price drops below  watermark - offset.

    For a BUY trailing SL (protecting a short, uncommon):
      - Watermark moves DOWN when price falls.
      - Triggers when price rises above  watermark + offset.

    Watermark resolution order: Redis cache → DB column → first-tick init.
    """
    order_id = order["id"]
    side     = order["order_type"].upper()
    offset   = float(order.get("trailing_offset") or 0)

    if offset <= 0:
        logger.warning(f"[ENGINE] TSL order #{order_id} has invalid offset ({offset}) — skipping.")
        return

    # Resolve watermark: Redis → DB fallback
    raw = _redis.get(_tsl_key(order_id))
    if raw is not None:
        watermark = float(raw)
    elif order.get("watermark_price"):
        watermark = float(order["watermark_price"])
        _redis.set(_tsl_key(order_id), str(watermark))     # repopulate cache
    else:
        # First-ever tick for this TSL — initialise watermark, do not trigger yet
        _persist_tsl_watermark(order_id, market_price)
        return

    if side == "SELL":
        if market_price > watermark:
            # Favourable move: raise the watermark
            _persist_tsl_watermark(order_id, market_price)
            return
        # Unfavourable: check trigger
        if market_price <= watermark - offset:
            logger.info(
                f"[ENGINE] 🔔 TRAILING SELL triggered: {order['symbol']} "
                f"watermark={watermark:.2f}  offset={offset:.2f}  market={market_price:.2f}"
            )
            if _execute_order(order, market_price):
                _redis.delete(_tsl_key(order_id))   # clean up after fill

    elif side == "BUY":
        if market_price < watermark:
            _persist_tsl_watermark(order_id, market_price)
            return
        if market_price >= watermark + offset:
            logger.info(
                f"[ENGINE] 🔔 TRAILING BUY triggered: {order['symbol']} "
                f"watermark={watermark:.2f}  offset={offset:.2f}  market={market_price:.2f}"
            )
            if _execute_order(order, market_price):
                _redis.delete(_tsl_key(order_id))


def _process_bracket_entry(order: dict, market_price: float) -> None:
    """
    Bracket entry leg.

    - If the entry has a limit price: treat like a LIMIT order.
    - If no price (market bracket): fill immediately at the current tick price.

    Once this entry fills, its child TP+SL orders (stored in DB with
    parent_order_id = this order's ID) will be picked up by
    _get_active_orders_for_symbol on the NEXT engine tick.
    """
    side        = order["order_type"].upper()
    limit_price = order.get("price")

    if not limit_price or float(limit_price) <= 0:
        # Market bracket entry — execute immediately
        logger.info(f"[ENGINE] 🔔 BRACKET MARKET entry triggered: {order['symbol']} @ {market_price:.2f}")
        _execute_order(order, market_price)
        return

    limit_price = float(limit_price)
    triggered = (
        (side == "BUY"  and market_price <= limit_price) or
        (side == "SELL" and market_price >= limit_price)
    )
    if triggered:
        logger.info(
            f"[ENGINE] 🔔 BRACKET LIMIT entry triggered: {order['symbol']} "
            f"limit={limit_price:.2f}  market={market_price:.2f}"
        )
        _execute_order(order, market_price)


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────

def _dispatch(order: dict, market_price: float) -> None:
    """Route an order to its correct handler based on execution_mode."""
    mode = (order.get("execution_mode") or "LIMIT").upper()

    if mode in ("LIMIT", "OCO"):
        _process_limit_or_oco(order, market_price)
    elif mode == "TRAILING":
        _process_trailing_sl(order, market_price)
    elif mode == "BRACKET":
        _process_bracket_entry(order, market_price)
    else:
        logger.warning(f"[ENGINE] Unknown execution_mode '{mode}' on order #{order['id']} — skipping.")


# ──────────────────────────────────────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────────────────────────────────────

def run_order_engine_sync() -> None:
    """
    Main background loop. Runs in a dedicated daemon thread so it never
    blocks FastAPI's async event loop.

    On startup  : restores TSL watermarks from DB into Redis.
    Every tick  : fetches the latest Redis price per symbol, then dispatches
                  all actionable pending orders to the correct handler.
    """
    logger.info("⚙️  [ORDER ENGINE] Starting — restoring TSL state from DB...")
    _restore_tsl_watermarks()
    logger.info(f"⚙️  [ORDER ENGINE] Running — polling every {int(POLL_INTERVAL * 1000)}ms")

    while True:
        try:
            for symbol in config.SYMBOLS:
                market_price = _get_latest_price(symbol)
                if market_price <= 0:
                    continue

                orders = _get_active_orders_for_symbol(symbol)
                for order in orders:
                    _dispatch(order, market_price)

        except Exception as e:
            logger.error(f"[ENGINE] Unexpected loop error: {e}")

        time.sleep(POLL_INTERVAL)


# Backward-compatible alias — keeps existing code that references the old name working.
run_limit_order_engine_sync = run_order_engine_sync
