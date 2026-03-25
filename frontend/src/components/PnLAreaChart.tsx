import React from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";

interface HistoryData {
  time: string;
  pnl: number;
  optimizedPnl?: number; // Optional second series
}

interface Props {
  data: HistoryData[];
  isProfitable: boolean;
  isComparing?: boolean;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ background: "#0d0d18", border: "1px solid #1e1e2e", padding: "10px", borderRadius: "8px", color: "#e0e0e0" }}>
        <p style={{ margin: 0, fontSize: "12px", color: "#888" }}>{label}</p>
        <div style={{ marginTop: "8px" }}>
          {payload.map((entry: any, index: number) => (
             <div key={index} style={{ fontSize: "14px", fontWeight: "bold", color: entry.color }}>
               {entry.name}: ₹{entry.value.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
             </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

const PnLAreaChart: React.FC<Props> = ({ data, isProfitable, isComparing }) => {
  const color = isProfitable ? "#00ff88" : "#ff5555";
  const optimizeColor = "#00e5ff"; // Bright cyan for optimization

  return (
    <div style={{ width: "100%", minHeight: "450px", marginTop: "24px" }}>
      <ResponsiveContainer width="100%" height={450}>
        <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorPnL" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.4} />
              <stop offset="95%" stopColor={color} stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="colorOpt" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={optimizeColor} stopOpacity={0.2} />
              <stop offset="95%" stopColor={optimizeColor} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" vertical={false} />
          
          <XAxis 
            dataKey="time" 
            stroke="#555" 
            tick={{ fill: "#888", fontSize: 12 }} 
            tickMargin={10}
            minTickGap={30}
          />
          
          <YAxis 
            stroke="#555" 
            tick={{ fill: "#888", fontSize: 12 }} 
            tickFormatter={(val) => `₹${(val / 1000).toFixed(1)}k`}
            tickMargin={10}
            axisLine={false}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#555", strokeWidth: 1, strokeDasharray: "3 3" }} />
          
          <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
          
          <Area 
            name="Actual PnL"
            type="monotone" 
            dataKey="pnl" 
            stroke={color} 
            strokeWidth={3}
            fillOpacity={1} 
            fill="url(#colorPnL)" 
            animationDuration={1500}
          />

          {isComparing && (
            <Area
              name="Optimized PnL"
              type="monotone"
              dataKey="optimizedPnl"
              stroke={optimizeColor}
              strokeWidth={2}
              strokeDasharray="5 5"
              fillOpacity={1}
              fill="url(#colorOpt)"
              animationDuration={1500}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PnLAreaChart;
