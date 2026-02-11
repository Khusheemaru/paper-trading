import config
import redis
import time
import random
import json
import logging
from database import DatabaseHandler

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# 1. Initialize Database
# The connection pool is initialized automatically in __init__
db = DatabaseHandler()

# 2. Initialize Redis
try:
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB, decode_responses=True)
    r.ping() 
    logging.info(f"✅ [REDIS] Connected to {config.REDIS_HOST}:{config.REDIS_PORT}")
except Exception as e:
    logging.error(f"❌ [REDIS] Connection Failed: {e}")
    exit(1)

# --- CONFIG MAPPING ---
# Ensure we use the primary symbol from config
CURRENT_SYMBOL = config.PRIMARY_SYMBOL 

# MODE A: THE SIMULATOR (Mock Data)
def run_mock_stream():
    logging.info(f"[MODE: MOCK] Starting {CURRENT_SYMBOL} Simulator...")
    
    price = 24500.00  
    
    while True:
        try:
            # 1. Simulate Price Movement
            change = random.uniform(-10.0, 10.0) 
            price += change
            
            # 2. Simulate Spread
            spread = random.uniform(0.05, 1.50)
            bid = price - (spread / 2)
            ask = price + (spread / 2)
            
            # Simulate Volume (optional, but good for your new DB schema)
            volume = random.randint(50, 500)
            
            # 3. Push to Redis
            pipe = r.pipeline()
            pipe.set(f"price:{CURRENT_SYMBOL}", round(price, 2))
            pipe.set(f"bid:{CURRENT_SYMBOL}", round(bid, 2))
            pipe.set(f"ask:{CURRENT_SYMBOL}", round(ask, 2))
            pipe.set(f"spread:{CURRENT_SYMBOL}", round(spread, 2))
            pipe.execute()
            
            # 4. Save to DB 
            # Note: We do NOT pass timestamp anymore, database.py handles it.
            # Signature: insert_tick(symbol, price, bid, ask, volume)
            db.insert_tick(CURRENT_SYMBOL, price, bid, ask, volume)
            
            logging.info(f"[MOCK] {CURRENT_SYMBOL}: ₹{price:.2f} | Spread: ₹{spread:.2f}")
            
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            logging.info("[STOP] Simulator stopped by user.")
            break
        except Exception as e:
            logging.error(f"!! Error: {e}")
            time.sleep(1)

# MODE B: REAL MARKET DATA (Angel One)
def run_live_stream():
    try:
        from smartapi import SmartConnect, SmartWebSocket
    except ImportError:
        logging.error("❌ Library 'smartapi-python' not found.")
        return

    logging.info(f"🚀 [MODE: LIVE] Connecting to Angel One...")

    try:
        obj = SmartConnect(api_key=config.INDIAN_API_KEY)
        data = obj.generateSession(config.INDIAN_CLIENT_CODE, config.INDIAN_PASSWORD, config.TOTP_SECRET)
        feed_token = obj.getfeedToken()
        logging.info("✅ [API] Session Generated & Token Received")
    except Exception as e:
        logging.error(f"❌ [API] Login Failed: {e}")
        return

    def on_message(ws, message):
        try:
            # Check if message contains LTP (Last Traded Price)
            if "ltp" in message:
                ltp = float(message.get('ltp'))
                best_bid = float(message.get('bp', ltp)) 
                best_ask = float(message.get('sp', ltp))
                spread = best_ask - best_bid
                
                # Angel One often sends volume as 'v' or 'vol'
                # We use 0 if not found to prevent errors
                volume = int(message.get('v', 0)) 

                # Push to Redis
                r.set(f"price:{CURRENT_SYMBOL}", ltp)
                r.set(f"bid:{CURRENT_SYMBOL}", best_bid)
                r.set(f"ask:{CURRENT_SYMBOL}", best_ask)
                r.set(f"spread:{CURRENT_SYMBOL}", spread)
                
                # Insert into DB
                # Note: We do NOT pass timestamp, database.py uses datetime.now()
                db.insert_tick(CURRENT_SYMBOL, ltp, best_bid, best_ask, volume)

                print(f"⚡ [LIVE] {CURRENT_SYMBOL}: ₹{ltp:.2f}")
                
        except Exception as e:
            logging.error(f"Parse Error: {e}")

    def on_open(ws):
        logging.info("✅ [WS] WebSocket Connection Established")
        subscribe_packet = {
            "action": "subscribe", 
            "mode": 2, 
            "exchangeType": "nse_cm", 
            "tokens": [config.SYMBOL_TOKEN] 
        }
        ws.send(json.dumps(subscribe_packet))

    def on_error(ws, error):
        logging.error(f"❌ [WS] Error: {error}")

    sws = SmartWebSocket(feed_token, config.INDIAN_CLIENT_CODE)
    sws._on_open = on_open
    sws._on_message = on_message
    sws._on_error = on_error
    sws.connect()

if __name__ == "__main__":
    if config.USE_MOCK_DATA:
        run_mock_stream()
    else:
        run_live_stream()