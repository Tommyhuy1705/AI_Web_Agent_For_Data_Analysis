"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, LayoutDashboard, MessageSquare, Database, Users } from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { name: "Trợ lý SIA", href: "/", icon: MessageSquare },
    { name: "Tổng quan", href: "/dashboard", icon: LayoutDashboard },
    { name: "Nguồn dữ liệu", href: "#", icon: Database },
    { name: "Khách hàng", href: "#", icon: Users },
  ];

  return (
    <aside className="w-[80px] hover:w-[240px] transition-[width] duration-300 ease-[cubic-bezier(0.2,0,0,1)] bg-[#0A0D14] text-slate-300 flex flex-col h-full border-r border-slate-800/60 flex-shrink-0 group z-50 overflow-hidden relative shadow-[4px_0_24px_-12px_rgba(0,0,0,0.5)]">
      <div className="h-16 flex items-center px-4 border-b border-slate-800/60 shrink-0">
        <Activity className="w-8 h-8 text-indigo-500 fill-indigo-500/20 shrink-0 mx-2 transition-transform group-hover:scale-110 duration-500" />
        <span className="ml-3 font-bold text-lg text-white opacity-0 group-hover:opacity-100 transition-opacity duration-300 whitespace-nowrap bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
          SIA Platform
        </span>
      </div>
      
      <div className="flex-1 py-6 flex flex-col gap-2 px-3 overflow-y-auto custom-scrollbar">
        {links.map((link) => {
          const isActive = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.name}
              href={link.href}
              className={`flex items-center px-3 py-3 rounded-xl transition-all duration-200 mt-1 ${
                isActive 
                  ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_0_12px_0_rgba(99,102,241,0.1)]" 
                  : "hover:bg-slate-800/40 hover:text-white border border-transparent text-slate-400"
              }`}
              title={link.name}
            >
              <Icon className={`w-5 h-5 shrink-0 mx-1.5 transition-colors ${isActive ? "text-indigo-400 fill-indigo-400/10" : "group-hover/icon:text-white"}`} />
              <span className="ml-4 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap text-[15px] tracking-wide">
                {link.name}
              </span>
            </Link>
          );
        })}
      </div>

      <div className="p-4 border-t border-slate-800/60 mx-3 mb-4 rounded-2xl bg-slate-800/20 opacity-0 group-hover:opacity-100 transition-all duration-300 whitespace-nowrap overflow-hidden backdrop-blur-md border border-white/5 shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-white font-bold shrink-0 shadow-lg shadow-indigo-500/20 border border-white/20">
            A
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white tracking-wide">Quản trị viên</span>
            <span className="text-[11px] font-medium text-indigo-400 uppercase tracking-wider">Doanh nghiệp</span>
          </div>
        </div>
      </div>
    </aside>
  );
}