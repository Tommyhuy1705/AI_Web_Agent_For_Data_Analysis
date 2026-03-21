/**
 * Zustand Store - Agent State Management
 * Quản lý state cho chat messages, charts, alarms, và loading states.
 * Hỗ trợ multi-chart cho dashboard mode.
 * v2: Thêm Chat History & Context Memory (session_id, chatSessions)
 */

import { create } from "zustand";

// ============================================================
// Types
// ============================================================

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  metadata?: {
    sql?: string;
    rowCount?: number;
    chartConfig?: ChartConfig | null;
    allCharts?: ChartConfig[];
    isDashboard?: boolean;
    panelCount?: number;
    insight?: string;
    agentThoughts?: AgentThought[];
    action_type?: string;
    action_input?: string;
  };
}

export interface ChartConfig {
  chart_type: string;
  title: string;
  description?: string;
  config: Record<string, any>;
  data: Record<string, any>[];
  dashboard_panel?: string;
}

export interface AgentThought {
  thought: string;
  tool?: string;
  toolInput?: string;
  action_type?: string;
  action_input?: string;
}

export interface AlarmEvent {
  id: string;
  type: string;
  severity: "warning" | "critical";
  message: string;
  naturalMessage?: string;
  currentRevenue: number;
  previousRevenue: number;
  changePct: number;
  timestamp: string;
  read: boolean;
}

export interface ChatSession {
  session_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_active: boolean;
}

// ============================================================
// Store Interface
// ============================================================

interface AgentStore {
  // Chat State
  messages: ChatMessage[];
  conversationId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  currentStreamContent: string;

  // Session State (Chat History)
  sessionId: string | null;
  chatSessions: ChatSession[];
  isLoadingSessions: boolean;

  // Canvas State (biểu đồ hiện tại)
  activeChart: ChartConfig | null;
  chartHistory: ChartConfig[];

  // Alarm State
  alarms: AlarmEvent[];
  unreadAlarmCount: number;

  // Status
  connectionStatus: "connected" | "disconnected" | "connecting";
  statusMessage: string;

  // Actions - Chat
  addMessage: (message: ChatMessage) => void;
  updateLastAssistantMessage: (content: string, metadata?: Partial<ChatMessage["metadata"]>) => void;
  setConversationId: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setCurrentStreamContent: (content: string) => void;
  appendStreamContent: (chunk: string) => void;
  clearMessages: () => void;

  // Actions - Session (New Chat & History)
  setSessionId: (id: string | null) => void;
  startNewChat: () => void;
  setChatSessions: (sessions: ChatSession[]) => void;
  addChatSession: (session: ChatSession) => void;
  removeChatSession: (sessionId: string) => void;
  loadSession: (session: ChatSession, messages: ChatMessage[]) => void;
  setLoadingSessions: (loading: boolean) => void;

  // Actions - Canvas
  setActiveChart: (chart: ChartConfig | null) => void;
  addChartToHistory: (chart: ChartConfig) => void;

  // Actions - Alarm
  addAlarm: (alarm: AlarmEvent) => void;
  markAlarmRead: (id: string) => void;
  clearAlarms: () => void;

  // Actions - Status
  setConnectionStatus: (status: "connected" | "disconnected" | "connecting") => void;
  setStatusMessage: (message: string) => void;
}

// ============================================================
// Store Implementation
// ============================================================

export const useAgentStore = create<AgentStore>((set, get) => ({
  // Initial State
  messages: [],
  conversationId: null,
  isLoading: false,
  isStreaming: false,
  currentStreamContent: "",

  // Session State
  sessionId: null,
  chatSessions: [],
  isLoadingSessions: false,

  activeChart: null,
  chartHistory: [],

  alarms: [],
  unreadAlarmCount: 0,

  connectionStatus: "disconnected",
  statusMessage: "",

  // Chat Actions
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateLastAssistantMessage: (content, metadata) =>
    set((state) => {
      const messages = [...state.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].role === "assistant") {
        messages[lastIdx] = {
          ...messages[lastIdx],
          content,
          metadata: { ...messages[lastIdx].metadata, ...metadata },
        };
      }
      return { messages };
    }),

  setConversationId: (id) => set({ conversationId: id }),
  setLoading: (loading) => set({ isLoading: loading }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setCurrentStreamContent: (content) => set({ currentStreamContent: content }),
  appendStreamContent: (chunk) =>
    set((state) => ({
      currentStreamContent: state.currentStreamContent + chunk,
    })),
  clearMessages: () =>
    set({
      messages: [],
      conversationId: null,
      currentStreamContent: "",
      activeChart: null,
      chartHistory: [],
    }),

  // Session Actions
  setSessionId: (id) => set({ sessionId: id }),

  /**
   * startNewChat: Reset toàn bộ workspace về trạng thái ban đầu.
   * Được gọi khi user nhấn nút "New Chat".
   */
  startNewChat: () =>
    set({
      messages: [],
      conversationId: null,
      sessionId: null,
      currentStreamContent: "",
      activeChart: null,
      chartHistory: [],
      isLoading: false,
      isStreaming: false,
      statusMessage: "",
    }),

  setChatSessions: (sessions) => set({ chatSessions: sessions }),

  addChatSession: (session) =>
    set((state) => ({
      chatSessions: [session, ...state.chatSessions],
    })),

  removeChatSession: (sessionId) =>
    set((state) => ({
      chatSessions: state.chatSessions.filter((s) => s.session_id !== sessionId),
    })),

  /**
   * loadSession: Load lại một session cũ từ lịch sử.
   * Reset workspace và điền messages từ session đã chọn.
   */
  loadSession: (session, messages) =>
    set({
      sessionId: session.session_id,
      conversationId: null,
      messages,
      currentStreamContent: "",
      activeChart: null,
      chartHistory: [],
      isLoading: false,
      isStreaming: false,
      statusMessage: "",
    }),

  setLoadingSessions: (loading) => set({ isLoadingSessions: loading }),

  // Canvas Actions
  setActiveChart: (chart) =>
    set((state) => {
      if (chart) {
        return {
          activeChart: chart,
          chartHistory: [...state.chartHistory, chart],
        };
      }
      return { activeChart: chart };
    }),

  addChartToHistory: (chart) =>
    set((state) => ({
      chartHistory: [...state.chartHistory, chart],
    })),

  // Alarm Actions
  addAlarm: (alarm) =>
    set((state) => ({
      alarms: [alarm, ...state.alarms],
      unreadAlarmCount: state.unreadAlarmCount + 1,
    })),

  markAlarmRead: (id) =>
    set((state) => ({
      alarms: state.alarms.map((a) =>
        a.id === id ? { ...a, read: true } : a
      ),
      unreadAlarmCount: Math.max(0, state.unreadAlarmCount - 1),
    })),

  clearAlarms: () => set({ alarms: [], unreadAlarmCount: 0 }),

  // Status Actions
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setStatusMessage: (message) => set({ statusMessage: message }),
}));
