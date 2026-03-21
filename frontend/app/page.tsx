/**
 * Main Page - Omni-Revenue Agent
 * UI chia 2 cột: Chat (trái) & Canvas/Dashboard (phải)
 * Hỗ trợ hiển thị multi-chart grid khi user yêu cầu tạo dashboard.
 */

"use client";

import { useEffect, useMemo } from "react";
import ChatInterface from "@/components/agent/ChatInterface";
import DynamicChart from "@/components/visualizations/DynamicChart";
import { useAgentStore, type ChartConfig } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import { Bell, Activity, TrendingUp, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function Home() {
  const { alarms, unreadAlarmCount, activeChart, messages, markAlarmRead } =
    useAgentStore();
  const { subscribeAlarms, unsubscribeAlarms } = useAgentStream();

  // Subscribe to alarm stream on mount
  useEffect(() => {
    subscribeAlarms();
    return () => unsubscribeAlarms();
  }, []);

  // Check if the latest assistant message is a dashboard (multi-chart)
  const dashboardCharts = useMemo(() => {
    const lastAssistant = [...messages].reverse().find(
      (m) => m.role === "assistant" && m.metadata?.isDashboard && m.metadata?.allCharts?.length
    );
    return lastAssistant?.metadata?.allCharts || null;
  }, [messages]);

  return (
    <div className="flex flex-col h-full bg-background overflow-hidden">
      {/* Top Navigation Bar */}
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-2 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-primary" />
          <h1 className="text-base font-bold">Omni-Revenue Agent</h1>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
            Enterprise AI
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Alarm Bell */}
          <div className="relative">
            <button className="p-2 rounded-lg hover:bg-muted relative">
              <Bell className="w-4 h-4" />
              {unreadAlarmCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-destructive text-destructive-foreground text-[9px] flex items-center justify-center">
                  {unreadAlarmCount}
                </span>
              )}
            </button>
          </div>

          {/* Dashboard Link */}
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-muted"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Dashboard
          </Link>

          {/* Status indicator */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <TrendingUp className="w-3 h-3" />
            <span>v1.0.0</span>
          </div>
        </div>
      </header>

      {/* Main Content - 2 Column Layout */}
      <main className="flex-1 flex min-h-0 overflow-hidden">
        {/* Left Column: Chat Interface */}
        <div className="w-[420px] min-w-[360px] border-r flex flex-col h-full overflow-hidden">
          <ChatInterface />
        </div>

        {/* Right Column: Canvas / Dashboard */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Canvas Area */}
          <div className="flex-1 min-h-0 overflow-auto">
            {dashboardCharts && dashboardCharts.length >= 1 ? (
              /* Multi-chart Dashboard Grid */
              <div className="p-4">
                <div className="flex items-center gap-2 mb-4">
                  <LayoutDashboard className="w-4 h-4 text-primary" />
                  <h2 className="text-sm font-semibold">Dashboard tùy chỉnh</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                    {dashboardCharts.length} biểu đồ
                  </span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {dashboardCharts.map((chart: ChartConfig, idx: number) => (
                    <div
                      key={idx}
                      className="border rounded-lg bg-card shadow-sm overflow-hidden"
                    >
                      <div className="h-[320px]">
                        <DynamicChart config={chart} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Single Chart View */
              <DynamicChart />
            )}
          </div>

          {/* Alarm Bar (if any) */}
          {alarms.length > 0 && (
            <div className="border-t max-h-32 overflow-y-auto">
              {alarms.slice(0, 3).map((alarm) => (
                <div
                  key={alarm.id}
                  className={cn(
                    "flex items-center gap-3 px-4 py-2 text-xs border-b last:border-b-0 cursor-pointer hover:bg-muted/50",
                    !alarm.read && "bg-destructive/5"
                  )}
                  onClick={() => markAlarmRead(alarm.id)}
                >
                  <span
                    className={cn(
                      "w-2 h-2 rounded-full flex-shrink-0",
                      alarm.severity === "critical"
                        ? "bg-red-500"
                        : "bg-yellow-500"
                    )}
                  />
                  <span className="flex-1 truncate">
                    {alarm.naturalMessage || alarm.message}
                  </span>
                  <span className="text-muted-foreground flex-shrink-0">
                    {new Date(alarm.timestamp).toLocaleTimeString("vi-VN")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
