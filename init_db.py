import logging
from database import DatabaseHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("INIT_DB")

def init_db():
    logger.info("Starting initial database schema creation...")
    db = DatabaseHandler()
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            # Read the schema file
            with open("db/schema.sql", "r") as f:
                schema_sql = f.read()
                
            # Execute the schema script
            cur.execute(schema_sql)
            conn.commit()
            logger.info("✅ Database initialized successfully: all tables created.")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Database initialization failed: {e}")
    finally:
        db.return_connection(conn)

if __name__ == "__main__":
    init_db()
