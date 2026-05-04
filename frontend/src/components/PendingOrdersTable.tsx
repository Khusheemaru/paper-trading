import { useEffect, useState } from "react";

interface Order {
  id: number;
  symbol: string;
  order_type: string;
  quantity: number;
  price: number;
  status: string;
}

interface PendingOrdersTableProps {
  token: string;
  refresh: number; // Trigger refresh when this changes
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function PendingOrdersTable({ token, refresh }: PendingOrdersTableProps) {
  const [orders, setOrders] = useState<Order[]>([]);

  const fetchOrders = async () => {
    try {
      const response = await fetch(`${API_BASE}/orders`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        // Filter only pending limit/stop orders
        const pending = data.filter((o: Order) => o.status === "pending");
        setOrders(pending);
      }
    } catch (err) {
      console.error("Failed to fetch orders:", err);
    }
  };

  const handleCancel = async (orderId: number) => {
    try {
      const res = await fetch(`${API_BASE}/orders/${orderId}/cancel`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchOrders();
      }
    } catch (err) {
      console.error("Cancel failed:", err);
    }
  };

  useEffect(() => {
    fetchOrders();
    const interval = setInterval(fetchOrders, 2000); // Poll every 2s
    return () => clearInterval(interval);
  }, [token, refresh]);

  if (orders.length === 0) {
    return (
      <div style={{ background: "#1e1e1e", padding: "20px", borderRadius: "8px", textAlign: "center", color: "#888", marginTop: "20px" }}>
        No pending orders
      </div>
    );
  }

  return (
    <div style={{ background: "#1e1e1e", padding: "20px", borderRadius: "8px", marginTop: "20px" }}>
      <h3 style={{ marginTop: 0 }}>Pending Limit Orders</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #444" }}>
            <th style={headerStyle}>Symbol</th>
            <th style={headerStyle}>Side</th>
            <th style={headerStyle}>Qty</th>
            <th style={headerStyle}>Limit Price</th>
            <th style={headerStyle}>Action</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} style={{ borderBottom: "1px solid #333" }}>
              <td style={cellStyle}>{o.symbol}</td>
              <td style={{ ...cellStyle, color: o.order_type === "buy" ? "#00ff88" : "#ff4d6d" }}>
                {o.order_type.toUpperCase()}
              </td>
              <td style={cellStyle}>{o.quantity}</td>
              <td style={cellStyle}>₹{Number(o.price).toFixed(2)}</td>
              <td style={cellStyle}>
                <button
                  onClick={() => handleCancel(o.id)}
                  style={{
                    background: "#333", color: "#fff", border: "none",
                    padding: "5px 10px", borderRadius: "4px", cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const headerStyle: React.CSSProperties = { padding: "10px", textAlign: "left", color: "#aaa", fontSize: "14px" };
const cellStyle: React.CSSProperties = { padding: "10px", color: "#fff" };
