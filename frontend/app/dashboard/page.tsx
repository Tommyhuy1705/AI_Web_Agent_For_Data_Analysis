/**
 * Dashboard Page - Static Enterprise Dashboard
 * Showing grid các chart tổng quan revenue, product, customer.
 * Tự động load data mới nhất khi user truy cập.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
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
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  DollarSign,
  ShoppingCart,
  Users,
  Package,
  RefreshCw,
  LayoutDashboard,
  MessageSquare,
} from "lucide-react";
import Link from "next/link";
import { API_BASE } from "@/lib/utils";

// ============================================================
// Types
// ============================================================

interface DashboardData {
  revenue_summary: {
    total_orders: number;
    total_revenue: number;
    avg_order_value: number;
    total_customers: number;
    total_products: number;
  };
  monthly_revenue: ChartData;
  top_products: ChartData;
  customer_segments: ChartData;
  daily_revenue: ChartData;
  channel_distribution: ChartData;
}

interface ChartData {
  chart_type: string;
  title: string;
  config: Record<string, any>;
  data: Record<string, any>[];
  error?: string;
}

// ============================================================
// Constants
// ============================================================

const COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16",
];

// ============================================================
// Helper Functions
// ============================================================

const formatNumber = (value: number) => {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString("vi-VN");
};

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat("vi-VN", {
    style: "decimal",
    maximumFractionDigits: 0,
  }).format(value) + " VND";
};

// ============================================================
// Custom Tooltip
// ============================================================

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

// ============================================================
// KPI Card Component
// ============================================================

function KPICard({
  title,
  value,
  icon: Icon,
  color,
  format = "number",
}: {
  title: string;
  value: number;
  icon: any;
  color: string;
  format?: "number" | "currency";
}) {
  return (
    <div className={`bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-2xl p-5 flex items-center gap-5 shadow-sm hover:shadow-md transition-all duration-300 transform hover:-translate-y-0.5`}>
      <div className={`p-3.5 rounded-xl ${color} shadow-sm`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-1">{title}</p>
        <p className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300">
          {format === "currency" ? formatCurrency(value) : formatNumber(value)}
        </p>
      </div>
    </div>
  );
}

// ============================================================
// Chart Card Component
// ============================================================

function ChartCard({
  chartData,
  className = "",
}: {
  chartData: ChartData;
  className?: string;
}) {
  if (!chartData || chartData.error) {
    return (
      <div className={`bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 shadow-sm rounded-2xl p-6 transition-all hover:shadow-md ${className}`}>
        <h3 className="text-sm font-medium mb-2">{chartData?.title || "Error"}</h3>
        <div className="flex items-center justify-center h-48 text-muted-foreground text-xs">
          Failed to load data
        </div>
      </div>
    );
  }

  const { chart_type, title, config, data } = chartData;
  const series = config?.series || [];
  const xAxisKey = config?.xAxis?.dataKey || (data[0] ? Object.keys(data[0])[0] : "");

  const revenueSeriesKey = series?.[0]?.dataKey;
  const revenueValues = revenueSeriesKey
    ? data
        .map((d: any) => Number(d?.[revenueSeriesKey] ?? 0))
        .filter((v: number) => Number.isFinite(v) && v >= 0)
    : [];
  const maxRevenue = revenueValues.length ? Math.max(...revenueValues) : 0;
  const minPositiveRevenue = revenueValues.length
    ? Math.min(...revenueValues.filter((v: number) => v > 0))
    : 0;
  const isRevenueTrendChart =
    title.toLowerCase().includes("doanh thu") &&
    (chart_type === "line" || chart_type === "area");
  // If one point is much larger than the rest, use sqrt scale so changes remain visible.
  const useAdaptiveSqrtScale =
    isRevenueTrendChart &&
    maxRevenue > 0 &&
    minPositiveRevenue > 0 &&
    maxRevenue / minPositiveRevenue >= 100;

  const renderChart = () => {
    switch (chart_type) {
      case "line":
        return (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 10 }} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={formatNumber}
                scale={useAdaptiveSqrtScale ? "sqrt" : "auto"}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {series.map((s: any, i: number) => (
                <Line
                  key={i}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name}
                  stroke={s.color || COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case "bar":
        return (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 10 }} />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={formatNumber}
                scale={useAdaptiveSqrtScale ? "sqrt" : "auto"}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
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

      case "pie":
        const pieDataKey = config?.dataKey || "total_revenue";
        const pieNameKey = config?.nameKey || xAxisKey;
        return (
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data}
                dataKey={pieDataKey}
                nameKey={pieNameKey}
                cx="50%"
                cy="50%"
                outerRadius="70%"
                label={({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }) => {
                  const RADIAN = Math.PI / 180;
                  const radius = outerRadius * 1.15;
                  const x = cx + radius * Math.cos(-midAngle * RADIAN);
                  const y = cy + radius * Math.sin(-midAngle * RADIAN);
                  return (
                    <text x={x} y={y} fill={COLORS[index % COLORS.length]} textAnchor={x > cx ? "start" : "end"} dominantBaseline="central">
                      {(percent * 100).toFixed(1)}%
                    </text>
                  );
                }}
                labelLine={{ strokeWidth: 1, stroke: "#64748b" }}
              >
                {data.map((_: any, i: number) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        );

      case "area":
        return (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
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

      default:
        return (
          <div className="flex items-center justify-center h-48 text-muted-foreground text-xs">
            Unsupported chart type
          </div>
        );
    }
  };

  return (
    <div className={`bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 shadow-sm rounded-2xl p-6 transition-all hover:shadow-md ${className}`}>
      <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-4">{title}</h3>
      {renderChart()}
    </div>
  );
}

// ============================================================
// Main Dashboard Page
// ============================================================

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/dashboard/data`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      if (result.success) {
        setData(result.data);
        setLastUpdated(new Date());
      } else {
        throw new Error("Failed to load dashboard data");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  return (
    <div className="flex flex-col h-full font-sans max-w-[1600px] mx-auto w-full">
      {/* Dashboard Top Actions */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">Enterprise Dashboard</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Revenue and analytics figures are updated automatically in real-time.
            {lastUpdated && ` Last updated: ${lastUpdated.toLocaleTimeString("vi-VN")}`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl disabled:opacity-50 transition-all shadow-md shadow-indigo-600/20 font-medium"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh Data
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0">
        {loading && !data ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-500 bg-white/50 dark:bg-[#111827]/50 rounded-3xl border border-slate-200/50 dark:border-slate-800/50 backdrop-blur-sm">
            <div className="p-4 bg-white dark:bg-slate-800 rounded-full shadow-lg shadow-indigo-500/10 mb-4 animate-bounce">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
            </div>
            <p className="font-medium text-slate-600 dark:text-slate-300">Syncing data...</p>
          </div>
        ) : error && !data ? (
          <div className="flex items-center justify-center h-64 bg-rose-50/50 dark:bg-rose-900/10 rounded-3xl border border-rose-100 dark:border-rose-900/20">
            <div className="text-center">
              <p className="text-sm font-semibold text-rose-600 dark:text-rose-400 mb-4">Error: {error}</p>
              <button
                onClick={fetchDashboardData}
                className="text-sm font-medium px-6 py-2.5 rounded-xl bg-rose-600 text-white hover:bg-rose-700 shadow-lg shadow-rose-600/20 transition-all"
              >
                Retry
              </button>
            </div>
          </div>
        ) : data ? (
          <div className="space-y-6 animate-fade-in pb-12">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5">
              <KPICard
                title="Total Revenue"
                value={data.revenue_summary.total_revenue}
                icon={DollarSign}
                color="bg-gradient-to-br from-indigo-500 to-indigo-600"
                format="currency"
              />
              <KPICard
                title="Total Orders"
                value={data.revenue_summary.total_orders}
                icon={ShoppingCart}
                color="bg-gradient-to-br from-blue-500 to-blue-600"
              />
              <KPICard
                title="Avg Order Value"
                value={data.revenue_summary.avg_order_value}
                icon={TrendingUp}
                color="bg-gradient-to-br from-emerald-500 to-emerald-600"
                format="currency"
              />
              <KPICard
                title="Total Customers"
                value={data.revenue_summary.total_customers}
                icon={Users}
                color="bg-gradient-to-br from-amber-500 to-amber-600"
              />
              <KPICard
                title="Total Products"
                value={data.revenue_summary.total_products}
                icon={Package}
                color="bg-gradient-to-br from-rose-500 to-rose-600"
              />
            </div>

            {/* Charts Grid - Row 1 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ChartCard chartData={data.monthly_revenue} />
              <ChartCard chartData={data.daily_revenue} />
            </div>

            {/* Charts Grid - Row 2 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ChartCard chartData={data.top_products} />
              <ChartCard chartData={data.customer_segments} />
            </div>

            {/* Charts Grid - Row 3 */}
            <div className="grid grid-cols-1 gap-6">
              <ChartCard chartData={data.channel_distribution} />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
