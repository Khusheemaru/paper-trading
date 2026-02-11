import { useState, useEffect, useRef } from "react";
import { createChart, ColorType, LineSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, LineData } from "lightweight-charts";

// --- CONFIG ---
const SOCKET_URL = "ws://localhost:8000/ws/market_data";
const HISTORY_URL = "http://localhost:8000/history";

// --- TYPE DEFINITIONS ---
interface MarketData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  spread: number;
  timestamp: number;
}

function App() {
  const [currentData, setCurrentData] = useState<MarketData>({
    symbol: "LOADING",
    price: 0,
    bid: 0,
    ask: 0,
    spread: 0,
    timestamp: 0,
  });

  const [connectionStatus, setConnectionStatus] = useState("Initializing...");

  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const isMountedRef = useRef(false);

  useEffect(() => {
    isMountedRef.current = true;

    if (!chartContainerRef.current) return;

    // 1. Initialize Chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { type: ColorType.Solid, color: "#111" },
        textColor: "#DDD",
      },
      grid: { vertLines: { color: "#333" }, horzLines: { color: "#333" } },
      timeScale: { timeVisible: true, secondsVisible: true },
    });

    const lineSeries = chart.addSeries(LineSeries, {
      color: "#2962FF",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;

    // 2. Define WebSocket Logic
    const connectWebSocket = (lastHistoryTime: number) => {
      if (!isMountedRef.current) return;

      console.log(">> Connecting to WebSocket...");
      const ws = new WebSocket(SOCKET_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnectionStatus("Open");
      ws.onclose = () => setConnectionStatus("Closed");
      ws.onerror = () => setConnectionStatus("Error");

      ws.onmessage = (event) => {
        const data: MarketData = JSON.parse(event.data);
        setCurrentData(data);

        // CRITICAL FIX: Ignore ticks older than or equal to last history point
        // This prevents the chart from "going back in time" and crashing
        if (data.timestamp <= lastHistoryTime) {
          return;
        }

        // Update Chart
        if (seriesRef.current) {
          seriesRef.current.update({
            time: data.timestamp as any,
            value: data.price,
          } as LineData);

          // Update tracker so we keep filtering properly
          lastHistoryTime = data.timestamp;
        }
      };
    };

    // 3. FETCH HISTORY FIRST -> THEN CONNECT WEBSOCKET
    setConnectionStatus("Fetching History...");
    fetch(HISTORY_URL)
      .then((res) => res.json())
      .then((historyData) => {
        if (!isMountedRef.current) return;

        let lastTime = 0;

        if (historyData.length > 0) {
          // Sort data: Oldest -> Newest
          const sortedData = historyData.sort(
            (a: any, b: any) => a.time - b.time,
          );

          // Remove potential duplicates in history itself
          const uniqueData = sortedData.filter(
            (item: any, index: number, self: any[]) =>
              index === 0 || item.time > self[index - 1].time,
          );

          lineSeries.setData(uniqueData);

          // Capture the very last timestamp
          lastTime = uniqueData[uniqueData.length - 1].time;
          console.log(
            `>> Loaded ${uniqueData.length} history points. Last time: ${lastTime}`,
          );
        }

        // ONLY CONNECT AFTER DATA IS SET
        connectWebSocket(lastTime);
      })
      .catch((err) => {
        console.error("History fetch failed", err);
        // If history fails, start fresh
        connectWebSocket(0);
      });

    // Resize Handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      isMountedRef.current = false;
      chart.remove();
      window.removeEventListener("resize", handleResize);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return (
    <div
      style={{
        backgroundColor: "#000",
        color: "#fff",
        minHeight: "100vh",
        padding: "20px",
        fontFamily: "sans-serif",
      }}
    >
      {/* HEADER */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <h2 style={{ margin: 0 }}>🇮🇳 HedgeBot Cockpit</h2>
        <div
          style={{
            fontSize: "12px",
            color: connectionStatus === "Open" ? "#0f0" : "#f00",
          }}
        >
          Status: {connectionStatus}
        </div>
      </div>

      {/* METRIC CARDS */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "15px",
          marginBottom: "20px",
        }}
      >
        <Card
          label="NIFTY 50"
          value={`₹${currentData.price.toFixed(2)}`}
          color="#fff"
        />
        <Card
          label="Best Bid"
          value={`₹${currentData.bid.toFixed(2)}`}
          color="#0f0"
        />
        <Card
          label="Best Ask"
          value={`₹${currentData.ask.toFixed(2)}`}
          color="#f00"
        />
        <Card
          label="Spread"
          value={`₹${currentData.spread.toFixed(2)}`}
          color={currentData.spread < 1.0 ? "#0f0" : "#ffa500"}
        />
      </div>

      {/* CHART CONTAINER */}
      <div
        ref={chartContainerRef}
        style={{
          border: "1px solid #333",
          borderRadius: "8px",
          overflow: "hidden",
        }}
      />
    </div>
  );
}

// Simple Sub-Component
interface CardProps {
  label: string;
  value: string;
  color: string;
}

const Card = ({ label, value, color }: CardProps) => (
  <div
    style={{
      background: "#1e1e1e",
      padding: "15px",
      borderRadius: "8px",
      textAlign: "center",
    }}
  >
    <div style={{ color: "#888", fontSize: "14px", marginBottom: "5px" }}>
      {label}
    </div>
    <div style={{ fontSize: "24px", fontWeight: "bold", color: color }}>
      {value}
    </div>
  </div>
);

export default App;
