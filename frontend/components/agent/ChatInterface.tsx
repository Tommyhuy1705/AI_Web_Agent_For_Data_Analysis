"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Sparkles, Loader2, BarChart2, CheckCircle2, MessageSquareText, Search, Database, ChevronDown, ChevronRight, Check, Copy, History, PlusCircle, Command, MessageSquare, Trash2, X, Clock, Mic } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";
import { useCallback } from "react";
import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Bot, User, Sparkles, Loader2, BarChart2, CheckCircle2,
  MessageSquareText, Search, Database, ChevronDown, ChevronRight,
  Check, Copy, History, PlusCircle, MessageSquare, Trash2, X, Clock,
  Mic, MicOff, Volume2, VolumeX,
} from "lucide-react";
import { useAgentStore, ChatSession, ChatMessage as ChatMessageType } from "@/store/useAgentStore";
import { useAgentStream } from "@/hooks/useAgentStream";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Format timestamps
const formatTime = (date?: Date) => {
  if (!date) return "";
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
};

// ------------------------------------------------------------------ //
//  SQL Viewer                                                         //
// ------------------------------------------------------------------ //
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
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
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

// ------------------------------------------------------------------ //
//  Audio Briefing Button                                              //
// ------------------------------------------------------------------ //
function AudioBriefingButton({ text }: { text: string }) {
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handlePlay = async () => {
    if (isPlaying) {
      // Stop playback
      audioRef.current?.pause();
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      setIsPlaying(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/audio/briefing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 2000) }), // Giới hạn 2000 ký tự
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        console.error("Audio briefing error:", err);
        alert(err.detail || "Không thể tạo audio. Vui lòng kiểm tra ELEVENLABS_API_KEY.");
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      // Dọn dẹp audio cũ
      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }

      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsPlaying(false);
      };

      await audio.play();
      setIsPlaying(true);
    } catch (e) {
      console.error("Audio briefing failed:", e);
    } finally {
      setIsLoading(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (audioRef.current?.src) {
        URL.revokeObjectURL(audioRef.current.src);
      }
    };
  }, []);

  return (
    <button
      type="button"
      onClick={handlePlay}
      disabled={isLoading}
      title={isPlaying ? "Dừng phát" : "Nghe Báo Cáo"}
      className={cn(
        "inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-md border transition-colors font-medium mt-2",
        isPlaying
          ? "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
          : "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100",
        isLoading && "opacity-60 cursor-wait"
      )}
    >
      {isLoading ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : isPlaying ? (
        <VolumeX className="w-3 h-3" />
      ) : (
        <Volume2 className="w-3 h-3" />
      )}
      {isLoading ? "Đang tạo..." : isPlaying ? "Dừng" : "Nghe Báo Cáo"}
    </button>
  );
}

// ------------------------------------------------------------------ //
//  Chat History Sidebar                                               //
// ------------------------------------------------------------------ //
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
    if (diffHours < 1) return "Just now";
    if (diffHours < 24) return `${Math.floor(diffHours)} hours ago`;
    if (diffHours < 48) return "Yesterday";
    return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
  };

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-20 flex">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative z-30 w-72 h-full bg-background border-r shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-primary" />
            <span className="font-semibold text-sm">Chat History</span>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {isLoadingSessions ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : chatSessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center px-4">
              <MessageSquare className="w-8 h-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No chat history</p>
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
                        · {session.message_count} messages
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(e, session.session_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 hover:text-destructive transition-all"
                  title="Delete"
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

// ------------------------------------------------------------------ //
//  Voice Input Hook (Web Speech API)                                  //
// ------------------------------------------------------------------ //
function useVoiceInput(onTranscript: (text: string) => void) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSupported(true);
      const recognition = new SpeechRecognition();
      recognition.lang = "vi-VN";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        onTranscript(transcript);
        setIsListening(false);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, [onTranscript]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current || isListening) return;
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch (e) {
      console.error("Failed to start recognition:", e);
    }
  }, [isListening]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current || !isListening) return;
    recognitionRef.current.stop();
    setIsListening(false);
  }, [isListening]);

  return { isListening, isSupported, startListening, stopListening };
}

// ------------------------------------------------------------------ //
//  Main ChatInterface                                                 //
// ------------------------------------------------------------------ //
export default function ChatInterface() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, startNewChat } = useAgentStore();
  const [showHistory, setShowHistory] = useState(false);
  const handleNewChat = useCallback(() => startNewChat(), [startNewChat]);
  const isTyping = false;
  const { sendMessage } = useAgentStream();

  // Voice Input
  const handleTranscript = useCallback((text: string) => {
    setInput((prev) => (prev ? `${prev} ${text}` : text));
  }, []);
  const { isListening, isSupported, startListening, stopListening } = useVoiceInput(handleTranscript);

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

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white/50 dark:bg-slate-900/30">
      {/* Chat History Sidebar */}
      <ChatHistorySidebar
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        userId="default_user"
      />

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
            <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">AI Data Analysis</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(true)}
            className="p-1.5 px-3 rounded-lg bg-white/50 dark:bg-zinc-800/50 hover:bg-white dark:hover:bg-zinc-800 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.1)] transition-all flex items-center gap-2 border border-zinc-200 dark:border-zinc-700"
            title="Chat History"
          >
            <History className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
            <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">History</span>
          </button>

          <button
            onClick={handleNewChat}
            className="p-1.5 px-3 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.1)] transition-all flex items-center gap-2 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400"
            title="New Conversation"
          >
            <PlusCircle className="w-4 h-4" />
            <span className="text-xs font-medium">New Chat</span>
          </button>
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
              I can analyze financial data, lookup customer metrics, explore products, or create statistical dashboards.
            </p>

            <div className="grid grid-cols-1 w-full max-w-md gap-3 text-left">
              <button 
                onClick={() => handleSuggestionClick("Analyze revenue this month vs last month")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-indigo-50/50 hover:border-indigo-200 dark:hover:bg-indigo-900/20 dark:hover:border-indigo-800 transition-all shadow-sm hover:shadow"
              >
                <BarChart2 className="w-5 h-5 text-indigo-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Analyze revenue this month vs last month</span>
              </button>
              <button 
                onClick={() => handleSuggestionClick("What are the top 5 best-selling products?")}
              <button
                onClick={() => handleSuggestionClick("Top 5 sản phẩm bán chạy nhất là gì?")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-emerald-50/50 hover:border-emerald-200 dark:hover:bg-emerald-900/20 dark:hover:border-emerald-800 transition-all shadow-sm hover:shadow"
              >
                <Search className="w-5 h-5 text-emerald-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Top 5 products by revenue</span>
              </button>
              <button 
                onClick={() => handleSuggestionClick("Create a business overview dashboard")}
                className="group flex gap-3 p-3.5 px-4 rounded-2xl bg-white dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/50 hover:bg-amber-50/50 hover:border-amber-200 dark:hover:bg-amber-900/20 dark:hover:border-amber-800 transition-all shadow-sm hover:shadow"
              >
                <Sparkles className="w-5 h-5 text-amber-500 shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm text-slate-600 dark:text-slate-300 font-medium">Create a business overview report dashboard</span>
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
                        <CheckCircle2 className="w-3.5 h-3.5" /> Queried {msg.metadata.action_type === 'sql' ? 'Database' : 'Knowledge Base'}
                      </div>
                      <div className="text-[11px] text-slate-500 bg-white/50 dark:bg-[#111827]/50 p-1.5 rounded-md font-mono truncate max-w-full">
                        {msg.metadata.action_input ? (typeof msg.metadata.action_input === 'string' ? msg.metadata.action_input : JSON.stringify(msg.metadata.action_input)) : "Executed..."}
                      </div>
                    </div>
                  )}

                  {/* Main Text Content */}
                  {msg.content && (
                    <div
                      className={cn(
                        "prose max-w-none break-words leading-relaxed",
                        msg.role === "user"
                          ? "prose-invert text-white marker:text-white"
                          : "prose-slate dark:prose-invert",
                        "prose-p:m-0 prose-ul:m-0 prose-li:m-0 prose-code:px-1 prose-code:py-0.5 prose-code:rounded-md prose-code:bg-black/10 dark:prose-code:bg-white/10 prose-code:before:content-none prose-code:after:content-none"
                      )}
                    >
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  )}

                  {/* SQL Viewer */}
                  {msg.metadata?.sql && <SQLViewer sql={msg.metadata.sql} />}

                  {/* Dashboard Notification Pill */}
                  {msg.metadata?.isDashboard && (
                    <div className="mt-3 flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-100 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-[13px] font-medium select-none shadow-sm pb-2 cursor-default">
                      <BarChart2 className="w-4 h-4" /> 
                      Created {msg.metadata.allCharts?.length || 0} charts on analytics board
                    </div>
                  )}

                  {/* 🔊 Audio Briefing Button — chỉ hiện cho assistant messages có nội dung */}
                  {msg.role === "assistant" && msg.content && msg.content.length > 20 && (
                    <AudioBriefingButton text={msg.content} />
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
              placeholder="Ask SIA anything about data..."
              disabled={isTyping}
              className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-full py-3.5 pl-11 pr-[88px] text-sm outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/50 transition-all font-medium disabled:opacity-50 text-slate-700 dark:text-slate-200 placeholder:text-slate-400 shadow-inner"
            />
            <div className="absolute right-1.5 top-1.5 bottom-1.5 flex items-center gap-1">
              <button
                type="button"
                className="w-[36px] h-full bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-full flex items-center justify-center transition-all disabled:opacity-40"
              >
                <Mic className="w-4 h-4" />
              </button>
              <button
                type="submit"
                disabled={!input.trim() || isTyping}
                className="w-[36px] h-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center transition-all disabled:opacity-40 disabled:hover:bg-indigo-600 shadow-md shadow-indigo-500/20"
              >
                {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 -ml-0.5" />}
              </button>
            </div>
          </div>
        </form>
        <div className="text-center mt-3">
          <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">AI can make mistakes. Verify important data before making decisions.</span>
        </div>
      </div>
    </div>
  );
}
