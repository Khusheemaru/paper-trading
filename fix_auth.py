import logging
from database import DatabaseHandler
from server import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FIX_AUTH")

def fix_auth():
    logger.info("Fixing trader password...")
    db = DatabaseHandler()
    conn = db.get_connection()
    try:
        hashed_pw = get_password_hash("password")
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET password_hash = %s WHERE email = 'trader@hedgebot.com';
            """, (hashed_pw,))
            conn.commit()
            logger.info("✅ Password fixed!")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to fix password: {e}")
    finally:
        db.return_connection(conn)

if __name__ == "__main__":
    fix_auth()
