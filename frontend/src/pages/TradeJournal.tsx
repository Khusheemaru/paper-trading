/**
 * TradeJournal.tsx — Interactive Trade Journal Page
 *
 * Displays all trade journal entries enriched with trade metadata.
 * Clicking any row opens a modal showing the chart snapshot and reason.
 * Data source: GET /journal
 */

import React, { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

interface JournalEntry {
  id: number;
  trade_id: number;
  symbol: string;
  side: string;
  quantity: number;
  execution_price: number;
  pnl: number | null;
  entry_reason: string | null;
  exit_reason: string | null;
  entry_snapshot_path: string | null;
  exit_snapshot_path: string | null;
  created_at: string;
}

interface TradeJournalProps {
  token: string;
}

// ── Styles ──────────────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#0d0d18",
  border: "1px solid #1e1e2e",
  borderRadius: "16px",
  padding: "24px",
};

const tableHeaderStyle: React.CSSProperties = {
  padding: "12px 16px",
  textAlign: "left",
  fontSize: "11px",
  color: "#666",
  textTransform: "uppercase",
  letterSpacing: "1px",
  fontWeight: 600,
  borderBottom: "1px solid #1e1e2e",
  whiteSpace: "nowrap",
};

const tableCellStyle: React.CSSProperties = {
  padding: "14px 16px",
  fontSize: "13px",
  color: "#ccc",
  borderBottom: "1px solid #111",
  verticalAlign: "middle",
};

// ── Component ────────────────────────────────────────────────────────────────
export default function TradeJournal({ token }: TradeJournalProps) {
  const [entries,  setEntries ] = useState<JournalEntry[]>([]);
  const [loading,  setLoading ] = useState(true);
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const [filter,   setFilter  ] = useState<"all" | "BUY" | "buy" | "SELL" | "sell">("all");

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    const fetchJournal = async () => {
      try {
        const res = await fetch(`${API_BASE}/journal`, { headers });
        if (res.ok) setEntries(await res.json());
      } finally {
        setLoading(false);
      }
    };
    fetchJournal();
  }, []);

  const filtered = filter === "all" ? entries : entries.filter(e => e.side?.toUpperCase() === filter.toUpperCase());

  const pnlColor = (pnl: number | null) => {
    if (pnl === null) return "#888";
    return pnl >= 0 ? "#00ff88" : "#ff5555";
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
      + " " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  };

  const totalRealised = entries.reduce((acc, e) => acc + (e.pnl ?? 0), 0);
  const winners       = entries.filter(e => (e.pnl ?? 0) > 0).length;
  const winRate       = entries.length > 0 ? ((winners / entries.length) * 100).toFixed(1) : "—";

  return (
    <div style={{ padding: "40px 60px", color: "#e0e0e0", minHeight: "calc(100vh - 70px)" }}>

      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "32px", color: "#00e5ff", margin: "0 0 8px 0" }}>Trade Journal</h1>
        <p style={{ color: "#666", margin: 0, fontSize: "14px" }}>
          Every trade recorded — with entry reason, chart snapshot, and realised PnL.
        </p>
      </div>

      {/* ── Summary Strip ───────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "28px" }}>
        {[
          { label: "Total Trades",    value: entries.length.toString(),                      color: "#e0e0e0" },
          { label: "Win Rate",        value: winRate === "—" ? "—" : `${winRate}%`,          color: "#00e5ff" },
          { label: "Realised PnL",    value: `₹${totalRealised.toFixed(2)}`,                color: pnlColor(totalRealised) },
          { label: "With Snapshots",  value: entries.filter(e => e.entry_snapshot_path).length.toString(), color: "#a78bfa" },
        ].map(m => (
          <div key={m.label} style={{ ...card, textAlign: "center" }}>
            <div style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "6px" }}>{m.label}</div>
            <div style={{ fontSize: "24px", fontWeight: 700, color: m.color }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* ── Table ───────────────────────────────────────────────────── */}
      <div style={card}>
        {/* Filter Tabs */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          {["all", "BUY", "SELL"].map(f => (
            <button
              key={f}
              id={`journal-filter-${f}`}
              onClick={() => setFilter(f as any)}
              style={{
                padding: "7px 18px", borderRadius: "20px", cursor: "pointer", fontWeight: 600, fontSize: "12px",
                background: filter === f ? "#00e5ff22" : "transparent",
                color: filter === f ? "#00e5ff" : "#555",
                border: `1px solid ${filter === f ? "#00e5ff44" : "#2a2a3e"}`,
              }}
            >
              {f === "all" ? "All Trades" : f}
            </button>
          ))}
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: "40px", color: "#555" }}>Loading journal entries...</div>
        )}

        {!loading && filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px", color: "#333" }}>
            <div style={{ fontSize: "48px", marginBottom: "16px" }}>📓</div>
            <p>No journal entries yet. Trades executed via strategies or manually will appear here.</p>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Date", "Symbol", "Side", "Qty", "Price", "PnL", "Reason", "Snapshot"].map(h => (
                  <th key={h} style={tableHeaderStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(entry => (
                <tr
                  key={entry.id}
                  id={`journal-row-${entry.id}`}
                  onClick={() => setSelected(entry)}
                  style={{ cursor: "pointer", transition: "background 0.15s" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#111")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <td style={tableCellStyle}>{formatDate(entry.created_at)}</td>
                  <td style={{ ...tableCellStyle, fontWeight: 700, color: "#00e5ff" }}>{entry.symbol}</td>
                  <td style={{ ...tableCellStyle, color: entry.side?.toUpperCase() === "BUY" ? "#00ff88" : "#ff5555", fontWeight: 700 }}>
                    {entry.side?.toUpperCase()}
                  </td>
                  <td style={tableCellStyle}>{entry.quantity}</td>
                  <td style={tableCellStyle}>₹{Number(entry.execution_price).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                  <td style={{ ...tableCellStyle, color: pnlColor(entry.pnl), fontWeight: 600 }}>
                    {entry.pnl !== null ? `₹${Number(entry.pnl).toFixed(2)}` : "—"}
                  </td>
                  <td style={{ ...tableCellStyle, maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#888" }}>
                    {entry.entry_reason ?? "Manual trade"}
                  </td>
                  <td style={tableCellStyle}>
                    {entry.entry_snapshot_path ? (
                      <span style={{ padding: "3px 10px", background: "#a78bfa22", color: "#a78bfa", borderRadius: "12px", fontSize: "11px", fontWeight: 700 }}>
                        VIEW
                      </span>
                    ) : (
                      <span style={{ color: "#333", fontSize: "12px" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Detail Modal ─────────────────────────────────────────────── */}
      {selected && (
        <div
          id="journal-modal-overlay"
          onClick={() => setSelected(null)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: "#0d0d18", border: "1px solid #2a2a3e", borderRadius: "20px",
              padding: "32px", maxWidth: "760px", width: "90vw", maxHeight: "85vh", overflowY: "auto",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "20px", color: "#e0e0e0" }}>
                  <span style={{ color: selected.side?.toUpperCase() === "BUY" ? "#00ff88" : "#ff5555" }}>
                    {selected.side?.toUpperCase()}
                  </span>
                  {" "}{selected.symbol}
                </h2>
                <div style={{ color: "#555", fontSize: "13px", marginTop: "4px" }}>{formatDate(selected.created_at)}</div>
              </div>
              <button onClick={() => setSelected(null)} style={{ background: "transparent", border: "none", color: "#555", fontSize: "22px", cursor: "pointer" }}>✕</button>
            </div>

            {/* Stats row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "24px" }}>
              {[
                { label: "Qty",   value: selected.quantity.toString() },
                { label: "Price", value: `₹${Number(selected.execution_price).toLocaleString("en-IN", { minimumFractionDigits: 2 })}` },
                { label: "PnL",   value: selected.pnl !== null ? `₹${Number(selected.pnl).toFixed(2)}` : "Open", color: pnlColor(selected.pnl) },
              ].map(s => (
                <div key={s.label} style={{ background: "#111", border: "1px solid #1e1e2e", borderRadius: "10px", padding: "14px", textAlign: "center" }}>
                  <div style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "4px" }}>{s.label}</div>
                  <div style={{ fontSize: "18px", fontWeight: 700, color: s.color ?? "#e0e0e0" }}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Entry Reason */}
            {selected.entry_reason && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "8px" }}>Entry Reason</div>
                <div style={{ background: "#111", border: "1px solid #1e1e2e", borderRadius: "10px", padding: "14px", color: "#aaa", fontSize: "14px", lineHeight: 1.6 }}>
                  {selected.entry_reason}
                </div>
              </div>
            )}

            {/* Exit Reason */}
            {selected.exit_reason && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "8px" }}>Exit Reason</div>
                <div style={{ background: "#111", border: "1px solid #1e1e2e", borderRadius: "10px", padding: "14px", color: "#aaa", fontSize: "14px", lineHeight: 1.6 }}>
                  {selected.exit_reason}
                </div>
              </div>
            )}

            {/* Snapshot */}
            {selected.entry_snapshot_path && (
              <div>
                <div style={{ fontSize: "11px", color: "#555", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "8px" }}>Chart at Entry</div>
                <img
                  src={`${API_BASE}${selected.entry_snapshot_path}`}
                  alt="Chart snapshot at entry"
                  style={{ width: "100%", borderRadius: "12px", border: "1px solid #1e1e2e" }}
                />
              </div>
            )}

            {!selected.entry_snapshot_path && !selected.entry_reason && (
              <div style={{ textAlign: "center", color: "#333", padding: "24px" }}>
                No additional metadata for this trade.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
