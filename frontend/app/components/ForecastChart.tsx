"use client";

import type { ComponentType } from "react";
import {
  LineChart as RLineChart,
  Line,
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";

type Props = {
  forecast: number[];
  p90: number[];
  threshold: number;
  loading?: boolean;
};

// Recharts typing shim for TS false-positives
const XAxisC = XAxis as unknown as ComponentType<any>;
const YAxisC = YAxis as unknown as ComponentType<any>;
const ReferenceLineC = ReferenceLine as unknown as ComponentType<any>;

export default function ForecastChart({ forecast, p90, threshold, loading }: Props) {
  const data =
    forecast?.map((v, i) => ({
      t: `+${i + 1}m`,
      forecast: Math.round(v * 100) / 100,
      p90: Math.round((p90?.[i] ?? v) * 100) / 100,
    })) ?? [];

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RLineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxisC dataKey="t" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={{ stroke: "#475569" }} tickLine={{ stroke: "#475569" }} />
          <YAxisC allowDecimals tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={{ stroke: "#475569" }} tickLine={{ stroke: "#475569" }} />
          <Tooltip
            contentStyle={{
              background: "rgb(2 6 23)",        // slate-950
              border: "1px solid rgb(51 65 85)", // slate-700
              borderRadius: 12,
              color: "rgb(226 232 240)",         // slate-200
            }}
            labelStyle={{ color: "rgb(148 163 184)" }} // slate-400
            itemStyle={{ color: "rgb(226 232 240)" }}
          />
          <ReferenceLineC y={threshold} stroke="#f87171" strokeDasharray="4 4" />{/* rose-400 */}
          <Line type="monotone" dataKey="forecast" stroke="#60a5fa" dot={false} strokeWidth={2} /> {/* blue-400 */}
          <Line type="monotone" dataKey="p90" stroke="#c084fc" dot={false} strokeWidth={2} />     {/* violet-400 */}
        </RLineChart>
      </ResponsiveContainer>
      {loading && <div className="mt-2 text-center text-xs text-slate-400">Loading…</div>}
    </div>
  );
}
