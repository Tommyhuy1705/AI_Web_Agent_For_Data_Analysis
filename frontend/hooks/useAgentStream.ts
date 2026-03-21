/**
 * useAgentStream Hook
 * Xử lý kết nối SSE (Server-Sent Events) từ FastAPI Backend.
 * Quản lý luồng streaming cho chat và alarm notifications.
 * Hỗ trợ multi-chart cho dashboard mode.
 */

"use client";

import { useCallback, useRef } from "react";
import { useAgentStore, type ChatMessage, type ChartConfig } from "@/store/useAgentStore";
import { BACKEND_URL } from "@/lib/utils";
import { alarmPayloadSchema, chartConfigSchema } from "@/lib/schemas";

// ============================================================
// Types
// ============================================================

interface SSEEvent {
  event: string;
  data: unknown;
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
  const alarmReconnectAttemptRef = useRef(0);

  const MAX_CHAT_RETRIES = 2;
  const MAX_ALARM_RETRIES = 5;

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
    sessionId,
    setSessionId,
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

      const safeParseJson = (value: string): unknown => {
        try {
          return JSON.parse(value);
        } catch {
          return null;
        }
      };

      const parseSSEBlock = (block: string): SSEEvent | null => {
        const lines = block.split("\n");
        let event = "message";
        const dataLines: string[] = [];

        for (const rawLine of lines) {
          const line = rawLine.trimEnd();
          if (!line || line.startsWith(":")) {
            continue;
          }
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
            continue;
          }
          if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }

        if (!dataLines.length) {
          return null;
        }

        const rawData = dataLines.join("\n");
        const parsed = safeParseJson(rawData);
        return {
          event,
          data: parsed ?? { raw: rawData },
        };
      };

      try {
        let fullContent = "";
        let chartConfig: ChartConfig | null = null;
        let allCharts: ChartConfig[] = [];
        let insight = "";
        let sql = "";
        let hasStreamedData = false;
        let isDashboard = false;

        // Helper to process each SSE event
        const processSSEEvent = (event: string, data: any) => {
          switch (event) {
            case "start":
              setStatusMessage("Bắt đầu xử lý...");
              // Cập nhật session_id từ backend nếu backend tạo session mới
              if ((data as any).session_id && (data as any).session_id !== sessionId) {
                setSessionId((data as any).session_id);
              }
              break;

            case "status":
              setStatusMessage(data.message || "");
              break;

            case "sql_generated":
              sql = data.sql || "";
              if (data.tool_used === "dashboard_builder") {
                isDashboard = true;
              }
              setStatusMessage("SQL đã được sinh...");
              break;

            case "data_ready":
              {
                const rowCount = data.row_count || 0;
                const panelCount = data.panel_count;
                if (panelCount) {
                  isDashboard = true;
                  setStatusMessage(`Dashboard: ${panelCount} biểu đồ, ${rowCount} dòng dữ liệu`);
                } else {
                  setStatusMessage(`Đã truy vấn ${rowCount} dòng dữ liệu`);
                }
              }
              break;

            case "message_chunk":
              hasStreamedData = true;
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
              {
                const parsedChart = chartConfigSchema.safeParse(data);
                if (parsedChart.success) {
                  const chart = parsedChart.data as ChartConfig;
                  
                  if (isDashboard) {
                    // Dashboard mode: collect all charts
                    allCharts.push(chart);
                    setActiveChart(chart);
                    // Update metadata with all charts so far
                    updateLastAssistantMessage(fullContent, {
                      chartConfig: allCharts.length === 1 ? chart : allCharts[0],
                      allCharts: [...allCharts],
                      isDashboard: true,
                      panelCount: allCharts.length,
                    });
                  } else {
                    // Single chart mode
                    chartConfig = chart;
                    setActiveChart(chartConfig);
                    updateLastAssistantMessage(fullContent, { chartConfig });
                  }
                } else {
                  setStatusMessage("Đang xử lý biểu đồ...");
                }
              }
              break;

            case "insight":
              insight = data.text || "";
              if (insight && !fullContent.includes(insight)) {
                fullContent += "\n\n" + insight;
              }
              updateLastAssistantMessage(fullContent, { insight });
              break;

            case "complete":
              {
                const meta: any = {
                  sql,
                  rowCount: data.row_count,
                  chartConfig: isDashboard ? (allCharts[0] || null) : chartConfig,
                  insight,
                };
                if (isDashboard) {
                  meta.allCharts = allCharts;
                  meta.isDashboard = true;
                  meta.panelCount = data.panel_count || allCharts.length;
                }
                updateLastAssistantMessage(
                  fullContent || data.message || "Hoàn thành!",
                  meta
                );
              }
              break;

            case "error":
              updateLastAssistantMessage(
                `Lỗi: ${data.message || "Đã xảy ra lỗi không xác định"}`
              );
              setConnectionStatus("disconnected");
              break;

            case "done":
              setStatusMessage("");
              break;
          }
        };

        const consumeStream = async () => {
          const response = await fetch(`${BACKEND_URL}/api/chat/stream`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              message,
              conversation_id: conversationId,
              user_id: "default_user",
              session_id: sessionId,  // Truyền session_id cho Chat History
            }),
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          setConnectionStatus("connected");

          const reader = response.body?.getReader();
          if (!reader) {
            throw new Error("No response body");
          }

          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }
            hasStreamedData = true;
            buffer += decoder.decode(value, { stream: true });

            let delimiterIndex = buffer.indexOf("\n\n");
            while (delimiterIndex !== -1) {
              const eventBlock = buffer.slice(0, delimiterIndex);
              buffer = buffer.slice(delimiterIndex + 2);
              const parsedEvent = parseSSEBlock(eventBlock);
              if (parsedEvent) {
                processSSEEvent(parsedEvent.event, parsedEvent.data as any);
              }
              delimiterIndex = buffer.indexOf("\n\n");
            }
          }

          const finalEvent = parseSSEBlock(buffer.trim());
          if (finalEvent) {
            processSSEEvent(finalEvent.event, finalEvent.data as any);
          }
        };

        let attempt = 0;
        while (attempt <= MAX_CHAT_RETRIES) {
          try {
            await consumeStream();
            break;
          } catch (error: any) {
            if (controller.signal.aborted) {
              throw error;
            }

            attempt += 1;
            const shouldRetry = attempt <= MAX_CHAT_RETRIES && hasStreamedData;
            if (!shouldRetry) {
              throw error;
            }

            setConnectionStatus("connecting");
            setStatusMessage(`Mạng gián đoạn, đang tự kết nối lại (${attempt}/${MAX_CHAT_RETRIES})...`);
            await new Promise((resolve) => setTimeout(resolve, 800 * attempt));
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
      alarmReconnectAttemptRef.current = 0;

      eventSource.onopen = () => {
        alarmReconnectAttemptRef.current = 0;
      };

      eventSource.addEventListener("alarm", (event) => {
        try {
          const rawData = JSON.parse(event.data);
          const parsed = alarmPayloadSchema.safeParse(rawData);
          if (!parsed.success) {
            return;
          }

          const data = parsed.data;
          addAlarm({
            id: `alarm-${Date.now()}`,
            type: data.type || "revenue_alarm",
            severity: data.severity || "warning",
            message: data.message || "",
            naturalMessage: data.natural_message,
            currentRevenue: Number(data.current_revenue || 0),
            previousRevenue: Number(data.previous_revenue || 0),
            changePct: Number(data.change_pct || 0),
            timestamp: data.timestamp || new Date().toISOString(),
            read: false,
          });
        } catch {
          // Parse error, skip
        }
      });

      eventSource.onerror = () => {
        if (alarmReconnectAttemptRef.current >= MAX_ALARM_RETRIES) {
          unsubscribeAlarms();
          return;
        }

        alarmReconnectAttemptRef.current += 1;
        const nextDelay = Math.min(10000, alarmReconnectAttemptRef.current * 1500);
        setTimeout(() => {
          unsubscribeAlarms();
          subscribeAlarms();
        }, nextDelay);
      };
    } catch {
      // EventSource not supported or connection error
    }
  }, [addAlarm]);

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
