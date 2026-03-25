import psycopg2
from passlib.context import CryptContext
import config
import sys

# Setup colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def check_hashing():
    print("1. Checking Password Hashing (passlib + bcrypt)...", end=" ")
    try:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hash_out = pwd_context.hash("test1234")
        if pwd_context.verify("test1234", hash_out):
            print(f"{GREEN}OK{RESET}")
            return True
        else:
            print(f"{RED}FAILED (Verification failed){RESET}")
            return False
    except Exception as e:
        print(f"{RED}FAILED{RESET}")
        print(f"   Error: {e}")
        return False

def check_db():
    print("2. Checking Database Connection...", end=" ")
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASS
        )
        print(f"{GREEN}OK{RESET}")
        
        print("3. Checking Database Schema...", end=" ")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            required_tables = {'users', 'portfolios', 'positions', 'orders', 'trades'}
            missing = required_tables - set(tables)
            
            if not missing:
                print(f"{GREEN}OK{RESET}")
                return True
            else:
                print(f"{RED}FAILED{RESET}")
                print(f"   Missing tables: {missing}")
                return False
    except Exception as e:
        print(f"{RED}FAILED{RESET}")
        print(f"   Error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("--- DIAGNOSTIC START ---")
    hashing_ok = check_hashing()
    db_ok = check_db()
    print("--- DIAGNOSTIC END ---")
    
    if hashing_ok and db_ok:
        print(f"\n{GREEN}✅ System checks passed. The 500 error might be logic-related.{RESET}")
    else:
        print(f"\n{RED}❌ System checks failed. Fix the issues above.{RESET}")
