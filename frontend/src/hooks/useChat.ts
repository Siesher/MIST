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

  const handleWSMessage = useCallback(
    (msg: WSServerMessage) => {
      console.log("[Chat] Handling WS message:", msg.type);
      switch (msg.type) {
        case "connection_ready":
          console.log("[Chat] Connection ready, session state:", msg.session_state);
          setSessionState(sessionId, msg.session_state);
          break;

        case "token": {
          const state = useChatStore.getState();
          if (!state.isStreaming) {
            console.log("[Chat] Starting streaming, isThinking:", msg.is_thinking);
            setIsStreaming(true);
            setIsLoading(false);
          }
          appendStreamingContent(msg.content, msg.is_thinking);
          break;
        }

        case "response_complete": {
          console.log("[Chat] Response complete");
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
          console.log("[Chat] Mode changed:", msg.previous_mode, "->", msg.current_mode);
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

        case "error":
          setIsStreaming(false);
          setIsLoading(false);
          setStreamingMessage(null);
          console.error("WebSocket error:", msg.code, msg.message);
          break;

        case "knowledge_update":
          break;
      }
    },
    [sessionId, addMessage, setStreamingMessage, appendStreamingContent, setIsStreaming, setIsLoading, setSessionState, setSessionMode],
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
        } catch (error) {
          setIsLoading(false);
          console.error("Failed to send message:", error);
        }
      }
    },
    [sessionId, useStreaming, wsConnected, wsSendMessage, addMessage, setIsLoading, setSessionState],
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
      } catch (error) {
        console.error("Failed to get hint:", error);
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
        } catch (error) {
          console.error("Failed to change mode:", error);
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
