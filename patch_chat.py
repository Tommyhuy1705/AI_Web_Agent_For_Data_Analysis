import os

with open("frontend/components/agent/ChatInterface.tsx", "w") as f:
    f.write("""\"use client\";

import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Sparkles, Loader2, BarChart2, CheckCircle2, MessageSquareText, Search } from "lucide-react";
import { useAgentStore } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

// Format timestamps
const formatTime = (date?: Date) => {
  if (!date) return "";
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
};

export default function ChatInterface() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { messages, isTyping } = useAgentStore();
  const { sendMessage } = useAgentStream();

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isTyping) return;
    setInput("");
    await sendMessage(text);
  };

  const handleSuggestionClick = (text: string) => {
    setInput(text);
  };

  return (
    <div className="flex flex-col h-full bg-white/50 dark:bg-slate-900/30">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800/80 bg-white/80 dark:bg-[#111827]/80 backdrop-blur-md z-10 sticky top-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shadow-sm relative">
            <Bot className="w-5 h-5 text-indigo-500" />
            <span className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-500 border-2 border-white dark:border-[#111827] rounded-full"></span>
          </div>
          <div>
            <h2 className="text-[15px] font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 tracking-tight">
              SIA Assistant <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            </h2>
            <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Enterprise AI Analyst</p>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar scroll-smooth relative">
        {messages.length === 0 ? (
          <div className="flex flex-col h-full items-center justify-center text-center animate-fade-in px-6">
            <div className="w-20 h-20 mb-6 bg-gradient-to-br from-indigo-50 dark:from-indigo-900/20 to-purple-50 dark:to-purple-900/20 rounded-full flex items-center justify-center border border-indigo-100 dark:border-indigo-800/50 shadow-inner">
              <Bot className="w-10 h-10 text-indigo-500/80" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 dark:text-slate-100 mb-2">How can I help you today?</h3>
            <p className="text-slate-500 dark:text-slate-400 text-sm max-w-sm mb-8 leading-relaxed">
              I can analyze enterprise revenue data, look up customer metrics, retrieve product insights, or generate comprehensive analytical dashboards.
            </p>
            
            <div className="grid grid-cols-1 w-full max-w-md gap-3 text-left">
              <button 
                onClick={() => handleSuggestionClick("Phân tích doanh thu tháng này so với tháng trước")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-indigo-50/50 hover:border-indigo-200 dark:hover:bg-indigo-900/20 dark:hover:border-indigo-800 transition-all shadow-sm hover:shadow"
              >
                <BarChart2 className="w-5 h-5 text-indigo-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Analyze revenue performance this month vs last month</span>
              </button>
              <button 
                onClick={() => handleSuggestionClick("Top 5 sản phẩm bán chạy nhất là gì?")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-emerald-50/50 hover:border-emerald-200 dark:hover:bg-emerald-900/20 dark:hover:border-emerald-800 transition-all shadow-sm hover:shadow"
              >
                <Search className="w-5 h-5 text-emerald-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Find the top 5 highest selling products</span>
              </button>
              <button 
                onClick={() => handleSuggestionClick("Tạo dashboard tổng quan về tình hình kinh doanh")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-amber-50/50 hover:border-amber-200 dark:hover:bg-amber-900/20 dark:hover:border-amber-800 transition-all shadow-sm hover:shadow"
              >
                <Sparkles className="w-5 h-5 text-amber-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Generate a complete executive dashboard</span>
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div
              key={msg.id || index}
              className={cn(
                "flex gap-4 w-full animate-slide-up relative",
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              {/* Avatar */}
              <div
                className={cn(
                  "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-sm select-none border",
                  msg.role === "user"
                    ? "bg-gradient-to-tr from-indigo-500 to-purple-500 border-white/10 text-white"
                    : "bg-white dark:bg-[#111827] border-slate-200 dark:border-slate-700 text-indigo-500"
                )}
              >
                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Content */}
              <div 
                className={cn(
                  "max-w-[80%] flex flex-col group",
                  msg.role === "user" ? "items-end" : "items-start"
                )}
              >
                <div
                  className={cn(
                    "px-4 py-3 text-sm flex flex-col gap-1.5 shadow-sm",
                    msg.role === "user"
                      ? "bg-indigo-600 text-white rounded-2xl rounded-tr-sm"
                      : "bg-white dark:bg-[#1E293B] text-slate-800 dark:text-slate-200 rounded-2xl rounded-tl-sm border border-slate-100 dark:border-slate-800/80"
                  )}
                >
                  {/* Assistant System Actions Indicators */}
                  {msg.role === "assistant" && msg.metadata?.action_type && (
                    <div className="flex flex-col gap-1.5 mb-2 mt-1 w-full bg-slate-50/50 dark:bg-slate-900/50 p-2.5 rounded-xl border border-slate-100/50 dark:border-slate-700/30">
                      <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Checked {msg.metadata.action_type === 'sql' ? 'Database' : 'Knowledge Base'}
                      </div>
                      <div className="text-[11px] text-slate-500 bg-white/50 dark:bg-[#111827]/50 p-1.5 rounded-md font-mono truncate max-w-full">
                        {msg.metadata.action_input ? (typeof msg.metadata.action_input === 'string' ? msg.metadata.action_input : JSON.stringify(msg.metadata.action_input)) : "Executed..."}
                      </div>
                    </div>
                  )}

                  {/* Main Text Content */}
                  {msg.content && (
                    <div className={cn(
                      "prose max-w-none break-words leading-relaxed",
                      msg.role === "user" ? "prose-invert text-white marker:text-white" : "prose-slate dark:prose-invert",
                      "prose-p:m-0 prose-ul:m-0 prose-li:m-0 prose-code:px-1 prose-code:py-0.5 prose-code:rounded-md prose-code:bg-black/10 dark:prose-code:bg-white/10 prose-code:before:content-none prose-code:after:content-none"
                    )}>
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}

                  {/* Dashboard Notification Pill */}
                  {msg.metadata?.isDashboard && (
                    <div className="mt-3 flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-[13px] font-medium select-none shadow-sm pb-2 cursor-default">
                      <BarChart2 className="w-4 h-4" /> 
                      Generated {msg.metadata.allCharts?.length || 0} charts on canvas
                    </div>
                  )}
                </div>

                {/* Timestamp */}
                <div className="flex items-center gap-2 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity px-1">
                  <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500">
                    {formatTime(msg.timestamp || new Date())}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
        
        {isTyping && (
          <div className="flex gap-4 w-full animate-fade-in h-12">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-700 flex items-center justify-center text-indigo-500 shadow-sm">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-2xl rounded-tl-sm border border-slate-100 dark:border-slate-700/80 px-4 py-3 w-[68px] flex items-center justify-center shadow-sm">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-indigo-500/60 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1.5 h-1.5 bg-indigo-500/80 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce"></span>
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} className="h-2" />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 p-4 border-t border-slate-100 dark:border-slate-800/80 bg-white/80 dark:bg-[#111827]/80 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="flex items-center gap-2 relative max-w-2xl mx-auto w-full">
          <div className="relative flex-1 group">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <MessageSquareText className="h-4 w-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
            </div>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask SIA to analyze anything..."
              disabled={isTyping}
              className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-full py-3.5 pl-11 pr-16 text-sm outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/50 transition-all font-medium disabled:opacity-50 text-slate-700 dark:text-slate-200 placeholder:text-slate-400 shadow-inner"
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              className="absolute right-1.5 top-1.5 bottom-1.5 w-[36px] bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center transition-all disabled:opacity-40 disabled:hover:bg-indigo-600 shadow-md shadow-indigo-500/20"
            >
              {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 -ml-0.5" />}
            </button>
          </div>
        </form>
        <div className="text-center mt-3">
          <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">SIA Enterprise Analyst can make mistakes. Verify critical data.</span>
        </div>
      </div>
    </div>
  );
}
""")
