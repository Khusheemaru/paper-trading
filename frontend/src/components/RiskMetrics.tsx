import React from "react";

interface MetricsType {
  total_value: number;
  total_pnl: number;
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown: number;
  volatility: number;
}

interface Props {
  metrics: MetricsType | null;
}

const RiskMetrics: React.FC<Props> = ({ metrics }) => {
  if (!metrics) {
    return <div style={{ color: "#888" }}>Loading risk profiles...</div>;
  }

  const isProfitable = metrics.total_pnl >= 0;
  const pnlColor = isProfitable ? "#00ff88" : "#ff5555";

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "16px", marginTop: "24px" }}>
      
      <div style={{ background: "#0d0d18", border: `1px solid ${pnlColor}44`, padding: "20px", borderRadius: "12px" }}>
        <h4 style={{ margin: 0, color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Total Portfolio Value</h4>
        <p style={{ margin: "8px 0 0", fontSize: "28px", fontWeight: "bold", color: "#e0e0e0" }}>
          ₹{metrics.total_value.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </p>
        <span style={{ fontSize: "14px", color: pnlColor, display: "block", marginTop: "4px" }}>
          {isProfitable ? "+" : ""}
          ₹{metrics.total_pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })} All Time
        </span>
      </div>

      <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "20px", borderRadius: "12px" }}>
        <h4 style={{ margin: 0, color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Sharpe Ratio</h4>
        <p style={{ margin: "8px 0 0", fontSize: "24px", fontWeight: "bold", color: metrics.sharpe_ratio > 1.5 ? "#00ff88" : "#ffa500" }}>
          {metrics.sharpe_ratio.toFixed(2)}
        </p>
        <span style={{ fontSize: "12px", color: "#555" }}>Risk-adjusted return</span>
      </div>

      <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "20px", borderRadius: "12px" }}>
        <h4 style={{ margin: 0, color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Win Rate</h4>
        <p style={{ margin: "8px 0 0", fontSize: "24px", fontWeight: "bold", color: metrics.win_rate > 50 ? "#00ff88" : "#ff5555" }}>
          {metrics.win_rate}%
        </p>
        <span style={{ fontSize: "12px", color: "#555" }}>% of profitable trades</span>
      </div>

      <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "20px", borderRadius: "12px" }}>
        <h4 style={{ margin: 0, color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Max Drawdown</h4>
        <p style={{ margin: "8px 0 0", fontSize: "24px", fontWeight: "bold", color: metrics.max_drawdown < 10 ? "#00ff88" : "#ff5555" }}>
          -{metrics.max_drawdown}%
        </p>
        <span style={{ fontSize: "12px", color: "#555" }}>Largest peak-to-trough drop</span>
      </div>

      <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "20px", borderRadius: "12px" }}>
        <h4 style={{ margin: 0, color: "#888", fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>Volatility</h4>
        <p style={{ margin: "8px 0 0", fontSize: "24px", fontWeight: "bold", color: "#00e5ff" }}>
          {metrics.volatility}%
        </p>
        <span style={{ fontSize: "12px", color: "#555" }}>Annualized std deviation</span>
      </div>

    </div>
  );
};

export default RiskMetrics;
