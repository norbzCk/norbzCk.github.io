import { useCallback, useEffect, useRef, useState } from "react";
import { env } from "../../config/env";

export type DeliveryMessageState = "sending" | "sent" | "delivered" | "read";

export interface ChatMessage {
  id?: string;
  sender_id: number;
  sender_name: string;
  sender_role: string;
  text: string;
  timestamp: string;
  status?: DeliveryMessageState;
}

export interface LocationUpdate {
  lat: number;
  lng: number;
  rider_name: string;
}

export function useDeliverySocket(orderId: number | string | undefined, token: string | null, onOrderStatus?: (payload: { order_id: number; status: string; reason?: string; updated_by?: string; updated_at?: string }) => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [location, setLocation] = useState<LocationUpdate | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [presence, setPresence] = useState<Array<{ user?: number; state?: string; updated_at?: string }>>([]);
  const [isOtherPartyTyping, setIsOtherPartyTyping] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const optimisticIdRef = useRef(0);
  const typingTimeoutRef = useRef<number | null>(null);
  const onOrderStatusRef = useRef(onOrderStatus);
  onOrderStatusRef.current = onOrderStatus;

  useEffect(() => {
    if (!orderId || !token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = env.apiBase.replace(/^https?:\/\//, "");
    const wsUrl = `${protocol}//${host}/notifications/ws/delivery/${orderId}?token=${token}`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "history") {
        setMessages(Array.isArray(data.messages) ? data.messages : []);
      } else if (data.type === "chat") {
        const incomingId = String(data.id || data.client_id || `server-${Date.now()}`);

        setMessages((prev) => {
          const optimisticMatch = data.client_id ? prev.findIndex((item) => item.id === String(data.client_id)) : -1;

          if (optimisticMatch >= 0) {
            const next = [...prev];
            next[optimisticMatch] = {
              ...next[optimisticMatch],
              ...data,
              id: incomingId,
              status: data.status || "delivered",
            };
            return next;
          }

          return [...prev, { ...data, id: incomingId, status: data.status || "delivered" }];
        });
        if (!data.client_id && socketRef.current?.readyState === WebSocket.OPEN && data.id) {
          socketRef.current.send(
            JSON.stringify({
              type: "receipt",
              message_id: String(data.id),
              status: "read",
            }),
          );
        }
      } else if (data.type === "chat_status" || data.type === "receipt") {
        setMessages((prev) =>
          prev.map((item) =>
            item.id && String(item.id) === String(data.message_id)
              ? { ...item, status: data.status || item.status }
              : item,
          ),
        );
      } else if (data.type === "typing") {
        setIsOtherPartyTyping(Boolean(data.is_typing));
        if (typingTimeoutRef.current) {
          window.clearTimeout(typingTimeoutRef.current);
        }
        if (data.is_typing) {
          typingTimeoutRef.current = window.setTimeout(() => setIsOtherPartyTyping(false), 2200);
        }
      } else if (data.type === "location") {
        setLocation(data);
      } else if (data.type === "presence") {
        setPresence((prev) => {
          const others = prev.filter((item) => item.user !== data.user);
          return [...others, data];
        });
      } else if (data.type === "order_status" && typeof onOrderStatusRef.current === "function") {
        onOrderStatusRef.current({
          order_id: Number(data.order_id),
          status: String(data.status || ""),
          reason: data.reason ? String(data.reason) : undefined,
          updated_by: data.updated_by ? String(data.updated_by) : undefined,
          updated_at: data.updated_at ? String(data.updated_at) : undefined,
        });
      }
    };

    socket.onclose = () => {
      setIsConnected(false);
    };

    socket.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      if (typingTimeoutRef.current) {
        window.clearTimeout(typingTimeoutRef.current);
      }
      socket.close();
    };
  }, [orderId, token]);

  const sendChat = useCallback((text: string) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;

    const optimisticId = `local-${Date.now()}-${optimisticIdRef.current++}`;
    setMessages((prev) => [
      ...prev,
      {
        id: optimisticId,
        sender_id: 0,
        sender_name: "You",
        sender_role: "self",
        text,
        timestamp: new Date().toISOString(),
        status: "sending",
      },
    ]);

    socketRef.current.send(
      JSON.stringify({
        type: "chat",
        text,
        timestamp: new Date().toISOString(),
        client_id: optimisticId,
      }),
    );
  }, []);

  const sendTyping = useCallback((isTyping: boolean) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;

    socketRef.current.send(
      JSON.stringify({
        type: "typing",
        is_typing: isTyping,
      }),
    );
  }, []);

  const sendLocation = useCallback((lat: number, lng: number) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) return;

    socketRef.current.send(
      JSON.stringify({
        type: "location",
        lat,
        lng,
      }),
    );
  }, []);

  return {
    messages,
    location,
    isConnected,
    presence,
    isOtherPartyTyping,
    sendChat,
    sendTyping,
    sendLocation,
  };
}
