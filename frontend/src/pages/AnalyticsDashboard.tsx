import React, { useState, useEffect } from "react";
import RiskMetrics from "../components/RiskMetrics";
import PnLAreaChart from "../components/PnLAreaChart";

interface AnalyticsProps {
  token: string | null;
}

const AnalyticsDashboard: React.FC<AnalyticsProps> = ({ token }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  // Optimization State
  const [weights, setWeights] = useState({ NIFTY: 25, RELIANCE: 25, GOLD: 25, BONDS: 25 });
  const [optimizedHistory, setOptimizedHistory] = useState<any[]>([]);
  const [isOptimizing, setIsOptimizing] = useState(false);

  useEffect(() => {
    if (!token) return;
    
    const fetchAnalytics = async () => {
      try {
        const res = await fetch("http://localhost:8000/portfolio/analytics", {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const result = await res.json();
          setData(result);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    
    fetchAnalytics();
  }, [token]);

  const handleWeightChange = (symbol: string, val: number) => {
    setWeights(prev => ({ ...prev, [symbol]: val }));
  };

  const handleOptimize = async () => {
    if (!token) return;
    setIsOptimizing(true);
    try {
      const res = await fetch("http://localhost:8000/portfolio/optimize", {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ weights })
      });
      if (res.ok) {
        const result = await res.json();
        setOptimizedHistory(result);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsOptimizing(false);
    }
  };

  // Merge actual history with optimized history for the chart
  const mergedHistory = (data?.history || []).map((h: any, i: number) => ({
    ...h,
    optimizedPnl: optimizedHistory[i]?.pnl ?? null
  }));

  if (!token) {
    return <div style={{ padding: "40px", textAlign: "center", color: "#888" }}>Please Login First</div>;
  }

  if (loading) {
    return <div style={{ padding: "40px", textAlign: "center", color: "#888" }}>Loading analytical models...</div>;
  }

  const isProfitable = data?.metrics?.total_pnl >= 0;

  return (
    <div style={{ padding: "40px 60px", color: "#e0e0e0", minHeight: "calc(100vh - 70px)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "32px", color: "#00e5ff", margin: "0 0 8px 0" }}>Portfolio Analytics</h1>
          <p style={{ color: "#888", margin: 0 }}>
            Deep insights and algorithmic analysis of your multi-asset portfolio.
          </p>
        </div>
      </div>
      
      {/* ── OPTIMIZATION CONTROLS ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", marginBottom: "24px" }}>
        
        {/* LEFT: The Chart */}
        <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", borderRadius: "16px", padding: "20px", boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <h3 style={{ margin: "0", color: "#e0e0e0", fontSize: "16px" }}>Historical Performance vs Optimization</h3>
            <div style={{ display: "flex", gap: "16px", fontSize: "12px" }}>
              <span style={{ color: isProfitable ? "#00ff88" : "#ff5555" }}>● Actual PnL</span>
              {optimizedHistory.length > 0 && <span style={{ color: "#00e5ff" }}>-- Optimized Scenario</span>}
            </div>
          </div>
          <PnLAreaChart 
             data={mergedHistory} 
             isProfitable={isProfitable} 
             isComparing={optimizedHistory.length > 0} 
          />
        </div>

        {/* RIGHT: Slider Panel */}
        <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", borderRadius: "16px", padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <h3 style={{ margin: 0, fontSize: "16px", color: "#00e5ff" }}>Portfolio Optimization</h3>
          <p style={{ margin: 0, fontSize: "12px", color: "#666" }}>Adjust target weights to simulate an optimized allocation.</p>
          
          {(Object.keys(weights) as Array<keyof typeof weights>).map((sym) => (
            <div key={sym}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                <span style={{ fontSize: "13px", fontWeight: "600" }}>{sym}</span>
                <span style={{ fontSize: "13px", color: "#00ff88" }}>{weights[sym]}%</span>
              </div>
              <input 
                type="range" 
                min="0" max="100" 
                value={weights[sym]} 
                onChange={(e) => handleWeightChange(sym, parseInt(e.target.value))}
                style={{ width: "100%", accentColor: "#00e5ff", cursor: "pointer" }}
              />
            </div>
          ))}

          {/* Suggest Optimal Button */}
          <button
            onClick={() => {
              const optimal = { NIFTY: 40, RELIANCE: 30, BONDS: 20, GOLD: 10 };
              setWeights(optimal);
              // Auto-run simulation with optimal weights after state update
              setTimeout(() => {
                if (!token) return;
                setIsOptimizing(true);
                fetch("http://localhost:8000/portfolio/optimize", {
                  method: "POST",
                  headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
                  body: JSON.stringify({ weights: optimal })
                })
                  .then(r => r.json())
                  .then(result => setOptimizedHistory(result))
                  .catch(console.error)
                  .finally(() => setIsOptimizing(false));
              }, 0);
            }}
            style={{
              padding: "10px", borderRadius: "8px", border: "1px solid #00ff88",
              background: "transparent", color: "#00ff88", fontWeight: "600", cursor: "pointer",
              fontSize: "12px", transition: "all 0.2s"
            }}
          >
            💡 Suggest Optimal Allocation
          </button>

          <button 
            onClick={handleOptimize}
            disabled={isOptimizing}
            style={{ 
              padding: "12px", borderRadius: "8px", border: "none", 
              background: "#00e5ff", color: "#0a0a0f", fontWeight: "bold", cursor: "pointer",
              transition: "opacity 0.2s", opacity: isOptimizing ? 0.6 : 1
            }}
          >
            {isOptimizing ? "Simulating..." : "Optimize Portfolio"}
          </button>
        </div>
      </div>

      {/* Advanced Risk & Reward Metric Cards */}
      <RiskMetrics metrics={data?.metrics || null} />
      
    </div>
  );
};

export default AnalyticsDashboard;
