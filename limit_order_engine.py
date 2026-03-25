"""
limit_order_engine.py — Asynchronous Limit Order Execution Worker

How it works:
1. Runs as a background asyncio task, started by FastAPI's lifespan.
2. Every 500ms, polls Redis for the latest price of each symbol.
3. Scans all pending LIMIT orders in the DB for that symbol.
4. Executes any order whose limit condition is met at the current market price.
5. Uses the same execute_market_order() DB function to keep execution atomic.

Limit Order Logic:
  BUY  LIMIT: execute when market_price <= limit_price  (buy cheap)
  SELL LIMIT: execute when market_price >= limit_price  (sell high)
"""
import threading
import time
import logging
import json
from datetime import datetime

import redis as redis_lib
import config
from database import DatabaseHandler

logger = logging.getLogger("LIMIT_ENGINE")
db     = DatabaseHandler()

# Connect to Redis — same pool used by the streamer
if config.REDIS_URL:
    _redis = redis_lib.from_url(config.REDIS_URL, decode_responses=True)
else:
    _redis = redis_lib.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        decode_responses=True,
    )

POLL_INTERVAL = 0.5   # seconds between price checks


def _get_latest_price(symbol: str) -> float:
    """Pull the latest price for a symbol from Redis (returns 0 if not found)."""
    try:
        raw = _redis.get(f"price:{symbol}")
        if raw:
            return float(raw)
    except Exception as e:
        logger.warning(f"[ENGINE] Redis read failed for {symbol}: {e}")
    return 0.0


def _get_pending_limit_orders(symbol: str) -> list[dict]:
    """Fetch all pending LIMIT orders for a symbol from PostgreSQL."""
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM orders
                WHERE symbol = %s
                  AND status = 'pending'
                  AND execution_mode = 'LIMIT'
                ORDER BY created_at ASC
            """, (symbol,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"[ENGINE] DB query failed: {e}")
        return []
    finally:
        db.return_connection(conn)


def _check_and_execute(order: dict, market_price: float) -> bool:
    """
    Returns True if this limit order's price condition is met
    and executes it atomically via execute_market_order().
    """
    if market_price <= 0:
        return False

    side        = order["order_type"].upper()    # 'buy' or 'sell' from DB
    limit_price = float(order["price"])
    user_id     = order["user_id"]
    symbol      = order["symbol"]
    quantity    = order["quantity"]
    order_id    = order["id"]

    triggered = (
        (side == "BUY"  and market_price <= limit_price) or
        (side == "SELL" and market_price >= limit_price)
    )

    if not triggered:
        return False

    try:
        logger.info(
            f"[ENGINE] 🔔 LIMIT {side} triggered: {symbol} "
            f"limit={limit_price:.2f}  market={market_price:.2f}"
        )

        # Execute at the current market price (price improvement is favorable)
        result = db.execute_market_order(
            user_id=user_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=market_price,
            is_limit_execution=True,  # To avoid double-inserting the order record
            existing_order_id=order_id
        )
        return True

    except ValueError as e:
        # Insufficient funds / holdings — cancel the order
        logger.warning(f"[ENGINE] ⚠️ Order #{order_id} cancelled: {e}")
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE orders SET status = 'cancelled' WHERE id = %s",
                    (order_id,)
                )
                conn.commit()
        finally:
            db.return_connection(conn)
        return False

    except Exception as e:
        logger.error(f"[ENGINE] ❌ Execution error for order #{order_id}: {e}")
        return False

def run_limit_order_engine_sync():
    """
    Main background loop. Runs in a dedicated background thread,
    so it doesn't block FastAPI's async event loop.
    """
    logger.info("⚙️  [LIMIT ENGINE] Started — scanning every 500ms (Background Thread)")

    while True:
        try:
            for symbol in config.SYMBOLS:
                market_price = _get_latest_price(symbol)
                if market_price <= 0:
                    continue

                pending = _get_pending_limit_orders(symbol)
                for order in pending:
                    # Execute limit logic synchronously per order to maintain atomicity
                    _check_and_execute(order, market_price)

        except Exception as e:
            logger.error(f"[ENGINE] Unexpected error: {e}")

        time.sleep(POLL_INTERVAL)
