import { useEffect, useState } from "react";

interface AccountData {
  cash: number;
  invested: number;
  total_capital: number;
  current_pnl: number;
}

interface AccountSummaryProps {
  token: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function AccountSummary({ token }: AccountSummaryProps) {
  const [account, setAccount] = useState<AccountData | null>(null);

  const fetchAccount = async () => {
    try {
      const response = await fetch(`${API_BASE}/account`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setAccount(data);
      }
    } catch (err) {
      console.error("Failed to fetch account:", err);
    }
  };

  useEffect(() => {
    fetchAccount();
    const interval = setInterval(fetchAccount, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [token]);

  if (!account) return null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "12px",
        marginBottom: "20px",
        paddingTop: "16px",
      }}
    >
      <SummaryCard label="Total Capital"   value={`₹${account.total_capital.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} />
      <SummaryCard label="Cash Available" value={`₹${account.cash.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} />
      <SummaryCard label="Invested"        value={`₹${account.invested.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} />
      <SummaryCard
        label="Unrealized P&L"
        value={`${account.current_pnl >= 0 ? "+" : ""}₹${account.current_pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`}
        color={account.current_pnl >= 0 ? "#00ff88" : "#ff5555"}
      />
    </div>
  );
}

const SummaryCard = ({
  label,
  value,
  color = "#e0e0e0",
}: {
  label: string;
  value: string;
  color?: string;
}) => (
  <div
    style={{
      background: "#0d0d18",
      border: "1px solid #1e1e2e",
      padding: "14px 16px",
      borderRadius: "10px",
      textAlign: "center",
    }}
  >
    <div style={{ color: "#555", fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "6px" }}>
      {label}
    </div>
    <div style={{ fontSize: "20px", fontWeight: 700, color }}>{value}</div>
  </div>
);
