import requests
import json

BASE_URL = "http://localhost:8000"

print("1. Logging in as trader@hedgebot.com...")
resp = requests.post(f"{BASE_URL}/login", json={
    "email": "trader@hedgebot.com",
    "password": "password"
})

if resp.status_code != 200:
    print("Login failed!", resp.text)
    exit(1)

token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"Login successful. Token: {token[:20]}...\n")

print("2. Creating a new Strategy...")
strategy_payload = {
  "name": "RSI Oversold Buy Tester",
  "rules_json": {
    "symbol": "NIFTY",
    "condition": {
      "AND": [
        {"indicator": "RSI", "period": 14, "operator": "<", "value": 70}
      ]
    },
    "action": "BUY",
    "quantity_pct": 50,
    "order_mode": "MARKET"
  }
}

resp = requests.post(f"{BASE_URL}/strategies", headers=headers, json=strategy_payload)
print("Create Response:", resp.status_code, resp.text)

print("\n3. Fetching your active strategies...")
resp = requests.get(f"{BASE_URL}/strategies", headers=headers)
print("Get Response:", resp.status_code, json.dumps(resp.json(), indent=2))
