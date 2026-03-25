/**
 * TradingChart.tsx — Professional Candlestick Chart Component
 *
 * Features:
 * - Loads OHLCV historical candles from /market/history/{symbol} on mount
 * - Subscribes to live WebSocket ticks and merges them into the current candle
 * - Green/red candlesticks with dark background, matching the dashboard theme
 * - Automatically re-fetches and rebuilds when the active symbol changes
 */

import { useEffect, useRef, useCallback } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
} from "lightweight-charts";

const API_BASE = "http://localhost:8000";
const WS_BASE  = "ws://localhost:8000";

interface MarketTick {
  symbol: string;
  price: number;
  bid:   number;
  ask:   number;
  spread: number;
  timestamp: number;
}

interface TradingChartProps {
  symbol: string;
  onTickReceived?: (tick: MarketTick) => void; // pass live tick up to App
  onStatusChange?: (status: string) => void;
}

// Helper: round unix timestamp down to the nearest minute
const toMinuteTs = (ts: number): number => Math.floor(ts / 60) * 60;

export default function TradingChart({
  symbol,
  onTickReceived,
  onStatusChange,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);
  const seriesRef    = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const wsRef        = useRef<WebSocket | null>(null);
  const isMounted    = useRef(false);

  // Track the current open candle so we can merge ticks into it
  const currentCandle = useRef<CandlestickData<Time> | null>(null);
  const lastHistoryTsRef = useRef<number>(0);

  const notifyStatus = useCallback(
    (s: string) => onStatusChange?.(s),
    [onStatusChange]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    isMounted.current = true;

    // ── 1. Create Chart ─────────────────────────────────────────────
    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: 380,
      layout: {
        background: { type: ColorType.Solid, color: "#0d0d18" },
        textColor: "#555",
      },
      grid: {
        vertLines: { color: "#111827" },
        horzLines: { color: "#111827" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#1e1e2e" },
      timeScale: {
        borderColor: "#1e1e2e",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          "#00ff88",
      downColor:        "#ff4d6d",
      borderUpColor:    "#00ff88",
      borderDownColor:  "#ff4d6d",
      wickUpColor:      "#00ff88",
      wickDownColor:    "#ff4d6d",
    });

    chartRef.current  = chart;
    seriesRef.current = candleSeries;

    // ── 2. Resize handler ────────────────────────────────────────────
    const onResize = () => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);

    // ── 3. WebSocket: merge live ticks into the current candle ───────
    const connectWS = () => {
      if (!isMounted.current) return;
      if (wsRef.current) wsRef.current.close();

      const ws = new WebSocket(`${WS_BASE}/ws/market_data?symbol=${symbol}`);
      wsRef.current = ws;

      ws.onopen  = () => notifyStatus("Live");
      ws.onclose = () => { if (isMounted.current) notifyStatus("Reconnecting..."); };
      ws.onerror = () => notifyStatus("Error");

      ws.onmessage = (evt) => {
        const tick: MarketTick = JSON.parse(evt.data);
        onTickReceived?.(tick);

        if (!seriesRef.current) return;
        if (tick.timestamp <= lastHistoryTsRef.current) return;

        const minuteTs = toMinuteTs(tick.timestamp) as Time;

        if (
          currentCandle.current &&
          (currentCandle.current.time as number) === (minuteTs as number)
        ) {
          // Same minute → update the current candle
          const updated: CandlestickData<Time> = {
            ...currentCandle.current,
            high:  Math.max(currentCandle.current.high,  tick.price),
            low:   Math.min(currentCandle.current.low,   tick.price),
            close: tick.price,
          };
          currentCandle.current = updated;
          seriesRef.current.update(updated);
        } else {
          // New minute → open a fresh candle
          const newCandle: CandlestickData<Time> = {
            time:  minuteTs,
            open:  tick.price,
            high:  tick.price,
            low:   tick.price,
            close: tick.price,
          };
          currentCandle.current = newCandle;
          seriesRef.current.update(newCandle);
          lastHistoryTsRef.current = tick.timestamp;
        }
      };
    };

    // ── 4. Load historical candles FIRST, then open WS ──────────────
    notifyStatus("Loading...");
    fetch(`${API_BASE}/market/history/${symbol}?days=3`)
      .then((r) => r.json())
      .then((candles: CandlestickData<Time>[]) => {
        if (!isMounted.current || !seriesRef.current) return;

        let lastTs = 0;

        if (candles.length > 0) {
          // De-duplicate and sort by time
          const seen = new Set<number>();
          const clean = candles
            .filter((c) => {
              const t = c.time as number;
              if (seen.has(t)) return false;
              seen.add(t);
              return true;
            })
            .sort((a, b) => (a.time as number) - (b.time as number));

          seriesRef.current.setData(clean);
          currentCandle.current = clean[clean.length - 1];
          lastHistoryTsRef.current = currentCandle.current.time as number;
          chart.timeScale().fitContent();
        }

        connectWS();
      })
      .catch(() => {
        connectWS();
      });

    return () => {
      isMounted.current = false;
      chart.remove();
      window.removeEventListener("resize", onResize);
      if (wsRef.current) wsRef.current.close();
    };
  }, [symbol]); // Re-run entirely when symbol changes

  return (
    <div
      ref={containerRef}
      id={`chart-${symbol}`}
      style={{
        width: "100%",
        border: "1px solid #1e1e2e",
        borderRadius: "10px",
        overflow: "hidden",
        marginBottom: "20px",
      }}
    />
  );
}
