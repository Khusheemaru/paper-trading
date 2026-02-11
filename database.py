import psycopg2
from psycopg2.pool import SimpleConnectionPool
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
            self.pool = SimpleConnectionPool(
                1, 5,  # minconn=1, maxconn=5
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
    
    def create_order(self, user_id: int, symbol: str, order_type: str, quantity: int, price: Optional[float] = None) -> int:
        """Create new order (MARKET or LIMIT)"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO orders (user_id, symbol, order_type, quantity, price, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, symbol, order_type.upper(), quantity, price, 'pending', datetime.now()))
                order_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"✓ Order created: {order_type} {quantity} {symbol} (ID: {order_id})")
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