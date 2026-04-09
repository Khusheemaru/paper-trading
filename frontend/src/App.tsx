import { useState, useEffect, useCallback, useRef } from "react";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import TradingChart from "./components/TradingChart";
import Login from "./components/Login";
import AccountSummary from "./components/AccountSummary";
import TradePanel from "./components/TradePanel";
import PositionsTable from "./components/PositionsTable";
import PendingOrdersTable from "./components/PendingOrdersTable";
import AnalyticsDashboard from "./pages/AnalyticsDashboard";
import StrategyBuilder from "./pages/StrategyBuilder";
import TradeJournal from "./pages/TradeJournal";

// ─── CONFIG ──────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

// All symbols supported by the backend (matches config.py ASSET_CONFIG keys)
const SYMBOLS = ["NIFTY", "RELIANCE", "GOLD", "BONDS"] as const;
type Symbol = typeof SYMBOLS[number];

const SYMBOL_META: Record<Symbol, { label: string; currency: string }> = {
  NIFTY:    { label: "NIFTY 50",    currency: "₹" },
  RELIANCE: { label: "Reliance",    currency: "₹" },
  GOLD:     { label: "Gold (MCX)",  currency: "₹" },
  BONDS:    { label: "Bonds (10Y)", currency: "₹" },
};

// ─── TYPES ────────────────────────────────────────────────────────────────────
interface MarketData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  spread: number;
  timestamp: number;
}

type AllPrices = Partial<Record<Symbol, { price: number | null; bid: number | null; ask: number | null; spread: number | null }>>;

// ─── APP ──────────────────────────────────────────────────────────────────────
function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // Auth
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [cashAvailable, setCashAvailable] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Chart screenshot ref (set by TradingChart)
  const chartScreenshotRef = useRef<(() => Promise<string | null>) | null>(null);

  // ── Asset selection ──────────────────────────────────────────────
  const [activeSymbol, setActiveSymbol] = useState<Symbol>("NIFTY");

  // Live tick data for the active symbol (lifted up from TradingChart)
  const [currentData, setCurrentData] = useState<MarketData>({
    symbol: "NIFTY",
    price: 0, bid: 0, ask: 0, spread: 0, timestamp: 0,
  });

  // Snapshot prices for all 4 assets (from REST polling)
  const [allPrices, setAllPrices] = useState<AllPrices>({});

  const [connectionStatus, setConnectionStatus] = useState("Initializing...");
  const [dataMode, setDataMode] = useState<"live" | "mock">("mock");
  const [modeDialogMsg, setModeDialogMsg] = useState<string | null>(null);

  const handleModeToggle = async () => {
    const targetMode = dataMode === "mock" ? "live" : "mock";
    try {
      const res = await fetch(`${API_BASE}/admin/mode`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ mode: targetMode })
      });
      if (res.ok) {
        setDataMode(targetMode);
      } else {
        const err = await res.json();
        setModeDialogMsg(err.detail || "Unable to switch mode.");
      }
    } catch {
      setModeDialogMsg("Could not reach server. Is the backend running?");
    }
  };

  const handleTickReceived = useCallback((tick: MarketData) => {
    setCurrentData(tick);
  }, []);

  const handleStatusChange = useCallback((status: string) => {
    setConnectionStatus(status);
  }, []);

  // ── Fetch account cash ───────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    const fetchAccount = async () => {
      try {
        const res = await fetch(`${API_BASE}/account`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setCashAvailable(data.cash);
        }
      } catch (err) { console.error("Account fetch failed:", err); }
    };
    fetchAccount();
    const interval = setInterval(fetchAccount, 5000);
    return () => clearInterval(interval);
  }, [token, refreshTrigger]);

  // ── Poll all asset prices every 2 s for the asset header bar ────
  useEffect(() => {
    if (!token) return;
    const fetchPrices = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/prices`);
        if (res.ok) setAllPrices(await res.json());
      } catch { /* silently ignore */ }
    };
    fetchPrices();
    const id = setInterval(fetchPrices, 2000);
    return () => clearInterval(id);
  }, [token]);


  const handleLoginSuccess = (accessToken: string, uid: number) => {
    setToken(accessToken);
    localStorage.setItem("token", accessToken);
    localStorage.setItem("userId", uid.toString());
  };

  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem("token");
    localStorage.removeItem("userId");
  };

  const handleTradeComplete = async () => {
    setRefreshTrigger((prev) => prev + 1);
    // Auto-capture chart snapshot when a trade is placed (fire-and-forget)
    if (chartScreenshotRef.current) {
      try {
        const dataUrl = await chartScreenshotRef.current();
        if (dataUrl && token) {
          // Convert dataURL to Blob and POST to /journal/snapshot/{trade_id}
          // trade_id is unknown at this point — snapshot tagged to latest trade
          const blob = await (await fetch(dataUrl)).blob();
          const form = new FormData();
          form.append("file", blob, "snapshot.png");
          // Fetch the latest trade id from orders endpoint
          const ordersRes = await fetch(`${API_BASE}/orders`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (ordersRes.ok) {
            const orders = await ordersRes.json();
            const latest = orders.find((o: any) => o.status === "executed");
            if (latest?.id) {
              await fetch(`${API_BASE}/journal/snapshot/${latest.id}`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
                body: form,
              });
            }
          }
        }
      } catch (e) { console.warn("Snapshot capture failed:", e); }
    }
  };

  // ── Guard: show login ────────────────────────────────────────────
  if (!token) return <Login onLoginSuccess={handleLoginSuccess} />;

  const meta = SYMBOL_META[activeSymbol];
  const cur  = meta.currency;

  return (
    <>
    <div style={{ backgroundColor: "#0a0a0f", color: "#e0e0e0", minHeight: "100vh", fontFamily: "'Segoe UI', sans-serif" }}>

      {/* ── HEADER ─────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "14px 24px", borderBottom: "1px solid #1e1e2e", backgroundColor: "#0d0d18" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontWeight: 700, fontSize: "18px", color: "#00e5ff" }}>HedgeBot</span>
          <span style={{ color: "#555", fontSize: "16px" }}>|</span>
          <div style={{ display: "flex", gap: "8px", marginLeft: "10px" }}>
            {[
              { path: "/",          label: "Terminal"  },
              { path: "/analytics", label: "Analytics" },
              { path: "/strategies",label: "Strategies"},
              { path: "/journal",   label: "Journal"   },
            ].map(({ path, label }) => (
              <button
                key={path}
                id={`nav-${label.toLowerCase()}`}
                onClick={() => navigate(path)}
                style={{
                  background: location.pathname === path ? "rgba(0,229,255,0.1)" : "transparent",
                  color: location.pathname === path ? "#00e5ff" : "#888",
                  border: "none", padding: "6px 12px", borderRadius: "6px",
                  cursor: "pointer", fontWeight: 600, fontSize: "14px",
                  transition: "all 0.2s",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Asset Selector */}
        <div style={{ display: "flex", gap: "8px" }}>
          {SYMBOLS.map((sym) => (
            <button
              key={sym}
              id={`asset-btn-${sym}`}
              onClick={() => setActiveSymbol(sym)}
              style={{
                padding: "6px 14px", borderRadius: "6px", border: "none", cursor: "pointer",
                fontSize: "13px", fontWeight: 600,
                background: activeSymbol === sym ? "#00e5ff" : "#1a1a2e",
                color: activeSymbol === sym ? "#0a0a0f" : "#888",
                transition: "all 0.2s",
                opacity: location.pathname === '/analytics' ? 0.3 : 1
              }}
              disabled={location.pathname === '/analytics'}
            >
              {SYMBOL_META[sym].label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          {/* Live / Mock toggle */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "11px", color: "#888" }}>MOCK</span>
            <div
              onClick={handleModeToggle}
              style={{
                width: "40px", height: "22px", borderRadius: "11px", cursor: "pointer", position: "relative",
                background: dataMode === "live" ? "#00ff88" : "#333",
                transition: "background 0.3s"
              }}
            >
              <div style={{
                position: "absolute", top: "3px",
                left: dataMode === "live" ? "21px" : "3px",
                width: "16px", height: "16px", borderRadius: "50%",
                background: "#fff", transition: "left 0.3s"
              }} />
            </div>
            <span style={{ fontSize: "11px", color: dataMode === "live" ? "#00ff88" : "#888" }}>LIVE</span>
          </div>

          <span style={{ fontSize: "12px", color: connectionStatus === "Live" ? "#00ff88" : "#ff5555" }}>
            ● {connectionStatus}
          </span>
          <button
            onClick={handleLogout}
            style={{ padding: "7px 16px", background: "transparent", border: "1px solid #ff5555",
                     borderRadius: "6px", color: "#ff5555", cursor: "pointer", fontSize: "13px" }}
          >
            Logout
          </button>
        </div>
      </div>

      <Routes>
        <Route path="/" element={
          <>
            {/* ── ALL-ASSETS PRICE BAR ────────────────────────────────── */}
            <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #1e1e2e", backgroundColor: "#0d0d18" }}>
              {SYMBOLS.map((sym) => {
                const p = allPrices[sym];
                return (
                  <div key={sym}
                    onClick={() => setActiveSymbol(sym)}
                    style={{ flex: 1, padding: "10px 20px", cursor: "pointer",
                             borderRight: "1px solid #1e1e2e",
                             borderBottom: activeSymbol === sym ? "2px solid #00e5ff" : "2px solid transparent",
                             transition: "border-color 0.2s" }}
                  >
                    <div style={{ fontSize: "11px", color: "#666", marginBottom: "2px" }}>{SYMBOL_META[sym].label}</div>
                    <div style={{ fontSize: "16px", fontWeight: 700, color: activeSymbol === sym ? "#00e5ff" : "#ccc" }}>
                      {p?.price != null ? `₹${p.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}` : "—"}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ── ACCOUNT SUMMARY ─────────────────────────────────────── */}
            <div style={{ padding: "0 24px" }}>
              <AccountSummary token={token} />
            </div>

                      {/* ── MAIN CONTENT (2-COL GRID) ───────────────────────────── */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: "20px", padding: "0 24px 24px" }}>

              {/* LEFT COLUMN: metric cards + chart + positions */}
              <div>
                {/* 4 Metric Cards for Active Asset */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "16px" }}>
                  <MetricCard label={`${meta.label} Price`} value={`${cur}${currentData.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} color="#e0e0e0" />
                  <MetricCard label="Best Bid"   value={`${cur}${currentData.bid.toFixed(2)}`}    color="#00ff88" />
                  <MetricCard label="Best Ask"   value={`${cur}${currentData.ask.toFixed(2)}`}    color="#ff5555" />
                  <MetricCard label="Spread"     value={`${cur}${currentData.spread.toFixed(2)}`} color={currentData.spread < 2.0 ? "#00ff88" : "#ffa500"} />
                </div>

                {/* Live Candlestick Chart */}
                <TradingChart
                  symbol={activeSymbol}
                  onTickReceived={handleTickReceived}
                  onStatusChange={handleStatusChange}
                  onScreenshotReady={(fn) => { chartScreenshotRef.current = fn; }}
                />

                {/* Positions & Pending Orders Table */}
                <PositionsTable token={token} refresh={refreshTrigger} />
                <PendingOrdersTable token={token} refresh={refreshTrigger} />
              </div>

              {/* RIGHT COLUMN: Trade Panel */}
              <div style={{ paddingTop: "0" }}>
                <TradePanel
                  token={token}
                  currentPrice={currentData.price}
                  cashAvailable={cashAvailable}
                  symbol={activeSymbol}
                  onTradeComplete={handleTradeComplete}
                />
              </div>
            </div>
          </>
        } />
        
        <Route path="/analytics"  element={<AnalyticsDashboard token={token} />} />
        <Route path="/strategies" element={<StrategyBuilder    token={token} />} />
        <Route path="/journal"    element={<TradeJournal       token={token} />} />
      </Routes>
    </div>

    {/* ── MARKET CLOSED DIALOG ─────────────────────────────────────── */}
    {modeDialogMsg && (
      <div style={{
        position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.7)", zIndex: 9999
      }}>
        <div style={{
          background: "#0d0d18", border: "1px solid #ff5555", borderRadius: "16px",
          padding: "32px 40px", maxWidth: "440px", textAlign: "center"
        }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>🔔</div>
          <h3 style={{ color: "#ff5555", margin: "0 0 12px" }}>Mode Switch Failed</h3>
          <p style={{ color: "#aaa", lineHeight: 1.6, margin: "0 0 24px" }}>{modeDialogMsg}</p>
          <button
            onClick={() => setModeDialogMsg(null)}
            style={{
              padding: "10px 28px", borderRadius: "8px", border: "none",
              background: "#00e5ff", color: "#0a0a0f", fontWeight: "bold", cursor: "pointer"
            }}
          >
            OK, Continue with Mock Data
          </button>
        </div>
      </div>
    )}
    </>
  );
}

// ─── METRIC CARD COMPONENT ───────────────────────────────────────────────────
interface MetricCardProps { label: string; value: string; color: string; }
const MetricCard = ({ label, value, color }: MetricCardProps) => (
  <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "14px 16px",
                borderRadius: "10px", textAlign: "center" }}>
    <div style={{ color: "#555", fontSize: "11px", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "6px" }}>
      {label}
    </div>
    <div style={{ fontSize: "20px", fontWeight: 700, color }}>{value}</div>
  </div>
);

export default App;
