// Zustand store for chat state management

import { create } from "zustand";
import type { Message, Session, SessionState, ChatMode } from "@/types/api";

interface StreamingMessage {
  content: string;
  isThinking: boolean;
  thinkingContent: string;
}

interface ChatState {
  // Sessions
  sessions: Session[];
  activeSessionId: string | null;

  // Messages per session
  messages: Record<string, Message[]>;

  // Streaming state
  streamingMessage: StreamingMessage | null;
  isStreaming: boolean;
  isLoading: boolean;

  // Session state
  sessionStates: Record<string, SessionState>;

  // Mode per session
  sessionModes: Record<string, ChatMode>;

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

  setSessionState: (sessionId: string, state: SessionState) => void;

  setSessionMode: (sessionId: string, mode: ChatMode) => void;

  setTheme: (theme: "dark" | "light") => void;
  toggleTheme: () => void;

  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
}

export const useChatStore = create<ChatState>()((set) => ({
  sessions: [],
  activeSessionId: null,
  messages: {},
  streamingMessage: null,
  isStreaming: false,
  isLoading: false,
  sessionStates: {},
  sessionModes: {},
  theme: "dark",
  sidebarOpen: true,

  setSessions: (sessions) => set({ sessions }),
  addSession: (session) =>
    set((state) => ({
      sessions: [session, ...state.sessions],
    })),
  removeSession: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== sessionId),
      messages: Object.fromEntries(
        Object.entries(state.messages).filter(([k]) => k !== sessionId),
      ),
    })),
  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

  setMessages: (sessionId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [sessionId]: messages },
    })),
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
      if (!state.streamingMessage) {
        return {
          streamingMessage: {
            content: isThinking ? "" : content,
            isThinking,
            thinkingContent: isThinking ? content : "",
          },
        };
      }
      // If switching from thinking to response, keep thinking content
      if (state.streamingMessage.isThinking && !isThinking) {
        return {
          streamingMessage: {
            ...state.streamingMessage,
            isThinking: false,
            content: content,
          },
        };
      }
      // Append to appropriate field
      if (isThinking) {
        return {
          streamingMessage: {
            ...state.streamingMessage,
            thinkingContent: state.streamingMessage.thinkingContent + content,
          },
        };
      }
      return {
        streamingMessage: {
          ...state.streamingMessage,
          content: state.streamingMessage.content + content,
        },
      };
    }),
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),
  setIsLoading: (loading) => set({ isLoading: loading }),

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
