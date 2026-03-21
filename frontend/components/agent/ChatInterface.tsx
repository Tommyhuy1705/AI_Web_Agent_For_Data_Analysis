/**
 * ChatInterface Component
 * Giao diện chat tương tác với AI Agent.
 * v2: Thêm New Chat button, Chat History sidebar, và session management.
 */
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAgentStore, ChatSession, ChatMessage as ChatMessageType } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import {
  Send,
  Square,
  Bot,
  User,
  Loader2,
  Database,
  BarChart3,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  PlusCircle,
  History,
  Trash2,
  X,
  MessageSquare,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ------------------------------------------------------------------ */
/*  Markdown renderer with code-block copy                            */
/* ------------------------------------------------------------------ */
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
        table({ children }) {
          return (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full text-xs border-collapse border border-gray-300">
                {children}
              </table>
            </div>
          );
        },
        th({ children }) {
          return (
            <th className="border border-gray-300 bg-gray-100 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          );
        },
        td({ children }) {
          return (
            <td className="border border-gray-300 px-2 py-1">{children}</td>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

/* ------------------------------------------------------------------ */
/*  Collapsible SQL Viewer                                            */
/* ------------------------------------------------------------------ */
function SQLViewer({ sql }: { sql: string }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors font-medium cursor-pointer"
      >
        <Database className="w-3 h-3" />
        SQL
        {expanded ? (
          <ChevronDown className="w-3 h-3" />
        ) : (
          <ChevronRight className="w-3 h-3" />
        )}
      </button>

      {expanded && (
        <div className="mt-1.5 relative rounded-md overflow-hidden border border-blue-200 bg-slate-900 text-green-300">
          <div className="flex items-center justify-between px-3 py-1 text-[10px] bg-slate-800 border-b border-slate-700">
            <span className="text-slate-400 uppercase tracking-wide">SQL Query</span>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 text-[10px] cursor-pointer"
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="p-3 overflow-x-auto text-[11px] leading-relaxed font-mono whitespace-pre-wrap">
            {sql}
          </pre>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chat History Sidebar                                              */
/* ------------------------------------------------------------------ */
function ChatHistorySidebar({
  isOpen,
  onClose,
  userId,
}: {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
}) {
  const {
    chatSessions,
    setChatSessions,
    loadSession,
    removeChatSession,
    isLoadingSessions,
    setLoadingSessions,
    sessionId: currentSessionId,
  } = useAgentStore();

  // Load sessions on open
  useEffect(() => {
    if (!isOpen) return;
    const fetchSessions = async () => {
      setLoadingSessions(true);
      try {
        const res = await fetch(`${API_BASE}/api/chat/sessions?user_id=${userId}&limit=30`);
        if (res.ok) {
          const data = await res.json();
          setChatSessions(data.sessions || []);
        }
      } catch (e) {
        console.error("Failed to load sessions:", e);
      } finally {
        setLoadingSessions(false);
      }
    };
    fetchSessions();
  }, [isOpen, userId]);

  const handleSelectSession = async (session: ChatSession) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${session.session_id}/messages?limit=50`);
      if (res.ok) {
        const data = await res.json();
        const messages: ChatMessageType[] = (data.messages || []).map((m: any) => ({
          id: m.message_id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
          metadata: m.metadata ? JSON.parse(m.metadata) : undefined,
        }));
        loadSession(session, messages);
      }
    } catch (e) {
      console.error("Failed to load session messages:", e);
    }
    onClose();
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, { method: "DELETE" });
      removeChatSession(sessionId);
    } catch (e) {
      console.error("Failed to delete session:", e);
    }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    if (diffHours < 1) return "Vừa xong";
    if (diffHours < 24) return `${Math.floor(diffHours)} giờ trước`;
    if (diffHours < 48) return "Hôm qua";
    return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
  };

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-20 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />

      {/* Sidebar panel */}
      <div className="relative z-30 w-72 h-full bg-background border-r shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-primary" />
            <span className="font-semibold text-sm">Lịch sử hội thoại</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-muted text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto py-2">
          {isLoadingSessions ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : chatSessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center px-4">
              <MessageSquare className="w-8 h-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">Chưa có lịch sử hội thoại</p>
            </div>
          ) : (
            chatSessions.map((session) => (
              <div
                key={session.session_id}
                onClick={() => handleSelectSession(session)}
                className={cn(
                  "group flex items-start gap-2 px-3 py-2.5 mx-2 rounded-lg cursor-pointer transition-colors hover:bg-muted",
                  currentSessionId === session.session_id && "bg-primary/10 border border-primary/20"
                )}
              >
                <MessageSquare className="w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{session.title || "New Chat"}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Clock className="w-3 h-3 text-muted-foreground" />
                    <span className="text-[10px] text-muted-foreground">
                      {formatDate(session.updated_at)}
                    </span>
                    {session.message_count > 0 && (
                      <span className="text-[10px] text-muted-foreground">
                        · {session.message_count} tin nhắn
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(e, session.session_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 hover:text-destructive transition-all"
                  title="Xóa"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main ChatInterface                                                */
/* ------------------------------------------------------------------ */
export default function ChatInterface() {
  const [input, setInput] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    isLoading,
    isStreaming,
    statusMessage,
    connectionStatus,
    startNewChat,
    sessionId,
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

  // Handle New Chat
  const handleNewChat = useCallback(() => {
    startNewChat();
    setInput("");
    inputRef.current?.focus();
  }, [startNewChat]);

  // Suggested questions
  const suggestions = [
    "Tổng doanh thu tháng này là bao nhiêu?",
    "Top 5 sản phẩm bán chạy nhất?",
    "Phân tích doanh thu theo khu vực",
    "Tạo dashboard theo dõi đơn hàng và doanh thu",
  ];

  return (
    <div className="relative flex flex-col h-full bg-background overflow-hidden">
      {/* Chat History Sidebar */}
      <ChatHistorySidebar
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        userId="default_user"
      />

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          <h2 className="font-semibold text-sm">SIA</h2>
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
          {sessionId && (
            <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">
              Session active
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* History button */}
          <button
            onClick={() => setShowHistory(true)}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground"
            title="Lịch sử hội thoại"
          >
            <History className="w-4 h-4" />
          </button>

          {/* New Chat button */}
          <button
            onClick={handleNewChat}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-medium transition-colors"
            title="Cuộc hội thoại mới"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            New Chat
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">
              Xin chào! Tôi là SIA
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
                  "max-w-[85%] rounded-lg px-4 py-2.5 text-sm",
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

                {/* Metadata section: SQL viewer + badges */}
                {msg.metadata && msg.role === "assistant" && (
                  <div className="mt-2 space-y-1.5">
                    {/* Clickable SQL viewer */}
                    {msg.metadata.sql && (
                      <SQLViewer sql={msg.metadata.sql} />
                    )}

                    {/* Other badges */}
                    <div className="flex flex-wrap gap-1.5">
                      {msg.metadata.isDashboard && msg.metadata.panelCount ? (
                        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                          <BarChart3 className="w-3 h-3" />
                          Dashboard: {msg.metadata.panelCount} biểu đồ
                        </span>
                      ) : msg.metadata.chartConfig ? (
                        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                          <BarChart3 className="w-3 h-3" />
                          Biểu đồ
                        </span>
                      ) : null}
                      {msg.metadata.rowCount !== undefined && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                          {msg.metadata.rowCount} dòng
                        </span>
                      )}
                    </div>
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
            placeholder="Nhập câu hỏi về doanh thu tại đây..."
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
