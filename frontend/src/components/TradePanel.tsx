/**
 * TradePanel.tsx — Advanced Order Ticket (Phase 5)
 *
 * Tabs: MARKET | LIMIT | TRAILING SL | OCO | BRACKET
 * Backwards-compatible: MARKET and LIMIT behave identically to before.
 * Advanced modes send the new execution_mode field to /place_order.
 */

import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type ExecMode = "MARKET" | "LIMIT" | "TRAILING" | "OCO" | "BRACKET";

interface TradePanelProps {
  token: string;
  currentPrice: number;
  cashAvailable: number;
  symbol: string;
  onTradeComplete: () => void;
}

const TABS: { mode: ExecMode; label: string }[] = [
  { mode: "MARKET",   label: "Market"   },
  { mode: "LIMIT",    label: "Limit"    },
  { mode: "TRAILING", label: "Trail SL" },
  { mode: "OCO",      label: "OCO"      },
  { mode: "BRACKET",  label: "Bracket"  },
];

// ── Shared Styles ────────────────────────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  width: "100%", padding: "9px 12px",
  background: "#111", border: "1px solid #2a2a3e",
  borderRadius: "8px", color: "#e0e0e0", fontSize: "13px",
  boxSizing: "border-box",
};

const labelStyle: React.CSSProperties = {
  display: "block", marginBottom: "5px",
  color: "#666", fontSize: "11px",
  textTransform: "uppercase", letterSpacing: "0.8px",
};

const fieldBox: React.CSSProperties = { marginBottom: "14px" };

// ── Component ────────────────────────────────────────────────────────────────
export default function TradePanel({
  token, currentPrice, cashAvailable, symbol, onTradeComplete,
}: TradePanelProps) {
  const [tab,           setTab          ] = useState<ExecMode>("MARKET");
  const [side,          setSide         ] = useState<"BUY" | "SELL">("BUY");
  const [quantity,      setQuantity     ] = useState(1);
  const [limitPrice,    setLimitPrice   ] = useState(currentPrice);
  const [trailingOffset,setTrailingOffset] = useState(50);
  const [ocoLeg1,       setOcoLeg1     ] = useState(currentPrice * 1.02);
  const [ocoLeg2,       setOcoLeg2     ] = useState(currentPrice * 0.98);
  const [bracketEntry,  setBracketEntry ] = useState(currentPrice);
  const [bracketTP,     setBracketTP   ] = useState(currentPrice * 1.03);
  const [bracketSL,     setBracketSL   ] = useState(currentPrice * 0.97);
  const [loading,       setLoading      ] = useState(false);
  const [message,       setMessage      ] = useState("");
  const [msgType,       setMsgType      ] = useState<"ok" | "err">("ok");

  const estimatedCost = tab === "MARKET" ? currentPrice * quantity : (limitPrice || currentPrice) * quantity;
  const canAfford     = side === "BUY" ? estimatedCost <= cashAvailable : true;

  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  const showMsg = (text: string, type: "ok" | "err") => { setMessage(text); setMsgType(type); };

  const placeOrder = async (payload: object) => {
    setLoading(true); setMessage("");
    try {
      const res  = await fetch(`${API_BASE}/place_order`, { method: "POST", headers, body: JSON.stringify(payload) });
      const data = await res.json();
      if (res.ok) {
        showMsg(`✅ ${side} ${quantity} ${symbol} — ${tab === "MARKET" ? `₹${data.price?.toFixed(2) ?? currentPrice.toFixed(2)}` : "Order placed"}`, "ok");
        onTradeComplete();
      } else {
        showMsg(`❌ ${data.detail || "Order failed"}`, "err");
      }
    } catch (e: any) {
      showMsg(`❌ ${e.message}`, "err");
    } finally { setLoading(false); }
  };

  const handleSubmit = () => {
    const base = { symbol, side, quantity };

    if (tab === "MARKET")   return placeOrder({ ...base, price: 0, execution_mode: "MARKET" });
    if (tab === "LIMIT")    return placeOrder({ ...base, price: limitPrice, execution_mode: "LIMIT" });
    if (tab === "TRAILING") return placeOrder({ ...base, price: currentPrice, execution_mode: "TRAILING",
                                                trailing_offset: trailingOffset });
    if (tab === "OCO")      return placeOrder({ ...base, price: ocoLeg1, execution_mode: "OCO",
                                                oco_limit_price: ocoLeg2 });
    if (tab === "BRACKET")  return placeOrder({ ...base, price: bracketEntry, execution_mode: "BRACKET",
                                                take_profit_price: bracketTP, stop_loss_price: bracketSL });
  };

  return (
    <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", borderRadius: "12px", padding: "20px", marginBottom: "20px" }}>

      <h3 style={{ margin: "0 0 16px", fontSize: "14px", fontWeight: 600, color: "#e0e0e0" }}>
        Place Order — <span style={{ color: "#00e5ff" }}>{symbol}</span>
      </h3>

      {/* ── Mode Tabs ──────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "18px", background: "#111", borderRadius: "8px", padding: "4px" }}>
        {TABS.map(t => (
          <button
            key={t.mode}
            id={`tab-${t.mode}`}
            onClick={() => setTab(t.mode)}
            style={{
              flex: 1, padding: "7px 4px", border: "none", borderRadius: "6px", cursor: "pointer",
              fontSize: "11px", fontWeight: 700,
              background: tab === t.mode ? "#1e1e2e" : "transparent",
              color: tab === t.mode ? "#00e5ff" : "#555",
              transition: "all 0.2s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── BUY / SELL ─────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {(["BUY", "SELL"] as const).map(s => (
          <button
            key={s}
            id={`side-${s}`}
            onClick={() => setSide(s)}
            style={{
              flex: 1, padding: "10px", border: "none", borderRadius: "8px",
              fontWeight: 700, fontSize: "13px", cursor: "pointer", transition: "all 0.2s",
              background: side === s ? (s === "BUY" ? "#00ff88" : "#ff5555") : "#1a1a2e",
              color: side === s ? "#0a0a0f" : "#555",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* ── Quantity ───────────────────────────────────────────────── */}
      <div style={fieldBox}>
        <label style={labelStyle}>Quantity</label>
        <input id="order-quantity" type="number" min={1} style={inputStyle}
          value={quantity} onChange={e => setQuantity(parseInt(e.target.value) || 1)} />
      </div>

      {/* ── Mode-specific Inputs ───────────────────────────────────── */}

      {tab === "LIMIT" && (
        <div style={fieldBox}>
          <label style={labelStyle}>Limit Price (₹)</label>
          <input id="limit-price" type="number" step="0.05" style={inputStyle}
            value={limitPrice} onChange={e => setLimitPrice(Number(e.target.value))} />
        </div>
      )}

      {tab === "TRAILING" && (
        <div style={fieldBox}>
          <label style={labelStyle}>Trailing Offset (₹) — trail triggers when price drops by this amount below peak</label>
          <input id="trailing-offset" type="number" step="1" style={inputStyle}
            value={trailingOffset} onChange={e => setTrailingOffset(Number(e.target.value))} />
          <div style={{ color: "#555", fontSize: "11px", marginTop: "6px" }}>
            Entry: ₹{currentPrice.toFixed(2)} · Trailing gap: ₹{trailingOffset.toFixed(2)}
          </div>
        </div>
      )}

      {tab === "OCO" && (
        <>
          <div style={{ padding: "10px", background: "#0a0a14", borderRadius: "8px", marginBottom: "14px" }}>
            <div style={{ fontSize: "11px", color: "#555", marginBottom: "4px" }}>One-Cancels-Other: First triggered leg executes; the other is cancelled automatically.</div>
          </div>
          <div style={fieldBox}>
            <label style={labelStyle}>Leg 1 Price — Take Profit (₹)</label>
            <input id="oco-leg1" type="number" step="0.05" style={inputStyle}
              value={ocoLeg1} onChange={e => setOcoLeg1(Number(e.target.value))} />
          </div>
          <div style={fieldBox}>
            <label style={labelStyle}>Leg 2 Price — Stop Loss (₹)</label>
            <input id="oco-leg2" type="number" step="0.05" style={inputStyle}
              value={ocoLeg2} onChange={e => setOcoLeg2(Number(e.target.value))} />
          </div>
        </>
      )}

      {tab === "BRACKET" && (
        <>
          <div style={{ padding: "10px", background: "#0a0a14", borderRadius: "8px", marginBottom: "14px" }}>
            <div style={{ fontSize: "11px", color: "#555" }}>Entry fills first, then TP & SL activate simultaneously as linked limit orders.</div>
          </div>
          <div style={fieldBox}>
            <label style={labelStyle}>Entry Limit Price (₹)</label>
            <input id="bracket-entry" type="number" step="0.05" style={inputStyle}
              value={bracketEntry} onChange={e => setBracketEntry(Number(e.target.value))} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div style={fieldBox}>
              <label style={labelStyle}>Take Profit (₹)</label>
              <input id="bracket-tp" type="number" step="0.05" style={inputStyle}
                value={bracketTP} onChange={e => setBracketTP(Number(e.target.value))} />
            </div>
            <div style={fieldBox}>
              <label style={labelStyle}>Stop Loss (₹)</label>
              <input id="bracket-sl" type="number" step="0.05" style={inputStyle}
                value={bracketSL} onChange={e => setBracketSL(Number(e.target.value))} />
            </div>
          </div>
        </>
      )}

      {/* ── Estimated Cost ─────────────────────────────────────────── */}
      {tab !== "OCO" && (
        <div style={{ background: "#111", border: "1px solid #1e1e2e", borderRadius: "8px", padding: "12px", marginBottom: "14px" }}>
          <div style={{ color: "#555", fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "4px" }}>Estimated Cost</div>
          <div style={{ fontSize: "18px", fontWeight: 700, color: canAfford ? "#e0e0e0" : "#ff5555" }}>
            ₹{estimatedCost.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
        </div>
      )}

      {/* ── Submit ─────────────────────────────────────────────────── */}
      <button
        id="place-order-btn"
        onClick={handleSubmit}
        disabled={loading || (side === "BUY" && !canAfford && tab !== "OCO")}
        style={{
          width: "100%", padding: "13px", border: "none", borderRadius: "8px",
          background: (loading || (side === "BUY" && !canAfford)) ? "#555" : "linear-gradient(135deg, #0077ff, #00e5ff)",
          color: "#0a0a0f", fontSize: "14px", fontWeight: 700, cursor: "pointer",
          opacity: loading ? 0.6 : 1, transition: "all 0.2s",
        }}
      >
        {loading ? "Processing..." : `Place ${side} · ${tab}`}
      </button>

      {/* ── Message ────────────────────────────────────────────────── */}
      {message && (
        <div style={{
          marginTop: "12px", padding: "10px 14px", borderRadius: "8px", fontSize: "13px",
          background: msgType === "ok" ? "#0a1a0a" : "#1a0a0a",
          color:      msgType === "ok" ? "#00ff88" : "#ff5555",
          border: `1px solid ${msgType === "ok" ? "#00ff8833" : "#ff555533"}`,
        }}>
          {message}
        </div>
      )}
    </div>
  );
}
