import psycopg2
import json
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    """Database operations handler for HedgeBot paper trading"""
    
    def __init__(self):
        """Initialize connection pool"""
        try:
            self.pool = ThreadedConnectionPool(
                1, 20,  # minconn=1, maxconn=20 (Increased for background threads)
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
            logger.info("✓ Database connection pool initialized")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise

    def get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()

    def return_connection(self, conn):
        """Return connection to pool"""
        if conn:
            self.pool.putconn(conn)

    def close_all_connections(self):
        """Close all connections in pool"""
        self.pool.closeall()

    # ========== USER OPERATIONS ==========
    
    def create_user(self, username: str, email: str, password_hash: str) -> int:
        """Create new user and return user_id"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, created_at, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (username, email, password_hash, datetime.now(), 'active'))
                user_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ User created: {username} (ID: {user_id})")
                return user_id
        except psycopg2.IntegrityError as e:
            conn.rollback()
            logger.error(f"✗ User creation failed (duplicate): {e}")
            raise ValueError("Username or email already exists")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ User creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"✗ Get user failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"✗ Get user by ID failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== PORTFOLIO OPERATIONS ==========
    
    def create_portfolio(self, user_id: int, symbol: str, total_capital: float) -> int:
        """Create portfolio for user and symbol"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolios (user_id, symbol, total_capital, cash_available, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, symbol, total_capital, total_capital, datetime.now(), datetime.now()))
                portfolio_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Portfolio created for user {user_id}, symbol {symbol}")
                return portfolio_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Portfolio creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_portfolio(self, user_id: int, symbol: str) -> Optional[Dict]:
        """Get portfolio for user and symbol"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM portfolios WHERE user_id = %s AND symbol = %s",
                    (user_id, symbol)
                )
                portfolio = cur.fetchone()
                return dict(portfolio) if portfolio else None
        except Exception as e:
            logger.error(f"✗ Get portfolio failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_all_portfolios(self, user_id: int) -> List[Dict]:
        """Get all portfolios for a user"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM portfolios WHERE user_id = %s", (user_id,))
                portfolios = cur.fetchall()
                return [dict(p) for p in portfolios]
        except Exception as e:
            logger.error(f"✗ Get all portfolios failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def update_portfolio_cash(self, user_id: int, symbol: str, cash_delta: float) -> None:
        """Update portfolio cash (add or subtract)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE portfolios 
                    SET cash_available = cash_available + %s, updated_at = %s
                    WHERE user_id = %s AND symbol = %s
                """, (cash_delta, datetime.now(), user_id, symbol))
                conn.commit()
                logger.info(f"✓ Portfolio cash updated for user {user_id}: {cash_delta}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Update portfolio cash failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== POSITION OPERATIONS ==========
    
    def create_position(self, user_id: int, symbol: str, quantity: int, entry_price: float) -> int:
        """Create new position"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO positions (user_id, symbol, quantity, entry_price, current_price, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, symbol, quantity, entry_price, entry_price, 'open', datetime.now(), datetime.now()))
                position_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Position created: user {user_id}, {quantity} @ {symbol}")
                return position_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Position creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_position(self, user_id: int, symbol: str) -> Optional[Dict]:
        """Get position for user and symbol"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM positions WHERE user_id = %s AND symbol = %s AND status = 'open'",
                    (user_id, symbol)
                )
                position = cur.fetchone()
                return dict(position) if position else None
        except Exception as e:
            logger.error(f"✗ Get position failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_all_positions(self, user_id: int) -> List[Dict]:
        """Get all open positions for user"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM positions WHERE user_id = %s AND status = 'open'",
                    (user_id,)
                )
                positions = cur.fetchall()
                return [dict(p) for p in positions]
        except Exception as e:
            logger.error(f"✗ Get all positions failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def update_position(self, user_id: int, symbol: str, quantity_delta: int, current_price: float) -> None:
        """Update position quantity and current price"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Get current position
                cur.execute(
                    "SELECT quantity, entry_price FROM positions WHERE user_id = %s AND symbol = %s",
                    (user_id, symbol)
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError("Position not found")
                
                old_quantity, entry_price = result
                new_quantity = old_quantity + quantity_delta
                
                # Calculate unrealized PnL
                unrealized_pnl = (current_price - entry_price) * new_quantity if new_quantity > 0 else 0
                
                # Update position
                cur.execute("""
                    UPDATE positions 
                    SET quantity = %s, current_price = %s, unrealized_pnl = %s, updated_at = %s
                    WHERE user_id = %s AND symbol = %s
                """, (new_quantity, current_price, unrealized_pnl, datetime.now(), user_id, symbol))
                
                conn.commit()
                logger.info(f"✓ Position updated: user {user_id}, {symbol}, qty={new_quantity}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Update position failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def close_position(self, user_id: int, symbol: str) -> None:
        """Close position (mark as closed)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE positions 
                    SET status = 'closed', updated_at = %s
                    WHERE user_id = %s AND symbol = %s
                """, (datetime.now(), user_id, symbol))
                conn.commit()
                logger.info(f"✓ Position closed: user {user_id}, {symbol}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Close position failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== ORDER OPERATIONS ==========
    
    def create_order(
        self,
        user_id: int,
        symbol: str,
        order_type: str,
        quantity: int,
        price: Optional[float] = None,
        execution_mode: str = 'MARKET',
        parent_order_id: Optional[int] = None,
        trailing_offset: Optional[float] = None,
        watermark_price: Optional[float] = None,
        strategy_id: Optional[int] = None,
        entry_reason: Optional[str] = None,
    ) -> int:
        """Create new order (MARKET, LIMIT, OCO, TRAILING, BRACKET)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO orders (
                        user_id, symbol, order_type, quantity, price, status,
                        execution_mode, parent_order_id, trailing_offset,
                        watermark_price, strategy_id, entry_reason, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id, symbol, order_type.lower(), quantity, price, 'pending',
                    execution_mode.upper(), parent_order_id, trailing_offset,
                    watermark_price, strategy_id, entry_reason, datetime.now()
                ))
                order_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Order created: {execution_mode} {order_type} {quantity} {symbol} (ID: {order_id})")
                return order_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Order creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get order by ID"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
                order = cur.fetchone()
                return dict(order) if order else None
        except Exception as e:
            logger.error(f"✗ Get order failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_pending_orders(self, symbol: str) -> List[Dict]:
        """Get all pending orders for a symbol"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM orders WHERE symbol = %s AND status = 'pending' ORDER BY created_at ASC",
                    (symbol,)
                )
                orders = cur.fetchall()
                return [dict(o) for o in orders]
        except Exception as e:
            logger.error(f"✗ Get pending orders failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_user_orders(self, user_id: int) -> List[Dict]:
        """Get all orders for a user"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                orders = cur.fetchall()
                return [dict(o) for o in orders]
        except Exception as e:
            logger.error(f"✗ Get user orders failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def update_order_status(self, order_id: int, status: str, executed_price: Optional[float] = None) -> None:
        """Update order status (executed, cancelled, etc)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE orders 
                    SET status = %s, executed_price = %s, executed_at = %s
                    WHERE id = %s
                """, (status, executed_price, datetime.now() if status == 'executed' else None, order_id))
                conn.commit()
                logger.info(f"✓ Order {order_id} status updated to {status}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Update order status failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def cancel_order(self, order_id: int) -> None:
        """Cancel order"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE orders 
                    SET status = 'cancelled'
                    WHERE id = %s AND status = 'pending'
                """, (order_id,))
                conn.commit()
                logger.info(f"✓ Order {order_id} cancelled")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Cancel order failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== TRADE OPERATIONS ==========
    
    def create_trade(self, user_id: int, order_id: int, symbol: str, quantity: int, 
                    entry_price: float, entry_time: datetime) -> int:
        """Create new trade (from executed order)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trades (user_id, order_id, symbol, quantity, entry_price, entry_time, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, order_id, symbol, quantity, entry_price, entry_time, 'open', datetime.now()))
                trade_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Trade created: {quantity} {symbol} @ {entry_price} (ID: {trade_id})")
                return trade_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Trade creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_user_trades(self, user_id: int, limit: int = 100) -> List[Dict]:
        """Get user's trade history"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM trades WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit)
                )
                trades = cur.fetchall()
                return [dict(t) for t in trades]
        except Exception as e:
            logger.error(f"✗ Get user trades failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def close_trade(self, trade_id: int, exit_price: float, exit_time: datetime) -> None:
        """Close trade and calculate PnL"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Get trade details
                cur.execute(
                    "SELECT quantity, entry_price FROM trades WHERE id = %s",
                    (trade_id,)
                )
                result = cur.fetchone()
                if not result:
                    raise ValueError("Trade not found")
                
                quantity, entry_price = result
                pnl = (exit_price - entry_price) * quantity
                pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                # Update trade
                cur.execute("""
                    UPDATE trades 
                    SET exit_price = %s, exit_time = %s, pnl = %s, pnl_pct = %s, status = 'closed'
                    WHERE id = %s
                """, (exit_price, exit_time, pnl, pnl_pct, trade_id))
                
                conn.commit()
                logger.info(f"✓ Trade {trade_id} closed: PnL = {pnl}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Close trade failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def execute_market_order(self, user_id: int, symbol: str, side: str, quantity: int, price: float, is_limit_execution: bool = False, existing_order_id: Optional[int] = None) -> Dict:
        """
        Atomically execute a market order (or trigger a limit order):
        1. Validate Funds/Holdings
        2. Create Order (Executed) OR Update existing LIMIT order
        3. Create Trade
        4. Update Position
        5. Update Portfolio Cash
        """
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Fetch Portfolio
                cur.execute("SELECT * FROM portfolios WHERE user_id = %s AND symbol = %s FOR UPDATE", (user_id, symbol))
                portfolio = cur.fetchone()
                if not portfolio:
                     # Create if missing (rare case in this flow but safe)
                    cur.execute("""
                        INSERT INTO portfolios (user_id, symbol, total_capital, cash_available, created_at, updated_at)
                        VALUES (%s, %s, 1000000.00, 1000000.00, NOW(), NOW())
                        RETURNING *
                    """, (user_id, symbol))
                    portfolio = cur.fetchone()

                total_cost = price * quantity
                
                if side.upper() == "BUY":
                    if float(portfolio['cash_available']) < total_cost:
                        raise ValueError(f"Insufficient funds. Required: {total_cost}, Available: {portfolio['cash_available']}")
                    
                    cash_change = -total_cost
                    qty_change = quantity
                    
                elif side.upper() == "SELL":
                    # Check Holdings
                    cur.execute("SELECT quantity FROM positions WHERE user_id = %s AND symbol = %s", (user_id, symbol))
                    pos = cur.fetchone()
                    current_qty = pos['quantity'] if pos else 0
                    
                    if current_qty < quantity:
                        raise ValueError(f"Insufficient holdings. Required: {quantity}, Owned: {current_qty}")
                        
                    cash_change = total_cost
                    qty_change = -quantity
                else:
                    raise ValueError("Invalid side")

                # 2. Handle Order Record
                if is_limit_execution and existing_order_id:
                    # Lock the row to prevent race condition (two threads seeing same pending order)
                    cur.execute(
                        "SELECT id, status, parent_order_id FROM orders WHERE id = %s FOR UPDATE",
                        (existing_order_id,)
                    )
                    locked_order = cur.fetchone()
                    if not locked_order or locked_order['status'] != 'pending':
                        raise ValueError(f"Order {existing_order_id} is no longer pending — skipping execution.")

                    cur.execute("""
                        UPDATE orders
                        SET status = 'executed', executed_price = %s, executed_at = NOW()
                        WHERE id = %s
                        RETURNING id
                    """, (price, existing_order_id))
                    order_id = cur.fetchone()['id']

                    # OCO / BRACKET: atomically cancel all sibling orders linked to the same parent
                    parent_id = locked_order['parent_order_id']
                    if parent_id is not None:
                        cur.execute("""
                            UPDATE orders
                            SET status = 'cancelled'
                            WHERE parent_order_id = %s
                              AND id != %s
                              AND status = 'pending'
                        """, (parent_id, existing_order_id))
                        cancelled = cur.rowcount
                        if cancelled:
                            logger.info(f"✓ OCO/Bracket: cancelled {cancelled} sibling order(s) for parent {parent_id}")

                    # Standalone OCO: cancel the other leg sharing the same oco_group_id
                    oco_group_id = locked_order.get('oco_group_id')
                    if oco_group_id is not None:
                        cur.execute("""
                            UPDATE orders
                            SET status = 'cancelled'
                            WHERE oco_group_id = %s
                              AND id != %s
                              AND status = 'pending'
                        """, (oco_group_id, existing_order_id))
                        cancelled_oco = cur.rowcount
                        if cancelled_oco:
                            logger.info(f"✓ OCO: cancelled {cancelled_oco} paired leg(s) for group {oco_group_id}")
                else:
                    # Create a new market order
                    cur.execute("""
                        INSERT INTO orders (
                            user_id, symbol, order_type, quantity, price, executed_price,
                            status, execution_mode, created_at, executed_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'executed', 'MARKET', NOW(), NOW())
                        RETURNING id
                    """, (user_id, symbol, side.lower(), quantity, price, price))
                    order_id = cur.fetchone()['id']

                # 3. Create Trade
                cur.execute("""
                    INSERT INTO trades (user_id, order_id, symbol, quantity, entry_price, entry_time, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), 'open', NOW())
                    RETURNING id
                """, (user_id, order_id, symbol, quantity, price))
                trade_id = cur.fetchone()['id']

                # 4. Update Position (Upsert)
                cur.execute("""
                    INSERT INTO positions (user_id, symbol, quantity, entry_price, current_price, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'open', NOW(), NOW())
                    ON CONFLICT (user_id, symbol) 
                    DO UPDATE SET 
                        quantity = positions.quantity + %s,
                        current_price = %s,
                        updated_at = NOW()
                """, (user_id, symbol, quantity if side.upper() == "BUY" else 0, price, price, qty_change, price))

                # 5. Update Portfolio Cash
                cur.execute("""
                    UPDATE portfolios 
                    SET cash_available = cash_available + %s, updated_at = NOW()
                    WHERE id = %s
                """, (cash_change, portfolio['id']))

                conn.commit()
                logger.info(f"✓ Executed {side} {quantity} {symbol} @ {price}")
                
                return {"status": "executed", "order_id": order_id, "trade_id": trade_id, "price": price}

        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Market Execution Failed: {e}")
            raise e
        finally:
            self.return_connection(conn)


    # ========== MARKET TICKS OPERATIONS ==========
    
    def batch_insert_ticks(self, ticks: List[Dict]) -> None:
        """Batch insert market ticks (for performance)"""
        if not ticks:
            return
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Prepare data
                data = [
                    (tick['time'], tick['symbol'], tick['price'], tick.get('bid'), 
                     tick.get('ask'), tick.get('volume', 0))
                    for tick in ticks
                ]
                
                # Batch insert
                cur.executemany("""
                    INSERT INTO market_ticks (time, symbol, price, bid, ask, volume)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, data)
                
                conn.commit()
                logger.info(f"✓ Batch inserted {len(ticks)} ticks")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Batch insert ticks failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def insert_tick(self, symbol: str, price: float, bid: float, ask: float, volume: int = 0) -> None:
        """Insert single market tick"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO market_ticks (time, symbol, price, bid, ask, volume)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (datetime.now(), symbol, price, bid, ask, volume))
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Insert tick failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_recent_ticks(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Get recent market ticks"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM market_ticks 
                    WHERE symbol = %s 
                    ORDER BY time DESC 
                    LIMIT %s
                """, (symbol, limit))
                ticks = cur.fetchall()
                return [dict(t) for t in reversed(ticks)]  # Return in ascending order
        except Exception as e:
            logger.error(f"✗ Get recent ticks failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== CANDLES OPERATIONS ==========
    
    def insert_candle(self, symbol: str, time: datetime, open_price: float, high: float, 
                     low: float, close: float, volume: int) -> None:
        """Insert 1-minute candle"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO candles_1m (time, symbol, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, time) DO UPDATE SET
                    open = %s, high = %s, low = %s, close = %s, volume = %s
                """, (time, symbol, open_price, high, low, close, volume,
                      open_price, high, low, close, volume))
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Insert candle failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_candles(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get 1-minute candles"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM candles_1m 
                    WHERE symbol = %s 
                    ORDER BY time DESC 
                    LIMIT %s
                """, (symbol, limit))
                candles = cur.fetchall()
                return [dict(c) for c in reversed(candles)]
        except Exception as e:
            logger.error(f"✗ Get candles failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== STRATEGY OPERATIONS ==========

    def create_strategy(self, user_id: int, name: str, rules_json: dict) -> int:
        """Persist a new algorithmic strategy DSL for a user"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO strategies (user_id, name, rules_json, status, created_at, updated_at)
                    VALUES (%s, %s, %s, 'active', NOW(), NOW())
                    RETURNING id
                """, (user_id, name, json.dumps(rules_json)))
                strat_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Strategy created: '{name}' for user {user_id} (ID: {strat_id})")
                return strat_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Strategy creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_user_strategies(self, user_id: int) -> List[Dict]:
        """Fetch all strategies for a user, ordered newest first"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM strategies WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                return [dict(s) for s in cur.fetchall()]
        except Exception as e:
            logger.error(f"✗ Get user strategies failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_active_strategies(self) -> List[Dict]:
        """Fetch ALL active strategies across all users (used by the strategy engine worker)"""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM strategies WHERE status = 'active'")
                return [dict(s) for s in cur.fetchall()]
        except Exception as e:
            logger.error(f"✗ Get active strategies failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def update_strategy_status(self, strategy_id: int, user_id: int, status: str) -> None:
        """Pause or re-activate a strategy (user-scoped for isolation)"""
        if status not in ('active', 'paused'):
            raise ValueError("Strategy status must be 'active' or 'paused'")
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE strategies
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                """, (status, strategy_id, user_id))
                if cur.rowcount == 0:
                    raise ValueError(f"Strategy {strategy_id} not found or not owned by user {user_id}")
                conn.commit()
                logger.info(f"✓ Strategy {strategy_id} status → {status}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Strategy update failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def delete_strategy(self, strategy_id: int, user_id: int) -> None:
        """Permanently delete a strategy, enforcing user ownership."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM strategies WHERE id = %s AND user_id = %s",
                    (strategy_id, user_id)
                )
                if cur.rowcount == 0:
                    raise ValueError(f"Strategy {strategy_id} not found or not owned by user {user_id}")
                conn.commit()
                logger.info(f"✓ Strategy {strategy_id} deleted by user {user_id}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Strategy deletion failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    # ========== TRADE JOURNAL OPERATIONS ==========

    def get_trade(self, trade_id: int, user_id: int) -> Optional[Dict]:
        """Fetch a specific trade enforcing user ownership."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM trades WHERE id = %s AND user_id = %s", (trade_id, user_id))
                trade = cur.fetchone()
                return dict(trade) if trade else None
        except Exception as e:
            logger.error(f"✗ Get trade failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def create_trade_journal(self, trade_id: int, entry_reason: str = None, entry_snapshot_path: str = None) -> int:
        """Create a journal entry attached to a trade at entry time"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trade_journals (trade_id, entry_reason, entry_snapshot_path, created_at)
                    VALUES (%s, %s, %s, NOW())
                    RETURNING id
                """, (trade_id, entry_reason, entry_snapshot_path))
                journal_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Trade journal created for trade {trade_id} (ID: {journal_id})")
                return journal_id
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Trade journal creation failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def update_trade_journal_exit(
        self, trade_id: int, exit_reason: str = None, exit_snapshot_path: str = None
    ) -> None:
        """Attach exit metadata to an existing journal entry"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE trade_journals
                    SET exit_reason          = COALESCE(%s, exit_reason),
                        exit_snapshot_path   = COALESCE(%s, exit_snapshot_path)
                    WHERE trade_id = %s
                """, (exit_reason, exit_snapshot_path, trade_id))
                conn.commit()
                logger.info(f"✓ Trade journal exit updated for trade {trade_id}")
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Trade journal exit update failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_trade_journal(self, user_id: int) -> List[Dict]:
        """Fetch all journal entries for a user, enriched with trade metadata (newest first)."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        tj.id,
                        tj.trade_id,
                        tj.entry_reason,
                        tj.exit_reason,
                        tj.entry_snapshot_path,
                        tj.exit_snapshot_path,
                        tj.created_at,
                        t.symbol,
                        t.order_type     AS side,
                        t.quantity,
                        t.price          AS execution_price,
                        t.pnl
                    FROM trade_journals tj
                    JOIN trades t ON t.id = tj.trade_id
                    WHERE t.user_id = %s
                    ORDER BY tj.created_at DESC
                """, (user_id,))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"✗ Get trade journal failed: {e}")
            raise
        finally:
            self.return_connection(conn)

    def get_trade_journal_by_id(self, trade_id: int, user_id: int) -> Optional[Dict]:
        """Fetch the journal for a specific trade, enforcing user ownership."""
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT tj.*
                    FROM trade_journals tj
                    JOIN trades t ON t.id = tj.trade_id
                    WHERE tj.trade_id = %s AND t.user_id = %s
                """, (trade_id, user_id))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"✗ Get trade journal by id failed: {e}")
            raise
        finally:
            self.return_connection(conn)