"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { getWebSocketUrl } from "@/lib/api";
import type { WSServerMessage, WSClientMessage } from "@/types/api";

interface UseWebSocketOptions {
  sessionId: string | null;
  onMessage: (msg: WSServerMessage) => void;
  onError?: (error: Event) => void;
  onClose?: (event: CloseEvent) => void;
}

export function useWebSocket({
  sessionId,
  onMessage,
  onError,
  onClose,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  // Store callbacks in refs to avoid reconnection on callback change
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onCloseRef.current = onClose;
  }, [onMessage, onError, onClose]);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close(1000);
    }

    const url = getWebSocketUrl(sessionId);
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSServerMessage;
        // Use setTimeout to prevent React batching and ensure immediate render
        setTimeout(() => onMessageRef.current(data), 0);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = (event) => {
      onErrorRef.current?.(event);
    };

    ws.onclose = (event) => {
      setConnected(false);
      onCloseRef.current?.(event);

      // Reconnect with exponential backoff
      if (
        event.code !== 1000 &&
        event.code !== 1008 &&
        reconnectAttempts.current < maxReconnectAttempts
      ) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;
        setTimeout(connect, delay);
      }
    };

    wsRef.current = ws;
  }, [sessionId]); // Only depend on sessionId, not callbacks

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close(1000);
    };
  }, [connect]);

  const send = useCallback((msg: WSClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const sendMessage = useCallback(
    (content: string) => {
      send({
        type: "message",
        content,
        timestamp: Date.now(),
      });
    },
    [send],
  );

  const requestHint = useCallback(() => {
    send({ type: "hint_request" });
  }, [send]);

  const sendRaw = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return {
    connected,
    send,
    sendMessage,
    requestHint,
    sendRaw,
  };
}
