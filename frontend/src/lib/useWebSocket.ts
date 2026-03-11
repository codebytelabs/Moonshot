"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { getWsUrl } from "./api";

export interface WsMessage {
  type: string;
  data: Record<string, unknown>;
  ts: string;
}

export function useSwarmSocket() {
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // ping keepalive
        const ping = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
        }, 30000);
        ws.addEventListener("close", () => clearInterval(ping));
      };

      ws.onmessage = (ev) => {
        try {
          const msg: WsMessage = JSON.parse(ev.data);
          if (msg.type === "pong") return;
          setMessages((prev) => [...prev.slice(-500), msg]);
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    } catch {}
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return { messages, connected };
}
