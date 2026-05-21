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
