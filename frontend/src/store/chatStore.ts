// Zustand store for chat state management

import { create } from "zustand";
import type { Message, Session, SessionState, ChatMode } from "@/types/api";

interface StreamingMessage {
  content: string;
  isThinking: boolean;
  thinkingContent: string;
}

interface StreamMetrics {
  startedAt: number | null;           // ms timestamp when first token arrived
  thinkingStartedAt: number | null;   // ms timestamp when thinking started
  thinkingEndedAt: number | null;     // ms timestamp when thinking finished
  thinkingTokens: number;             // tokens in thinking phase
  responseTokens: number;             // tokens in response phase
  firstTokenAt: number | null;        // time-to-first-token (from request send)
  requestSentAt: number | null;       // when user sent request
}

interface SessionMetrics {
  totalTokens: number;
  latencies: number[];                // last N response durations in ms
  lastLatency: number | null;
}

interface ChatState {
  // Sessions
  sessions: Session[];
  activeSessionId: string | null;

  // Messages per session
  messages: Record<string, Message[]>;

  // Streaming state
  streamingMessage: StreamingMessage | null;
  streamMetrics: StreamMetrics;
  isStreaming: boolean;
  isLoading: boolean;

  // Session state
  sessionStates: Record<string, SessionState>;

  // Mode per session
  sessionModes: Record<string, ChatMode>;

  // Session-level metrics
  sessionMetrics: Record<string, SessionMetrics>;

  // Active model name + backend metadata (from /health)
  modelName: string | null;
  backendKind: string | null;       // "ollama" | "huggingface"
  turboQuant: boolean;
  contextLength: number | null;

  // Theme
  theme: "dark" | "light";

  // Sidebar
  sidebarOpen: boolean;

  // Actions
  setSessions: (sessions: Session[]) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
  setActiveSession: (sessionId: string | null) => void;

  setMessages: (sessionId: string, messages: Message[]) => void;
  addMessage: (sessionId: string, message: Message) => void;

  setStreamingMessage: (msg: StreamingMessage | null) => void;
  appendStreamingContent: (content: string, isThinking?: boolean) => void;
  setIsStreaming: (streaming: boolean) => void;
  setIsLoading: (loading: boolean) => void;

  // Metrics actions
  beginStream: () => void;
  resetStreamMetrics: () => void;
  recordTokenTimings: (isThinking: boolean, tokenCount: number) => void;
  finalizeStreamMetrics: (sessionId: string) => void;

  setModelName: (name: string) => void;
  setBackendInfo: (info: { kind?: string; turbo_quant?: boolean; context_length?: number }) => void;

  setSessionState: (sessionId: string, state: SessionState) => void;

  setSessionMode: (sessionId: string, mode: ChatMode) => void;

  setTheme: (theme: "dark" | "light") => void;
  toggleTheme: () => void;

  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
}

const INITIAL_STREAM_METRICS: StreamMetrics = {
  startedAt: null,
  thinkingStartedAt: null,
  thinkingEndedAt: null,
  thinkingTokens: 0,
  responseTokens: 0,
  firstTokenAt: null,
  requestSentAt: null,
};

// Rough token estimate from character count (4 chars ≈ 1 token for English/Russian mix)
function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.round(text.length / 4));
}

export const useChatStore = create<ChatState>()((set) => ({
  sessions: [],
  activeSessionId: null,
  messages: {},
  streamingMessage: null,
  streamMetrics: { ...INITIAL_STREAM_METRICS },
  isStreaming: false,
  isLoading: false,
  sessionStates: {},
  sessionModes: {},
  sessionMetrics: {},
  modelName: null,
  backendKind: null,
  turboQuant: false,
  contextLength: null,
  theme: "dark",
  sidebarOpen: true,

  setSessions: (sessions) => set({ sessions }),
  addSession: (session) => set((state) => ({ sessions: [session, ...state.sessions] })),
  removeSession: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== sessionId),
      messages: Object.fromEntries(Object.entries(state.messages).filter(([k]) => k !== sessionId)),
    })),
  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

  setMessages: (sessionId, messages) =>
    set((state) => ({ messages: { ...state.messages, [sessionId]: messages } })),
  addMessage: (sessionId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [sessionId]: [...(state.messages[sessionId] || []), message],
      },
    })),

  setStreamingMessage: (msg) => set({ streamingMessage: msg }),

  appendStreamingContent: (content, isThinking = false) =>
    set((state) => {
      const now = performance.now();
      const tokensDelta = estimateTokens(content);
      const metrics = { ...state.streamMetrics };

      // First token arrives
      if (metrics.startedAt === null) {
        metrics.startedAt = now;
        if (metrics.requestSentAt !== null) {
          metrics.firstTokenAt = now - metrics.requestSentAt;
        }
      }

      if (isThinking) {
        if (metrics.thinkingStartedAt === null) metrics.thinkingStartedAt = now;
        metrics.thinkingTokens += tokensDelta;
      } else {
        // First non-thinking token → close thinking phase
        if (metrics.thinkingStartedAt !== null && metrics.thinkingEndedAt === null) {
          metrics.thinkingEndedAt = now;
        }
        metrics.responseTokens += tokensDelta;
      }

      // Build streaming message as before
      let sm = state.streamingMessage;
      if (!sm) {
        sm = {
          content: isThinking ? "" : content,
          isThinking,
          thinkingContent: isThinking ? content : "",
        };
      } else if (sm.isThinking && !isThinking) {
        sm = { ...sm, isThinking: false, content: content };
      } else if (isThinking) {
        sm = { ...sm, thinkingContent: sm.thinkingContent + content };
      } else {
        sm = { ...sm, content: sm.content + content };
      }

      return { streamingMessage: sm, streamMetrics: metrics };
    }),

  setIsStreaming: (streaming) => set({ isStreaming: streaming }),
  setIsLoading: (loading) => set({ isLoading: loading }),

  beginStream: () =>
    set(() => ({
      streamMetrics: {
        ...INITIAL_STREAM_METRICS,
        requestSentAt: performance.now(),
      },
    })),

  resetStreamMetrics: () => set({ streamMetrics: { ...INITIAL_STREAM_METRICS } }),

  recordTokenTimings: () => {
    /* handled in appendStreamingContent */
  },

  finalizeStreamMetrics: (sessionId) =>
    set((state) => {
      const sm = state.streamMetrics;
      const totalTokens = sm.thinkingTokens + sm.responseTokens;
      const latency =
        sm.startedAt !== null && sm.requestSentAt !== null
          ? performance.now() - sm.requestSentAt
          : null;

      const existing = state.sessionMetrics[sessionId] || {
        totalTokens: 0,
        latencies: [],
        lastLatency: null,
      };

      const newLatencies = latency !== null ? [...existing.latencies, latency].slice(-10) : existing.latencies;

      return {
        sessionMetrics: {
          ...state.sessionMetrics,
          [sessionId]: {
            totalTokens: existing.totalTokens + totalTokens,
            latencies: newLatencies,
            lastLatency: latency,
          },
        },
      };
    }),

  setModelName: (name) => set({ modelName: name }),
  setBackendInfo: (info) =>
    set({
      backendKind: info.kind ?? null,
      turboQuant: info.turbo_quant ?? false,
      contextLength: info.context_length ?? null,
    }),

  setSessionState: (sessionId, sessionState) =>
    set((state) => ({
      sessionStates: { ...state.sessionStates, [sessionId]: sessionState },
    })),

  setSessionMode: (sessionId, mode) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("mits-preferred-mode", mode);
    }
    set((state) => ({
      sessionModes: { ...state.sessionModes, [sessionId]: mode },
    }));
  },

  setTheme: (theme) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("mits-theme", theme);
      document.documentElement.classList.toggle("dark", theme === "dark");
    }
    set({ theme });
  },
  toggleTheme: () =>
    set((state) => {
      const newTheme = state.theme === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        localStorage.setItem("mits-theme", newTheme);
        document.documentElement.classList.toggle("dark", newTheme === "dark");
      }
      return { theme: newTheme };
    }),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
