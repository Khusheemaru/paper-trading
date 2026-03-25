import logging
from database import DatabaseHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MIGRATE")

def migrate():
    logger.info("Starting schema migration...")
    db = DatabaseHandler()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(20) DEFAULT 'MARKET'
                CHECK (execution_mode IN ('MARKET', 'LIMIT', 'STOP'));
            """)
            
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_pending_limit
                ON orders(symbol, status, execution_mode)
                WHERE status = 'pending' AND execution_mode IN ('LIMIT', 'STOP');
            """)
            conn.commit()
            logger.info("✅ Migration successful!")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration failed: {e}")
    finally:
        db.return_connection(conn)

if __name__ == "__main__":
    migrate()
