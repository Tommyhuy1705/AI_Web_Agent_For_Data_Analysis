"use client";

import { useEffect, useMemo } from "react";
import ChatInterface from "@/components/agent/ChatInterface";
import DynamicChart from "@/components/visualizations/DynamicChart";
import { useAgentStore, type ChartConfig } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import { LayoutDashboard, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Home() {
  const { alarms, unreadAlarmCount, messages, markAlarmRead, activeChart } = useAgentStore();
  const { subscribeAlarms, unsubscribeAlarms } = useAgentStream();

  useEffect(() => {
    subscribeAlarms();
    return () => unsubscribeAlarms();
  }, []);

  const dashboardCharts = useMemo(() => {
    const lastAssistant = [...messages].reverse().find(
      (m) => m.role === "assistant" && m.metadata?.isDashboard && m.metadata?.allCharts?.length
    );
    return lastAssistant?.metadata?.allCharts || null;
  }, [messages]);

  return (
    <div className="flex w-full h-[calc(100vh-7rem)] gap-6">
      {/* Left Column: Chat Interface */}
      <div className="w-[480px] min-w-[360px] bg-white dark:bg-[#111827]/80 backdrop-blur-xl rounded-2xl shadow-xl shadow-slate-200/20 dark:shadow-none border border-slate-200/60 dark:border-slate-800/80 flex flex-col h-full overflow-hidden transition-all duration-300 relative z-10">
        <ChatInterface />
      </div>

      {/* Right Column: Canvas / Dashboard Insight */}
      <div className="flex-1 bg-white dark:bg-[#111827]/80 backdrop-blur-xl rounded-2xl shadow-xl shadow-slate-200/20 dark:shadow-none border border-slate-200/60 dark:border-slate-800/80 flex flex-col min-w-0 h-full overflow-hidden transition-all duration-300 relative z-10">
        {/* Canvas Area */}
        <div className="flex-1 min-h-0 overflow-auto custom-scrollbar">
          {dashboardCharts && dashboardCharts.length >= 1 ? (
            <div className="p-8">
              <div className="flex items-center justify-between mb-8 pb-5 border-b border-slate-100 dark:border-slate-800/50">
                <div className="flex items-center gap-4">
                  <div className="bg-indigo-500/10 p-2.5 rounded-xl border border-indigo-500/20">
                    <LayoutDashboard className="w-6 h-6 text-indigo-500" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold tracking-tight text-slate-800 dark:text-slate-100 flex items-center gap-2">
                      SIA Analytics Dashboard <Sparkles className="w-4 h-4 text-amber-500" />
                    </h2>
                    <p className="text-sm font-medium text-slate-500 mt-1">AI Insights • Showing {dashboardCharts.length} metrics</p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {dashboardCharts.map((chart: ChartConfig, idx: number) => (
                  <div
                    key={idx}
                    className="border border-slate-200/50 dark:border-slate-700/50 rounded-2xl bg-white dark:bg-slate-900 shadow-sm overflow-hidden hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300"
                  >
                    <div className="h-[380px] p-2">
                      <DynamicChart config={chart} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : activeChart ? (
            <div className="h-full w-full flex items-center justify-center p-8 bg-slate-50/20 dark:bg-transparent">
              <div className="w-full h-full bg-white dark:bg-slate-900 border border-slate-200/50 dark:border-slate-700/50 rounded-2xl shadow-sm overflow-hidden flex flex-col">
                <DynamicChart />
              </div>
            </div>
          ) : (
            <div className="h-full w-full flex flex-col items-center justify-center p-8 bg-slate-50/20 dark:bg-transparent text-center">
              <div className="w-24 h-24 mb-6 rounded-3xl bg-indigo-500/5 flex items-center justify-center border border-indigo-500/10">
                <Sparkles className="w-10 h-10 text-indigo-400 opacity-60" />
              </div>
              <h3 className="text-xl font-semibold text-slate-700 dark:text-slate-200 mb-2">Ready for data analysis</h3>
              <p className="text-slate-500 dark:text-slate-400 max-w-md">
                Select the assistant or type a question to start. SIA will automatically analyze and generate charts, alerts.
              </p>
            </div>
          )}
        </div>

        {/* Embedded Alarms / Alerts Stream */}
        {alarms.length > 0 && (
          <div className="border-t border-slate-200/60 dark:border-slate-800/80 max-h-48 overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50 custom-scrollbar shrink-0">
            {alarms.slice(0, 3).map((alarm) => (
              <div
                key={alarm.id}
                className={cn(
                  "flex items-start gap-4 px-6 py-4 text-sm border-b border-slate-200/40 dark:border-slate-800/40 last:border-0 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors",
                  !alarm.read && "bg-amber-50/30 dark:bg-amber-900/10"
                )}
                onClick={() => markAlarmRead(alarm.id)}
              >
                <div className="pt-1">
                  <span
                    className={cn(
                      "flex h-3 w-3 rounded-full flex-shrink-0 shadow-sm ring-4 ring-white dark:ring-[#111827]",
                      alarm.severity === "critical"
                        ? "bg-rose-500 shadow-rose-500/40"
                        : "bg-amber-500 shadow-amber-500/40"
                    )}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-800 dark:text-slate-200 mb-1 leading-snug">
                    {alarm.naturalMessage || alarm.message}
                  </p>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    SIA System Alert • {new Date(alarm.timestamp).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </p>
                </div>
                {!alarm.read && (
                    <div className="px-2 py-1 rounded-md bg-amber-100/50 dark:bg-amber-500/10 text-[10px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-widest">
                        New
                    </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
