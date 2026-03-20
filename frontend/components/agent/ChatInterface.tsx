/**
 * ChatInterface Component
 * Giao diện chat tương tác với AI Agent.
 * Hiển thị messages, status, và input.
 */

"use client";

import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAgentStore } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import {
  Send,
  Square,
  Trash2,
  Bot,
  User,
  Loader2,
  Database,
  BarChart3,
  Copy,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

function MarkdownMessage({ content }: { content: string }) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ inline, className, children, ...props }: any) {
          const rawCode = String(children).replace(/\n$/, "");

          if (inline) {
            return (
              <code className="px-1 py-0.5 rounded bg-black/10 text-[12px]" {...props}>
                {children}
              </code>
            );
          }

          const language = (className || "").replace("language-", "") || "text";
          const isCopied = copiedCode === rawCode;

          return (
            <div className="relative my-2 rounded-md overflow-hidden border bg-black text-white">
              <div className="flex items-center justify-between px-3 py-1.5 text-[10px] uppercase tracking-wide bg-black/80 border-b border-white/10">
                <span>{language}</span>
                <button
                  type="button"
                  onClick={async () => {
                    await navigator.clipboard.writeText(rawCode);
                    setCopiedCode(rawCode);
                    setTimeout(() => setCopiedCode(null), 1200);
                  }}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/10 hover:bg-white/20"
                >
                  {isCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  {isCopied ? "Copied" : "Copy code"}
                </button>
              </div>
              <pre className="p-3 overflow-x-auto text-[12px] leading-relaxed">
                <code className={className} {...props}>
                  {rawCode}
                </code>
              </pre>
            </div>
          );
        },
        p({ children }) {
          return <p className="mb-2 last:mb-0">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 mb-2">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 mb-2">{children}</ol>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export default function ChatInterface() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    isLoading,
    isStreaming,
    statusMessage,
    connectionStatus,
    clearMessages,
  } = useAgentStore();

  const { sendMessage, cancelStream } = useAgentStream();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusMessage]);

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    await sendMessage(trimmed);
  };

  // Handle keyboard shortcut
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Suggested questions
  const suggestions = [
    "Tổng doanh thu tháng này là bao nhiêu?",
    "Top 5 sản phẩm bán chạy nhất?",
    "Phân tích doanh thu theo khu vực",
    "So sánh doanh thu online vs offline",
  ];

  return (
    <div className="flex flex-col h-full bg-background overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          <h2 className="font-semibold text-sm">Omni-Revenue Agent</h2>
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              connectionStatus === "connected"
                ? "bg-green-500"
                : connectionStatus === "connecting"
                ? "bg-yellow-500 animate-pulse"
                : "bg-gray-400"
            )}
          />
        </div>
        <button
          onClick={clearMessages}
          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground"
          title="Xóa cuộc trò chuyện"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">
              Xin chào! Tôi là Omni-Revenue Agent
            </h3>
            <p className="text-sm text-muted-foreground mb-6 max-w-md">
              Tôi có thể giúp bạn phân tích dữ liệu doanh thu, tạo biểu đồ, và
              đưa ra insight kinh doanh. Hãy đặt câu hỏi!
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setInput(q);
                    inputRef.current?.focus();
                  }}
                  className="text-left text-xs p-3 rounded-lg border hover:bg-muted transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex gap-3 animate-fade-in",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {msg.role !== "user" && (
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}

              <div
                className={cn(
                  "max-w-[80%] rounded-lg px-4 py-2.5 text-sm",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                )}
              >
                {/* Message content */}
                <div className="whitespace-pre-wrap">
                  {msg.content ? (
                    <MarkdownMessage content={msg.content} />
                  ) : isStreaming && msg.role === "assistant" ? (
                    <span className="flex items-center gap-1">
                      <span className="typing-dot w-1.5 h-1.5 bg-current rounded-full" />
                      <span className="typing-dot w-1.5 h-1.5 bg-current rounded-full" />
                      <span className="typing-dot w-1.5 h-1.5 bg-current rounded-full" />
                    </span>
                  ) : (
                    ""
                  )}
                </div>

                {/* Metadata badges */}
                {msg.metadata && msg.role === "assistant" && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {msg.metadata.sql && (
                      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                        <Database className="w-3 h-3" />
                        SQL
                      </span>
                    )}
                    {msg.metadata.chartConfig && (
                      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                        <BarChart3 className="w-3 h-3" />
                        Biểu đồ
                      </span>
                    )}
                    {msg.metadata.rowCount !== undefined && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                        {msg.metadata.rowCount} dòng
                      </span>
                    )}
                  </div>
                )}
              </div>

              {msg.role === "user" && (
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary flex items-center justify-center">
                  <User className="w-4 h-4 text-primary-foreground" />
                </div>
              )}
            </div>
          ))
        )}

        {/* Status message */}
        {statusMessage && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground animate-fade-in">
            <Loader2 className="w-3 h-3 animate-spin" />
            {statusMessage}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area - Always visible at bottom */}
      <div className="border-t px-4 py-4 flex-shrink-0 bg-background shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="💬 Nhập câu hỏi về doanh thu tại đây..."
            rows={2}
            className="flex-1 resize-none rounded-xl border-2 border-primary/20 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/40 bg-muted/30 min-h-[52px] max-h-[120px] placeholder:text-muted-foreground/60"
            disabled={isLoading}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="p-3 rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
              title="Dừng"
            >
              <Square className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="Gửi"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
