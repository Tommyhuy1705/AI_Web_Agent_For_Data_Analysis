/**
 * DynamicChart Component
 * Nhận JSON config, tự động render thành biểu đồ tương tác.
 * Hỗ trợ: bar, line, pie, area, scatter, composed, table.
 */

"use client";

import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAgentStore, type ChartConfig } from "@/store/useAgentStore";
import { BarChart3, Table, TrendingUp, X } from "lucide-react";
import { chartConfigSchema } from "@/lib/schemas";

// Default colors
const COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16",
];

interface DynamicChartProps {
  config?: ChartConfig | null;
}

export default function DynamicChart({ config: propConfig }: DynamicChartProps) {
  const { activeChart, chartHistory, setActiveChart } = useAgentStore();
  const rawConfig = propConfig || activeChart;
  const parsedConfig = rawConfig ? chartConfigSchema.safeParse(rawConfig) : null;
  const config = parsedConfig?.success ? (parsedConfig.data as ChartConfig) : null;

  // Format number for tooltips
  const formatNumber = (value: number) => {
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toLocaleString("vi-VN");
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-background border rounded-lg shadow-lg p-3 text-xs">
        <p className="font-medium mb-1">{label}</p>
        {payload.map((entry: any, i: number) => (
          <p key={i} style={{ color: entry.color }} className="flex justify-between gap-4">
            <span>{entry.name}:</span>
            <span className="font-medium">{formatNumber(entry.value)}</span>
          </p>
        ))}
      </div>
    );
  };

  // Render chart based on type
  const renderChart = useMemo(() => {
    if (rawConfig && !config) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <TrendingUp className="w-12 h-12 mb-3 animate-pulse" />
          <p className="text-sm">Dang xu ly bieu do...</p>
        </div>
      );
    }

    if (!config || !config.data?.length) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <BarChart3 className="w-12 h-12 mb-3" />
          <p className="text-sm">Chưa có biểu đồ nào</p>
          <p className="text-xs mt-1">Hãy đặt câu hỏi để tạo biểu đồ phân tích</p>
        </div>
      );
    }

    const { chart_type, data, config: chartCfg } = config;
    const series = chartCfg?.series || [];
    const xAxisKey = chartCfg?.xAxis?.dataKey || Object.keys(data[0])[0];

    switch (chart_type) {
      case "bar":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s: any, i: number) => (
                <Bar
                  key={i}
                  dataKey={s.dataKey}
                  name={s.name}
                  fill={s.color || COLORS[i % COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );

      case "line":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s: any, i: number) => (
                <Line
                  key={i}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name}
                  stroke={s.color || COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case "pie":
        const pieDataKey = chartCfg?.dataKey || series[0]?.dataKey || "value";
        const pieNameKey = chartCfg?.nameKey || xAxisKey;
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={pieDataKey}
                nameKey={pieNameKey}
                cx="50%"
                cy="50%"
                outerRadius="70%"
                label={({ name, percent }) =>
                  `${name}: ${(percent * 100).toFixed(1)}%`
                }
                labelLine={{ strokeWidth: 1 }}
              >
                {data.map((_: any, i: number) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        );

      case "area":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s: any, i: number) => (
                <Area
                  key={i}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name}
                  stroke={s.color || COLORS[i % COLORS.length]}
                  fill={s.color || COLORS[i % COLORS.length]}
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case "scatter":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Scatter
                data={data}
                fill={COLORS[0]}
                name={series[0]?.name || "Data"}
              />
            </ScatterChart>
          </ResponsiveContainer>
        );

      case "composed":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s: any, i: number) => {
                const chartType = s.type || (i === 0 ? "bar" : "line");
                if (chartType === "bar") {
                  return (
                    <Bar
                      key={i}
                      dataKey={s.dataKey}
                      name={s.name}
                      fill={s.color || COLORS[i % COLORS.length]}
                      radius={[4, 4, 0, 0]}
                    />
                  );
                }
                return (
                  <Line
                    key={i}
                    type="monotone"
                    dataKey={s.dataKey}
                    name={s.name}
                    stroke={s.color || COLORS[i % COLORS.length]}
                    strokeWidth={2}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        );

      case "table":
        const columns = chartCfg?.columns || Object.keys(data[0]);
        return (
          <div className="overflow-auto h-full">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-muted">
                  {columns.map((col: string) => (
                    <th key={col} className="px-3 py-2 text-left font-medium border-b">
                      {col.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 100).map((row: any, i: number) => (
                  <tr key={i} className="hover:bg-muted/50">
                    {columns.map((col: string) => (
                      <td key={col} className="px-3 py-1.5 border-b">
                        {typeof row[col] === "number"
                          ? formatNumber(row[col])
                          : String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      default:
        return (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p className="text-sm">Loại biểu đồ không được hỗ trợ: {chart_type}</p>
          </div>
        );
    }
  }, [config]);

  return (
    <div className="flex flex-col h-full">
      {/* Chart Header */}
      {config && config.data?.length > 0 && (
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <div>
            <h3 className="text-sm font-medium">{config.title}</h3>
            {config.description && (
              <p className="text-xs text-muted-foreground">{config.description}</p>
            )}
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
              {config.chart_type}
            </span>
            <button
              onClick={() => setActiveChart(null)}
              className="p-1 rounded hover:bg-muted"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* Chart Area */}
      <div className="flex-1 p-4 min-h-0">{renderChart}</div>

      {/* Chart History */}
      {chartHistory.length > 1 && (
        <div className="border-t px-4 py-2">
          <p className="text-[10px] text-muted-foreground mb-1">Lịch sử biểu đồ:</p>
          <div className="flex gap-1 overflow-x-auto">
            {chartHistory.slice(-5).map((chart, i) => (
              <button
                key={i}
                onClick={() => setActiveChart(chart)}
                className="text-[10px] px-2 py-1 rounded bg-muted hover:bg-muted/80 whitespace-nowrap"
              >
                {chart.title?.slice(0, 20) || `Chart ${i + 1}`}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
