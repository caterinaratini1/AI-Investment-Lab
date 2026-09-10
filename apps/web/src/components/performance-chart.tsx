"use client";

import type { TooltipContentProps } from "recharts";
import {
  Area,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney } from "../lib/formatters";
import type { SeriesPoint } from "../lib/dashboard-types";

type PerformanceChartProps = {
  series: SeriesPoint[];
  currency: string;
  benchmarkLabel: string;
};

function ChartTooltip({
  active,
  payload,
  label,
}: TooltipContentProps) {
  if (!active || !payload.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.map((entry) => (
        <span key={String(entry.dataKey)} style={{ color: entry.color }}>
          {entry.name}: {formatMoney(Number(Array.isArray(entry.value) ? entry.value[0] : entry.value))}
        </span>
      ))}
    </div>
  );
}

export function PerformanceChart({
  series,
  currency,
  benchmarkLabel,
}: PerformanceChartProps) {
  if (!series.length) {
    return (
      <div className="chart-empty">
        <span aria-hidden="true">↗</span>
        <p>The comparison chart will appear after the first daily snapshot.</p>
      </div>
    );
  }

  const hasBenchmark = series.some((point) => point.benchmarkValue !== null);
  return (
    <>
      <div className="chart-frame" aria-label="Portfolio value comparison chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={series}
            margin={{ top: 16, right: 10, bottom: 0, left: 0 }}
            accessibilityLayer
          >
            <defs>
              <linearGradient id="portfolio-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#c7f36b" stopOpacity={0.16} />
                <stop offset="100%" stopColor="#c7f36b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="rgba(175,197,186,.12)" />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#81928a", fontSize: 11 }}
              minTickGap={28}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#81928a", fontSize: 11 }}
              tickFormatter={(value: number) =>
                new Intl.NumberFormat("en-IE", {
                  notation: "compact",
                  style: "currency",
                  currency,
                }).format(value)
              }
              width={64}
              domain={["dataMin - 100", "dataMax + 100"]}
            />
            <Tooltip content={ChartTooltip} cursor={{ stroke: "#52645c", strokeDasharray: 3 }} />
            <Area
              type="monotone"
              dataKey="portfolioValue"
              stroke="none"
              fill="url(#portfolio-fill)"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="portfolioValue"
              name="AI portfolio"
              stroke="#c7f36b"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 4, fill: "#c7f36b" }}
              isAnimationActive={false}
            />
            {hasBenchmark ? (
              <Line
                type="monotone"
                dataKey="benchmarkValue"
                name={benchmarkLabel}
                stroke="#7ccbd8"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ) : null}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <details className="data-table-disclosure">
        <summary>View chart data as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Valuation date</th>
                <th scope="col" className="numeric">AI portfolio</th>
                <th scope="col" className="numeric">{benchmarkLabel}</th>
              </tr>
            </thead>
            <tbody>
              {series.map((point) => (
                <tr key={point.date}>
                  <th scope="row">{point.date}</th>
                  <td className="numeric">{formatMoney(point.portfolioValue, currency)}</td>
                  <td className="numeric">{formatMoney(point.benchmarkValue, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
