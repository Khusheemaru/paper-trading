/**
 * StrategyBuilder.tsx — Visual Algorithmic Strategy Builder
 *
 * Allows users to define JSON DSL strategies visually without writing code.
 * Maps to the POST /strategies and GET /strategies API endpoints.
 * Supports: SMA, EMA, RSI, MACD, BB, PRICE comparisons with AND logic.
 */

import React, { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

interface StrategyBuilderProps {
  token: string;
}

type Indicator = "RSI" | "SMA" | "EMA" | "MACD" | "BB" | "PRICE";
type Operator  = "<" | ">" | "<=" | ">=" | "==";
type OrderMode = "MARKET" | "BRACKET";
type Action    = "BUY" | "SELL";

interface ConditionRule {
  indicator: Indicator;
  period?:   number;
  field?:    string;          // for MACD.histogram, BB.upper etc.
  operator:  Operator;
  compareType: "value" | "indicator";
  value?:    number;
  compare_to?: Indicator;
  compare_period?: number;
}

interface Strategy {
  id: number;
  name: string;
  status: "active" | "paused";
  rules_json: any;
  created_at: string;
}

const SYMBOLS  = ["NIFTY", "RELIANCE", "GOLD", "BONDS"];
const DICT_INDICATORS = ["MACD", "BB"];
const MACD_FIELDS = ["macd", "signal", "histogram"];
const BB_FIELDS   = ["upper", "middle", "lower"];

const needsPeriod = (ind: Indicator) => !["PRICE"].includes(ind);

// ─────────────────────────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#0d0d18",
  border: "1px solid #1e1e2e",
  borderRadius: "16px",
  padding: "24px",
};

const inputStyle: React.CSSProperties = {
  background: "#111",
  border: "1px solid #2a2a3e",
  borderRadius: "8px",
  color: "#e0e0e0",
  padding: "8px 12px",
  fontSize: "13px",
  width: "100%",
  boxSizing: "border-box",
};

const selectStyle: React.CSSProperties = { ...inputStyle };

const btnPrimary: React.CSSProperties = {
  padding: "10px 22px",
  background: "linear-gradient(135deg, #00e5ff, #0077ff)",
  border: "none",
  borderRadius: "8px",
  color: "#0a0a0f",
  fontWeight: 700,
  fontSize: "13px",
  cursor: "pointer",
};

const btnGhost: React.CSSProperties = {
  padding: "8px 16px",
  background: "transparent",
  border: "1px solid #2a2a3e",
  borderRadius: "8px",
  color: "#aaa",
  fontWeight: 600,
  fontSize: "12px",
  cursor: "pointer",
};

// ─────────────────────────────────────────────────────────────────────────────
export default function StrategyBuilder({ token }: StrategyBuilderProps) {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading,    setLoading   ] = useState(false);
  const [error,      setError     ] = useState("");
  const [success,    setSuccess   ] = useState("");

  // Form state
  const [name,       setName      ] = useState("");
  const [symbol,     setSymbol    ] = useState("NIFTY");
  const [action,     setAction    ] = useState<Action>("BUY");
  const [qtyPct,     setQtyPct    ] = useState(50);
  const [orderMode,  setOrderMode ] = useState<OrderMode>("MARKET");
  const [rules,      setRules     ] = useState<ConditionRule[]>([{
    indicator: "RSI", period: 14, operator: "<", compareType: "value", value: 30,
  }]);

  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchStrategies = async () => {
    const res = await fetch(`${API_BASE}/strategies`, { headers });
    if (res.ok) setStrategies(await res.json());
  };

  useEffect(() => { fetchStrategies(); }, []);

  const addRule = () =>
    setRules(r => [...r, { indicator: "SMA", period: 20, operator: ">", compareType: "value", value: 0 }]);

  const removeRule = (i: number) => setRules(r => r.filter((_, idx) => idx !== i));

  const updateRule = (i: number, patch: Partial<ConditionRule>) =>
    setRules(r => r.map((rule, idx) => idx === i ? { ...rule, ...patch } : rule));

  const buildDSL = () => {
    const conditions = rules.map(r => {
      const cond: any = {
        indicator: r.indicator,
        operator:  r.operator,
      };
      if (r.indicator !== "PRICE" && r.period) cond.period = r.period;
      if (DICT_INDICATORS.includes(r.indicator) && r.field) cond.field = r.field;

      if (r.compareType === "value") {
        cond.value = r.value;
      } else {
        cond.compare_to = r.compare_to;
        if (r.compare_period) cond.compare_period = r.compare_period;
      }
      return cond;
    });

    return {
      symbol,
      action,
      quantity_pct: qtyPct,
      order_mode:   orderMode,
      condition:    conditions.length === 1 ? conditions[0] : { AND: conditions },
    };
  };

  const handleCreate = async () => {
    setError(""); setSuccess(""); setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/strategies`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name, rules_json: buildDSL() }),
      });
      const data = await res.json();
      if (res.ok) {
        setSuccess(`Strategy "${name}" created successfully!`);
        setName("");
        fetchStrategies();
      } else {
        setError(data.detail || "Failed to create strategy.");
      }
    } finally { setLoading(false); }
  };

  const toggleStatus = async (id: number, current: string) => {
    const next = current === "active" ? "paused" : "active";
    await fetch(`${API_BASE}/strategies/${id}/status`, {
      method: "PATCH", headers, body: JSON.stringify({ status: next }),
    });
    fetchStrategies();
  };

  const deleteStrategy = async (id: number) => {
    if (!confirm("Delete this strategy? This cannot be undone.")) return;
    await fetch(`${API_BASE}/strategies/${id}`, { method: "DELETE", headers });
    fetchStrategies();
  };

  return (
    <div style={{ padding: "40px 60px", color: "#e0e0e0", minHeight: "calc(100vh - 70px)" }}>

      <div style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "32px", color: "#00e5ff", margin: "0 0 8px 0" }}>Strategy Builder</h1>
        <p style={{ color: "#666", margin: 0, fontSize: "14px" }}>
          Define automated trading rules using technical indicators. Each active strategy evaluates at every 1-minute candle close.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 420px", gap: "28px" }}>

        {/* ── LEFT: Builder Form ───────────────────────────────── */}
        <div style={card}>
          <h2 style={{ margin: "0 0 24px", fontSize: "16px", color: "#e0e0e0", fontWeight: 600 }}>
            New Strategy
          </h2>

          {/* Name */}
          <div style={{ marginBottom: "18px" }}>
            <label style={{ display: "block", color: "#888", fontSize: "12px", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>
              Strategy Name
            </label>
            <input id="strat-name" style={inputStyle} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. RSI Oversold Reversal" />
          </div>

          {/* Symbol + Action + Mode row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", marginBottom: "18px" }}>
            <div>
              <label style={{ display: "block", color: "#888", fontSize: "12px", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>Symbol</label>
              <select id="strat-symbol" style={selectStyle} value={symbol} onChange={e => setSymbol(e.target.value)}>
                {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: "block", color: "#888", fontSize: "12px", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>Action</label>
              <select id="strat-action" style={selectStyle} value={action} onChange={e => setAction(e.target.value as Action)}>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label style={{ display: "block", color: "#888", fontSize: "12px", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>Order Mode</label>
              <select id="strat-mode" style={selectStyle} value={orderMode} onChange={e => setOrderMode(e.target.value as OrderMode)}>
                <option value="MARKET">Market</option>
                <option value="BRACKET">Bracket</option>
              </select>
            </div>
          </div>

          {/* Quantity */}
          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", color: "#888", fontSize: "12px", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "1px" }}>
              Quantity — {qtyPct}% of available capital
            </label>
            <input type="range" min={5} max={100} step={5} value={qtyPct} onChange={e => setQtyPct(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#00e5ff" }} />
          </div>

          {/* Condition Rules */}
          <div style={{ marginBottom: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <label style={{ color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>
                Conditions (ALL must be true)
              </label>
              <button id="add-rule-btn" style={btnGhost} onClick={addRule}>+ Add Rule</button>
            </div>

            {rules.map((rule, i) => (
              <div key={i} style={{ background: "#0a0a14", border: "1px solid #2a2a3e", borderRadius: "10px", padding: "14px", marginBottom: "10px" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 80px 1fr auto", gap: "8px", alignItems: "center" }}>

                  {/* LHS Indicator */}
                  <select style={selectStyle} value={rule.indicator} onChange={e => updateRule(i, { indicator: e.target.value as Indicator, field: undefined })}>
                    {["RSI","SMA","EMA","MACD","BB","PRICE"].map(ind => <option key={ind} value={ind}>{ind}</option>)}
                  </select>

                  {/* Period */}
                  {needsPeriod(rule.indicator) && (
                    <input type="number" style={inputStyle} placeholder="Period" value={rule.period ?? ""} onChange={e => updateRule(i, { period: Number(e.target.value) })} />
                  )}
                  {!needsPeriod(rule.indicator) && <div />}

                  {/* Operator */}
                  <select style={selectStyle} value={rule.operator} onChange={e => updateRule(i, { operator: e.target.value as Operator })}>
                    {["<", ">", "<=", ">=", "=="].map(op => <option key={op} value={op}>{op}</option>)}
                  </select>

                  {/* RHS */}
                  <div style={{ display: "flex", gap: "6px" }}>
                    <select style={{ ...selectStyle, width: "90px" }} value={rule.compareType} onChange={e => updateRule(i, { compareType: e.target.value as "value" | "indicator" })}>
                      <option value="value">Value</option>
                      <option value="indicator">Indicator</option>
                    </select>
                    {rule.compareType === "value" ? (
                      <input type="number" style={inputStyle} value={rule.value ?? ""} onChange={e => updateRule(i, { value: Number(e.target.value) })} placeholder="e.g. 30" />
                    ) : (
                      <div style={{ display: "flex", gap: "4px", flex: 1 }}>
                        <select style={selectStyle} value={rule.compare_to ?? "SMA"} onChange={e => updateRule(i, { compare_to: e.target.value as Indicator })}>
                          {["SMA","EMA","RSI","PRICE"].map(ind => <option key={ind} value={ind}>{ind}</option>)}
                        </select>
                        <input type="number" style={{ ...inputStyle, width: "70px" }} placeholder="Period" value={rule.compare_period ?? ""} onChange={e => updateRule(i, { compare_period: Number(e.target.value) })} />
                      </div>
                    )}
                  </div>

                  {/* Remove */}
                  {rules.length > 1 && (
                    <button onClick={() => removeRule(i)} style={{ background: "transparent", border: "none", color: "#ff5555", cursor: "pointer", fontSize: "16px", padding: "4px 8px" }}>✕</button>
                  )}
                </div>

                {/* Sub-field for MACD/BB */}
                {DICT_INDICATORS.includes(rule.indicator) && (
                  <div style={{ marginTop: "8px" }}>
                    <select style={{ ...selectStyle, width: "160px" }} value={rule.field ?? ""} onChange={e => updateRule(i, { field: e.target.value })}>
                      <option value="">Select field...</option>
                      {(rule.indicator === "MACD" ? MACD_FIELDS : BB_FIELDS).map(f => (
                        <option key={f} value={f}>{f}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Feedback */}
          {error   && <div style={{ padding: "10px", background: "#1a0a0a", border: "1px solid #ff5555", borderRadius: "8px", color: "#ff5555", fontSize: "13px", marginBottom: "12px" }}>{error}</div>}
          {success && <div style={{ padding: "10px", background: "#0a1a0a", border: "1px solid #00ff88", borderRadius: "8px", color: "#00ff88", fontSize: "13px", marginBottom: "12px" }}>{success}</div>}

          <button id="create-strategy-btn" style={{ ...btnPrimary, width: "100%", padding: "14px", fontSize: "14px", opacity: loading || !name ? 0.6 : 1 }}
            onClick={handleCreate} disabled={loading || !name}>
            {loading ? "Creating..." : "Create Strategy"}
          </button>
        </div>

        {/* ── RIGHT: Active Strategies ─────────────────────────── */}
        <div>
          <h2 style={{ margin: "0 0 16px", fontSize: "16px", color: "#e0e0e0", fontWeight: 600 }}>
            Your Strategies ({strategies.length})
          </h2>

          {strategies.length === 0 && (
            <div style={{ ...card, textAlign: "center", color: "#555", padding: "40px" }}>
              <div style={{ fontSize: "40px", marginBottom: "12px" }}>🤖</div>
              <p>No strategies yet. Create one on the left to get started.</p>
            </div>
          )}

          {strategies.map(s => {
            const rules_json = s.rules_json || {};
            return (
              <div key={s.id} style={{ ...card, marginBottom: "14px", borderColor: s.status === "active" ? "#00e5ff33" : "#1e1e2e" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "15px", marginBottom: "4px" }}>{s.name}</div>
                    <div style={{ fontSize: "12px", color: "#666" }}>
                      {rules_json.action} · {rules_json.symbol} · {rules_json.order_mode} · {rules_json.quantity_pct}% capital
                    </div>
                  </div>
                  <div style={{
                    padding: "4px 12px", borderRadius: "20px", fontSize: "11px", fontWeight: 700,
                    background: s.status === "active" ? "#00ff8822" : "#2a2a2a",
                    color: s.status === "active" ? "#00ff88" : "#666",
                  }}>
                    {s.status.toUpperCase()}
                  </div>
                </div>

                <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
                  <button
                    id={`toggle-strat-${s.id}`}
                    style={{ ...btnGhost, color: s.status === "active" ? "#ffa500" : "#00ff88", borderColor: s.status === "active" ? "#ffa50033" : "#00ff8833" }}
                    onClick={() => toggleStatus(s.id, s.status)}
                  >
                    {s.status === "active" ? "Pause" : "Activate"}
                  </button>
                  <button
                    id={`delete-strat-${s.id}`}
                    style={{ ...btnGhost, color: "#ff5555", borderColor: "#ff555533" }}
                    onClick={() => deleteStrategy(s.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
