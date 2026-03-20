/**
 * Dashboard Page - Static Enterprise Dashboard
 * Hiển thị grid các biểu đồ tổng quan doanh thu, sản phẩm, khách hàng.
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
    <div className="bg-background border rounded-xl p-4 flex items-center gap-4 hover:shadow-md transition-shadow">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{title}</p>
        <p className="text-lg font-bold">
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
      <div className={`bg-background border rounded-xl p-4 ${className}`}>
        <h3 className="text-sm font-medium mb-2">{chartData?.title || "Error"}</h3>
        <div className="flex items-center justify-center h-48 text-muted-foreground text-xs">
          Không thể tải dữ liệu
        </div>
      </div>
    );
  }

  const { chart_type, title, config, data } = chartData;
  const series = config?.series || [];
  const xAxisKey = config?.xAxis?.dataKey || (data[0] ? Object.keys(data[0])[0] : "");

  const renderChart = () => {
    switch (chart_type) {
      case "line":
        return (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey={xAxisKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
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
              <YAxis tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
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
            Loại biểu đồ không được hỗ trợ
          </div>
        );
    }
  };

  return (
    <div className={`bg-background border rounded-xl p-4 ${className}`}>
      <h3 className="text-sm font-medium mb-3">{title}</h3>
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
    <div className="flex flex-col h-screen bg-muted/30">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-2 border-b bg-background/95 backdrop-blur">
        <div className="flex items-center gap-3">
          <LayoutDashboard className="w-5 h-5 text-primary" />
          <h1 className="text-base font-bold">Dashboard</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
            Enterprise Analytics
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-muted"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Chat Agent
          </Link>
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {lastUpdated && (
            <span className="text-[10px] text-muted-foreground">
              Cập nhật: {lastUpdated.toLocaleTimeString("vi-VN")}
            </span>
          )}
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6">
        {loading && !data ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Đang tải dữ liệu dashboard...</p>
            </div>
          </div>
        ) : error && !data ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-sm text-destructive mb-2">Lỗi: {error}</p>
              <button
                onClick={fetchDashboardData}
                className="text-xs px-4 py-2 rounded-lg bg-primary text-primary-foreground"
              >
                Thử lại
              </button>
            </div>
          </div>
        ) : data ? (
          <div className="max-w-7xl mx-auto space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <KPICard
                title="Tổng doanh thu"
                value={data.revenue_summary.total_revenue}
                icon={DollarSign}
                color="bg-blue-500"
                format="currency"
              />
              <KPICard
                title="Tổng đơn hàng"
                value={data.revenue_summary.total_orders}
                icon={ShoppingCart}
                color="bg-green-500"
              />
              <KPICard
                title="Giá trị TB/đơn"
                value={data.revenue_summary.avg_order_value}
                icon={TrendingUp}
                color="bg-purple-500"
                format="currency"
              />
              <KPICard
                title="Khách hàng"
                value={data.revenue_summary.total_customers}
                icon={Users}
                color="bg-orange-500"
              />
              <KPICard
                title="Sản phẩm"
                value={data.revenue_summary.total_products}
                icon={Package}
                color="bg-pink-500"
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
      </main>
    </div>
  );
}
