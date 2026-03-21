"use client";
import { Bell, Search, Settings } from "lucide-react";
import { useAgentStore } from "@/store/useAgentStore";
import { cn } from "@/lib/utils";

export default function Header() {
  const { unreadAlarmCount } = useAgentStore();

  return (
    <header className="h-[64px] bg-white dark:bg-[#0A0D14]/80 backdrop-blur-xl border-b border-slate-200/50 dark:border-slate-800/60 flex items-center justify-between px-6 shrink-0 relative z-40">
      {/* Search Bar - Center left */}
      <div className="flex flex-1 items-center max-w-xl relative group">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
          <Search className="h-[18px] w-[18px] text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
        </div>
        <input 
          type="text" 
          placeholder="Ask SIA to analyze data, or search..." 
          className="w-full bg-slate-100/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800/80 rounded-full py-2.5 pl-11 pr-4 text-sm font-medium outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/50 transition-all text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 shadow-sm"
        />
        <div className="absolute inset-y-0 right-3 flex items-center">
            <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-medium text-slate-400 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                ⌘K
            </kbd>
        </div>
      </div>

      <div className="flex flex-1 justify-end items-center gap-4">
        {/* Connection Status Indicator */}
        <div className="hidden lg:flex items-center gap-2.5 bg-emerald-50 dark:bg-emerald-500/10 px-3.5 py-1.5 rounded-full border border-emerald-100 dark:border-emerald-500/20 shadow-sm">
          <div className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </div>
          <span className="text-[11px] font-bold tracking-wider text-emerald-600 dark:text-emerald-400">Connected</span>
        </div>
        
        <div className="w-[1px] h-6 bg-slate-200 dark:bg-slate-800 mx-2 hidden sm:block"></div>

        {/* Global Controls */}
        <div className="flex items-center gap-2">
            <button className="p-2.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors text-slate-500 dark:text-slate-400">
                <Settings className="w-5 h-5" />
            </button>
            <button className="relative p-2.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors text-slate-500 dark:text-slate-400">
                <Bell className="w-5 h-5" />
                {unreadAlarmCount > 0 && (
                    <span className="absolute top-1.5 right-1.5 flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500 border-2 border-white dark:border-[#0A0D14]"></span>
                    </span>
                )}
            </button>
        </div>
      </div>
    </header>
  );
}