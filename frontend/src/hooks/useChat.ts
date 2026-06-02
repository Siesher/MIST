"use client";

import { useCallback } from "react";
import { useChatStore } from "@/store/chatStore";
import { useWebSocket } from "./useWebSocket";
import { sendMessage as sendMessageRest, getHint as getHintRest } from "@/lib/api";
import type { Message, WSServerMessage, ChatMode } from "@/types/api";

interface UseChatOptions {
  sessionId: string;
  useStreaming?: boolean;
}

export function useChat({ sessionId, useStreaming = true }: UseChatOptions) {
  const addMessage = useChatStore((s) => s.addMessage);
  const setStreamingMessage = useChatStore((s) => s.setStreamingMessage);
  const appendStreamingContent = useChatStore((s) => s.appendStreamingContent);
  const setIsStreaming = useChatStore((s) => s.setIsStreaming);
  const setIsLoading = useChatStore((s) => s.setIsLoading);
  const setSessionState = useChatStore((s) => s.setSessionState);
  const setSessionMode = useChatStore((s) => s.setSessionMode);
  const beginStream = useChatStore((s) => s.beginStream);
  const finalizeStreamMetrics = useChatStore((s) => s.finalizeStreamMetrics);
  const setRestSuggested = useChatStore((s) => s.setRestSuggested);

  const handleWSMessage = useCallback(
    (msg: WSServerMessage) => {
      switch (msg.type) {
        case "connection_ready":
          setSessionState(sessionId, msg.session_state);
          break;

        case "token": {
          const state = useChatStore.getState();
          if (!state.isStreaming) {
            setIsStreaming(true);
            setIsLoading(false);
          }
          appendStreamingContent(msg.content, msg.is_thinking);
          break;
        }

        case "response_complete": {
          // Capture accumulated reasoning before clearing the stream so it stays
          // viewable on the persisted message (even after the answer).
          const reasoning = useChatStore.getState().streamingMessage?.thinkingContent || "";
          finalizeStreamMetrics(sessionId);
          setIsStreaming(false);
          setStreamingMessage(null);
          setSessionState(sessionId, msg.session_state);

          const tutorMessage: Message = {
            id: msg.message_id,
            session_id: sessionId,
            role: "tutor",
            content: msg.response.content,
            timestamp: new Date().toISOString(),
            move_type: msg.response.move_type,
            is_correct: msg.response.is_correct,
            thinking: reasoning || undefined,
            citations: msg.response.citations,
          };
          addMessage(sessionId, tutorMessage);
          break;
        }

        case "hint_response": {
          const hintMsg: Message = {
            id: `hint-${msg.hint_number}`,
            session_id: sessionId,
            role: "tutor",
            content: `Подсказка ${msg.hint_number}: ${msg.hint_text}`,
            timestamp: new Date().toISOString(),
            move_type: "hint",
          };
          addMessage(sessionId, hintMsg);
          break;
        }

        case "mode_changed": {
          setSessionMode(sessionId, msg.current_mode as ChatMode);
          if (msg.message) {
            const systemMsg: Message = {
              id: `mode-${Date.now()}`,
              session_id: sessionId,
              role: "tutor",
              content: msg.message,
              timestamp: new Date().toISOString(),
              move_type: "system",
            };
            addMessage(sessionId, systemMsg);
          }
          break;
        }

        case "suggest_rest":
          // Cognitive overload flagged by the profiler → offer a "sleep & reflect"
          // break. ChatScreen reconciles this with the idle timer into one card.
          setRestSuggested(true);
          break;

        case "error":
          setIsStreaming(false);
          setIsLoading(false);
          setStreamingMessage(null);
          break;

        case "knowledge_update":
          break;
      }
    },
    [sessionId, addMessage, setStreamingMessage, appendStreamingContent, setIsStreaming, setIsLoading, setSessionState, setSessionMode, finalizeStreamMetrics, setRestSuggested],
  );

  const {
    connected: wsConnected,
    sendMessage: wsSendMessage,
    requestHint: wsRequestHint,
    sendRaw: wsSendRaw,
  } = useWebSocket({
    sessionId: useStreaming ? sessionId : null,
    onMessage: handleWSMessage,
  });

  const sendMessage = useCallback(
    async (content: string) => {
      // Add user message immediately
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        session_id: sessionId,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };
      addMessage(sessionId, userMsg);
      setIsLoading(true);
      beginStream();

      if (useStreaming && wsConnected) {
        wsSendMessage(content);
      } else {
        // Fallback to REST
        try {
          const result = await sendMessageRest(sessionId, content);
          setIsLoading(false);

          const tutorMsg: Message = {
            id: result.message_id,
            session_id: sessionId,
            role: "tutor",
            content: result.tutor_response.content,
            timestamp: new Date().toISOString(),
            move_type: result.tutor_response.move_type,
            is_correct: result.tutor_response.is_correct,
          };
          addMessage(sessionId, tutorMsg);
          setSessionState(sessionId, result.session_state);
        } catch {
          setIsLoading(false);
        }
      }
    },
    [sessionId, useStreaming, wsConnected, wsSendMessage, addMessage, setIsLoading, setSessionState, beginStream],
  );

  const requestHint = useCallback(async () => {
    if (useStreaming && wsConnected) {
      wsRequestHint();
    } else {
      try {
        const result = await getHintRest(sessionId);
        const hintMsg: Message = {
          id: `hint-${result.hint_number}`,
          session_id: sessionId,
          role: "tutor",
          content: `Подсказка ${result.hint_number}: ${result.hint_text}`,
          timestamp: new Date().toISOString(),
          move_type: "hint",
        };
        addMessage(sessionId, hintMsg);
      } catch {
        /* hint unavailable */
      }
    }
  }, [sessionId, useStreaming, wsConnected, wsRequestHint, addMessage]);

  const changeMode = useCallback(
    async (mode: ChatMode) => {
      // Cancel any active streaming
      const state = useChatStore.getState();
      if (state.isStreaming || state.isLoading) {
        setIsStreaming(false);
        setIsLoading(false);
        setStreamingMessage(null);
      }

      // Optimistic update
      setSessionMode(sessionId, mode);

      if (useStreaming && wsConnected && wsSendRaw) {
        // Send via WebSocket
        wsSendRaw({ type: "mode_change", mode });
      } else {
        // Fallback to REST
        try {
          const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
          await fetch(`${API_BASE}/sessions/${sessionId}/mode`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode }),
          });
        } catch {
          /* mode change failed */
        }
      }
    },
    [sessionId, useStreaming, wsConnected, wsSendRaw, setSessionMode, setIsStreaming, setIsLoading, setStreamingMessage],
  );

  return {
    sendMessage,
    requestHint,
    changeMode,
    wsConnected,
  };
}
