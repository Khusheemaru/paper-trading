import { useEffect, useState } from "react";

interface Position {
  symbol: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
}

interface PositionsTableProps {
  token: string;
  refresh: number; // Trigger refresh when this changes
}

export default function PositionsTable({ token, refresh }: PositionsTableProps) {
  const [positions, setPositions] = useState<Position[]>([]);

  const fetchPositions = async () => {
    try {
      const response = await fetch("http://localhost:8000/positions", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setPositions(data);
      }
    } catch (err) {
      console.error("Failed to fetch positions:", err);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 2000); // Poll every 2s for PnL updates
    return () => clearInterval(interval);
  }, [token, refresh]);

  if (positions.length === 0) {
    return (
      <div
        style={{
          background: "#1e1e1e",
          padding: "20px",
          borderRadius: "8px",
          textAlign: "center",
          color: "#888",
        }}
      >
        No open positions
      </div>
    );
  }

  return (
    <div
      style={{
        background: "#1e1e1e",
        padding: "20px",
        borderRadius: "8px",
        marginBottom: "20px",
      }}
    >
      <h3 style={{ marginTop: 0 }}>Open Positions</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #444" }}>
            <th style={headerStyle}>Symbol</th>
            <th style={headerStyle}>Qty</th>
            <th style={headerStyle}>Avg Price</th>
            <th style={headerStyle}>Current</th>
            <th style={headerStyle}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos, idx) => (
            <tr key={idx} style={{ borderBottom: "1px solid #333" }}>
              <td style={cellStyle}>{pos.symbol}</td>
              <td style={cellStyle}>{pos.quantity}</td>
              <td style={cellStyle}>₹{pos.entry_price?.toFixed(2) || 0}</td>
              <td style={cellStyle}>₹{pos.current_price?.toFixed(2) || 0}</td>
              <td
                style={{
                  ...cellStyle,
                  color: (pos.unrealized_pnl || 0) >= 0 ? "#0f0" : "#f00",
                  fontWeight: "bold",
                }}
              >
                ₹{pos.unrealized_pnl?.toFixed(2) || 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const headerStyle: React.CSSProperties = {
  padding: "10px",
  textAlign: "left",
  color: "#aaa",
  fontSize: "14px",
};

const cellStyle: React.CSSProperties = {
  padding: "10px",
  color: "#fff",
};
