from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import json
import asyncio
import config
import logging
import time
from database import DatabaseHandler

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

# --- INITIALIZE APP ---
app = FastAPI(title="HedgeBot India API")

# 1. DATABASE CONNECTION
db = DatabaseHandler()

# 2. CORS MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REDIS CONNECTION ---
try:
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB, decode_responses=True)
    r.ping()
    logger.info("✅ Connected to Redis")
except Exception as e:
    logger.error(f"❌ Redis Connection Failed: {e}")

# --- CONSTANTS & MODELS ---
DEMO_USER_ID = 1  # We use a single user for this local project

class OrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    price: float = 0.0 # 0 for Market Orders

# --- STARTUP EVENT (Auto-Setup) ---
@app.on_event("startup")
def startup_db_setup():
    """Ensures a Demo User and Portfolio exist when server starts"""
    try:
        # 1. Check/Create User
        user = db.get_user_by_id(DEMO_USER_ID)
        if not user:
            logger.info("⚙️ Creating Demo User...")
            try:
                db.create_user("trader", "trader@hedgebot.com", "hashed_secret")
            except:
                pass # User might exist via email
        
        # 2. Check/Create Portfolio
        portfolio = db.get_portfolio(DEMO_USER_ID, config.PRIMARY_SYMBOL)
        if not portfolio:
            logger.info(f"⚙️ Creating Initial Portfolio for {config.PRIMARY_SYMBOL}...")
            db.create_portfolio(DEMO_USER_ID, config.PRIMARY_SYMBOL, 1000000.0) # ₹10 Lakhs

    except Exception as e:
        logger.error(f"Startup setup failed (Non-critical if DB already set): {e}")

# ==========================================
#  PAPER TRADING API ENDPOINTS (NEW)
# ==========================================

@app.get("/account")
def get_account_summary():
    """Get Cash Balance and PnL"""
    portfolio = db.get_portfolio(DEMO_USER_ID, config.PRIMARY_SYMBOL)
    if not portfolio:
        return {"error": "Portfolio not found"}
    
    # Calculate Total PnL from open positions
    positions = db.get_all_positions(DEMO_USER_ID)
    unrealized_pnl = sum(p['unrealized_pnl'] for p in positions)
    
    return {
        "cash": float(portfolio['cash_available']),
        "invested": float(portfolio['total_capital']) - float(portfolio['cash_available']),
        "current_pnl": float(unrealized_pnl)
    }

@app.get("/positions")
def get_positions():
    """Get currently held positions"""
    positions = db.get_all_positions(DEMO_USER_ID)
    return positions

@app.get("/orders")
def get_orders():
    """Get order history"""
    orders = db.get_user_orders(DEMO_USER_ID)
    return orders

@app.post("/place_order")
def place_order(order: OrderRequest):
    """Manual Order Placement (Optional UI feature)"""
    try:
        # Create the order in DB
        order_id = db.create_order(
            user_id=DEMO_USER_ID,
            symbol=order.symbol,
            order_type=order.side, # BUY/SELL is technically the side, we map to order_type
            quantity=order.quantity,
            price=order.price if order.price > 0 else None
        )
        return {"status": "submitted", "order_id": order_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==========================================
#  EXISTING MARKET DATA ENDPOINTS
# ==========================================

@app.websocket("/ws/market_data")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ Client Connected to WebSocket")
    
    try:
        while True:
            # 1. Fetch latest data from Redis
            keys = [
                f"price:{config.PRIMARY_SYMBOL}",
                f"bid:{config.PRIMARY_SYMBOL}",
                f"ask:{config.PRIMARY_SYMBOL}",
                f"spread:{config.PRIMARY_SYMBOL}"
            ]
            values = r.mget(keys)
            
            # 2. Package into JSON
            if values[0]: # Check if data exists
                data = {
                    "symbol": config.PRIMARY_SYMBOL,
                    "price": float(values[0]),
                    "bid": float(values[1]),
                    "ask": float(values[2]),
                    "spread": float(values[3]),
                    "timestamp": int(time.time()) 
                }
                
                # 3. Send to Client
                await websocket.send_json(data)
            
            # 4. Throttle (30 FPS)
            await asyncio.sleep(0.033) 
            
    except WebSocketDisconnect:
        logger.info("❌ Client Disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")

@app.get("/history")
def get_history():
    """Returns the last 500 ticks so the chart doesn't look empty"""
    raw_data = db.get_recent_ticks(config.PRIMARY_SYMBOL, limit=500)
    formatted_data = []

    for row in raw_data:
        # Convert Postgres timestamp to Unix Integer
        ts = int(row['time'].timestamp())
        formatted_data.append({
            "time": ts,
            "value": float(row['price'])
        })
        
    return formatted_data

@app.get("/")
def health_check():
    return {"status": "running", "service": "HedgeBot India API"}