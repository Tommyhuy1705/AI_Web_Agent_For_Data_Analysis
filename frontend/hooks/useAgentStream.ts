/**
 * useAgentStream Hook
 * Xử lý kết nối SSE (Server-Sent Events) từ FastAPI Backend.
 * Quản lý luồng streaming cho chat và alarm notifications.
 */

"use client";

import { useCallback, useRef } from "react";
import { useAgentStore, type ChatMessage, type ChartConfig } from "@/store/useAgentStore";
import { BACKEND_URL } from "@/lib/utils";

// ============================================================
// Types
// ============================================================

interface SSEEvent {
  event: string;
  data: any;
}

interface UseAgentStreamReturn {
  sendMessage: (message: string) => Promise<void>;
  cancelStream: () => void;
  subscribeAlarms: () => void;
  unsubscribeAlarms: () => void;
}

// ============================================================
// Hook Implementation
// ============================================================

export function useAgentStream(): UseAgentStreamReturn {
  const abortControllerRef = useRef<AbortController | null>(null);
  const alarmEventSourceRef = useRef<EventSource | null>(null);

  const {
    addMessage,
    updateLastAssistantMessage,
    setActiveChart,
    setLoading,
    setStreaming,
    setCurrentStreamContent,
    appendStreamContent,
    setConversationId,
    setConnectionStatus,
    setStatusMessage,
    addAlarm,
    conversationId,
  } = useAgentStore();

  /**
   * Gửi message và nhận SSE stream từ Backend.
   */
  const sendMessage = useCallback(
    async (message: string) => {
      // Cancel any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: message,
        timestamp: new Date(),
      };
      addMessage(userMessage);

      // Add placeholder assistant message
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        metadata: {
          agentThoughts: [],
        },
      };
      addMessage(assistantMessage);

      setLoading(true);
      setStreaming(true);
      setCurrentStreamContent("");
      setConnectionStatus("connecting");

      try {
        const response = await fetch(`${BACKEND_URL}/api/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message,
            conversation_id: conversationId,
            user_id: "default_user",
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        setConnectionStatus("connected");

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let fullContent = "";
        let chartConfig: ChartConfig | null = null;
        let insight = "";
        let sql = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let eventType = "";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6).trim();

              if (eventType && eventData) {
                try {
                  const parsed = JSON.parse(eventData);
                  await processSSEEvent(eventType, parsed);
                } catch {
                  // Non-JSON data, skip
                }
                eventType = "";
                eventData = "";
              }
            }
          }
        }

        // Helper to process each SSE event
        async function processSSEEvent(event: string, data: any) {
          switch (event) {
            case "start":
              setStatusMessage("Bắt đầu xử lý...");
              break;

            case "status":
              setStatusMessage(data.message || "");
              break;

            case "sql_generated":
              sql = data.sql || "";
              setStatusMessage("SQL đã được sinh...");
              break;

            case "data_ready":
              setStatusMessage(`Đã truy vấn ${data.row_count || 0} dòng dữ liệu`);
              break;

            case "message_chunk":
              fullContent += data.chunk || "";
              appendStreamContent(data.chunk || "");
              updateLastAssistantMessage(fullContent);
              if (data.conversation_id) {
                setConversationId(data.conversation_id);
              }
              break;

            case "message_complete":
              fullContent = data.full_answer || fullContent;
              updateLastAssistantMessage(fullContent);
              if (data.conversation_id) {
                setConversationId(data.conversation_id);
              }
              break;

            case "agent_thought":
              // Lưu agent thoughts vào metadata
              break;

            case "chart":
              chartConfig = data as ChartConfig;
              setActiveChart(chartConfig);
              updateLastAssistantMessage(fullContent, { chartConfig });
              break;

            case "insight":
              insight = data.text || "";
              if (insight && !fullContent.includes(insight)) {
                fullContent += "\n\n" + insight;
              }
              updateLastAssistantMessage(fullContent, { insight });
              break;

            case "complete":
              updateLastAssistantMessage(fullContent || data.message || "Hoàn thành!", {
                sql,
                rowCount: data.row_count,
                chartConfig,
                insight,
              });
              break;

            case "error":
              updateLastAssistantMessage(
                `Lỗi: ${data.message || "Đã xảy ra lỗi không xác định"}`
              );
              break;

            case "done":
              setStatusMessage("");
              break;
          }
        }
      } catch (error: any) {
        if (error.name === "AbortError") {
          updateLastAssistantMessage("Đã hủy yêu cầu.");
        } else {
          updateLastAssistantMessage(
            `Lỗi kết nối: ${error.message}. Vui lòng kiểm tra Backend server.`
          );
        }
        setConnectionStatus("disconnected");
      } finally {
        setLoading(false);
        setStreaming(false);
        setStatusMessage("");
        abortControllerRef.current = null;
      }
    },
    [conversationId]
  );

  /**
   * Hủy stream hiện tại.
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreaming(false);
    setLoading(false);
  }, []);

  /**
   * Subscribe alarm SSE stream.
   */
  const subscribeAlarms = useCallback(() => {
    if (alarmEventSourceRef.current) return;

    try {
      const eventSource = new EventSource(`${BACKEND_URL}/api/alarm/stream`);
      alarmEventSourceRef.current = eventSource;

      eventSource.addEventListener("alarm", (event) => {
        try {
          const data = JSON.parse(event.data);
          addAlarm({
            id: `alarm-${Date.now()}`,
            type: data.type || "revenue_alarm",
            severity: data.severity || "warning",
            message: data.message || "",
            naturalMessage: data.natural_message,
            currentRevenue: data.current_revenue || 0,
            previousRevenue: data.previous_revenue || 0,
            changePct: data.change_pct || 0,
            timestamp: data.timestamp || new Date().toISOString(),
            read: false,
          });
        } catch {
          // Parse error, skip
        }
      });

      eventSource.onerror = () => {
        // Reconnect after 5 seconds
        setTimeout(() => {
          unsubscribeAlarms();
          subscribeAlarms();
        }, 5000);
      };
    } catch {
      // EventSource not supported or connection error
    }
  }, []);

  /**
   * Unsubscribe alarm SSE stream.
   */
  const unsubscribeAlarms = useCallback(() => {
    if (alarmEventSourceRef.current) {
      alarmEventSourceRef.current.close();
      alarmEventSourceRef.current = null;
    }
  }, []);

  return {
    sendMessage,
    cancelStream,
    subscribeAlarms,
    unsubscribeAlarms,
  };
}
