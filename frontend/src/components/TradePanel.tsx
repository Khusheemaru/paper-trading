import { useState } from "react";

interface TradePanelProps {
  token: string;
  currentPrice: number;
  cashAvailable: number;
  symbol: string;
  onTradeComplete: () => void;
}

export default function TradePanel({
  token,
  currentPrice,
  cashAvailable,
  symbol,
  onTradeComplete,
}: TradePanelProps) {
  const [quantity, setQuantity] = useState(1);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [executionMode, setExecutionMode] = useState<"MARKET" | "LIMIT">("MARKET");
  const [limitPrice, setLimitPrice] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const estimatedCost = currentPrice * quantity;
  const canAfford = side === "BUY" ? estimatedCost <= cashAvailable : true;

  const handleTrade = async () => {
    setLoading(true);
    setMessage("");

    try {
      const payload = {
        symbol: symbol,
        side,
        quantity,
        price: executionMode === "LIMIT" ? limitPrice : 0, // Backend ignores price for market orders
        execution_mode: executionMode
      };

      const response = await fetch("http://localhost:8000/place_order", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(
          `✅ ${side} ${quantity} @ ₹${data.price?.toFixed(2) || currentPrice.toFixed(2)}`
        );
        onTradeComplete();
      } else {
        setMessage(`❌ ${data.detail || "Order failed"}`);
      }
    } catch (err: any) {
      setMessage(`❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
      <div style={{
        background: "#0d0d18",
        padding: "20px",
        borderRadius: "10px",
        border: "1px solid #1e1e2e",
        marginBottom: "20px",
      }}>
        <h3 style={{ marginTop: 0, color: "#e0e0e0", fontSize: "15px", fontWeight: 600 }}>
          Place Order — <span style={{ color: "#00e5ff" }}>{symbol}</span>
        </h3>

      <div style={{ marginBottom: "15px" }}>
        <label style={{ display: "block", marginBottom: "5px", color: "#aaa" }}>
          Side
        </label>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={() => setSide("BUY")}
            style={{
              ...sideButtonStyle,
              background: side === "BUY" ? "#0f0" : "#2a2a2a",
              color: side === "BUY" ? "#000" : "#fff",
            }}
          >
            BUY
          </button>
          <button
            onClick={() => setSide("SELL")}
            style={{
              ...sideButtonStyle,
              background: side === "SELL" ? "#f00" : "#2a2a2a",
              color: side === "SELL" ? "#fff" : "#fff",
            }}
          >
            SELL
          </button>
        </div>
      </div>

      {/* Order Type Toggle: Market vs Limit */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "15px" }}>
        <button
          onClick={() => setExecutionMode("MARKET")}
          style={{
            flex: 1, padding: "8px", border: "1px solid #1e1e2e", borderRadius: "5px",
            background: executionMode === "MARKET" ? "#1e1e2e" : "transparent", color: "white", cursor: "pointer"
          }}
        >
          MARKET
        </button>
        <button
          onClick={() => setExecutionMode("LIMIT")}
          style={{
            flex: 1, padding: "8px", border: "1px solid #1e1e2e", borderRadius: "5px",
            background: executionMode === "LIMIT" ? "#1e1e2e" : "transparent", color: "white", cursor: "pointer"
          }}
        >
          LIMIT
        </button>
      </div>

      <div style={{ marginBottom: "15px" }}>
        <label style={{ display: "block", marginBottom: "5px", color: "#aaa" }}>
          Quantity
        </label>
        <input
          type="number"
          min="1"
          value={quantity}
          onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
          style={{
            width: "100%",
            padding: "10px",
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "6px",
            color: "#fff",
          }}
        />
      </div>

      {/* Limit Price Input (only if LIMIT selected) */}
      {executionMode === "LIMIT" && (
        <div style={{ marginBottom: "15px" }}>
          <label style={{ display: "block", marginBottom: "5px", color: "#888" }}>
            Limit Price (Ask/Bid)
          </label>
          <input
            type="number"
            min="1"
            step="0.05"
            value={limitPrice}
            onChange={(e) => setLimitPrice(Number(e.target.value))}
            style={{
              width: "100%", padding: "10px", borderRadius: "5px",
              border: "1px solid #333", background: "#111", color: "white"
            }}
          />
        </div>
      )}

      <div
        style={{
          marginBottom: "15px",
          padding: "10px",
          background: "#2a2a2a",
          borderRadius: "6px",
        }}
      >
        <div style={{ color: "#aaa", fontSize: "14px" }}>Estimated Cost</div>
        <div style={{ fontSize: "18px", fontWeight: "bold" }}>
          ₹{estimatedCost.toFixed(2)}
        </div>
      </div>

      <button
        onClick={handleTrade}
        disabled={loading || !canAfford}
        style={{
          width: "100%",
          padding: "12px",
          background: canAfford ? "#2962FF" : "#555",
          border: "none",
          borderRadius: "6px",
          color: "#fff",
          fontSize: "16px",
          fontWeight: "bold",
          cursor: canAfford ? "pointer" : "not-allowed",
          opacity: loading ? 0.6 : 1,
        }}
      >
        {loading ? "Processing..." : `Place ${side} Order`}
      </button>

      {!canAfford && side === "BUY" && (
        <div style={{ color: "#f00", fontSize: "14px", marginTop: "10px" }}>
          Insufficient funds
        </div>
      )}

      {message && (
        <div
          style={{
            marginTop: "15px",
            padding: "10px",
            background: "#2a2a2a",
            borderRadius: "6px",
            fontSize: "14px",
          }}
        >
          {message}
        </div>
      )}
    </div>
  );
}

const sideButtonStyle: React.CSSProperties = {
  flex: 1,
  padding: "10px",
  border: "none",
  borderRadius: "6px",
  fontWeight: "bold",
  cursor: "pointer",
};
