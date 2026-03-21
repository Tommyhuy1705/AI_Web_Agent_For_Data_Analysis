/**
 * Global TypeScript interfaces and types for SIA Frontend.
 * Import from "@/types" throughout the application.
 */

// ── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  chartConfig?: ChartConfig;
  toolUsed?: string;
  data?: Record<string, unknown>[];
}

export interface ChatRequest {
  message: string;
  sessionId?: string;
}

// ── Charts ────────────────────────────────────────────────────────────────────

export type ChartType = "bar" | "line" | "pie" | "donut" | "area" | "composed" | "scatter";

export interface ChartConfig {
  type: ChartType;
  title: string;
  xKey?: string;
  yKey?: string | string[];
  data: Record<string, unknown>[];
  colors?: string[];
  unit?: string;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface KPISummary {
  total_revenue: number;
  total_orders: number;
  total_customers: number;
  avg_order_value: number;
}

export interface DashboardData {
  revenue_summary: KPISummary;
  monthly_revenue: MonthlyRevenue[];
  top_products: TopProduct[];
  customer_segments: CustomerSegment[];
  daily_revenue: DailyRevenue[];
  channel_distribution: ChannelData[];
}

export interface MonthlyRevenue {
  month: string;
  revenue: number;
  orders: number;
}

export interface TopProduct {
  product_name: string;
  revenue: number;
  quantity: number;
}

export interface CustomerSegment {
  segment: string;
  revenue: number;
  customer_count: number;
}

export interface DailyRevenue {
  date: string;
  revenue: number;
  orders: number;
}

export interface ChannelData {
  channel: string;
  revenue: number;
  orders: number;
}

// ── Market Intelligence ───────────────────────────────────────────────────────

export interface CompetitorPrice {
  id: number;
  source: string;
  product_name: string;
  price: number;
  original_price?: number;
  discount_pct?: number;
  rating?: number;
  sold_count?: number;
  seller_name?: string;
  keyword: string;
  crawled_at: string;
}

export interface MarketIntelStatus {
  tinyfish_configured: boolean;
  last_crawl?: string;
  total_products: number;
  scheduler_active: boolean;
}

// ── Alarm ─────────────────────────────────────────────────────────────────────

export interface AlarmEvent {
  metric_name: string;
  current_value: number;
  previous_value: number;
  change_pct: number;
  severity: "warning" | "critical";
  message: string;
  triggered_at: string;
}

// ── SSE Stream ────────────────────────────────────────────────────────────────

export type SSEEventType =
  | "start"
  | "status"
  | "sql_generated"
  | "data_ready"
  | "chart"
  | "insight"
  | "complete"
  | "done"
  | "error";

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  sql?: string;
  data?: Record<string, unknown>[];
  chart_config?: ChartConfig;
  insight?: string;
  error?: string;
}
