import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, Loader2 } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { env } from "../config/env";

interface ChatMessage {
  role: "user" | "agent";
  text: string;
}

/**
 * Minimal Markdown renderer for agent replies: bold, italic, bullet
 * lists, and line breaks. Deliberately not a full Markdown library
 * (react-markdown, etc.) -- the model only ever needs these few
 * constructs for chat replies, and a tiny custom parser keeps bundle
 * size down instead of pulling in a full dependency for it.
 */
function renderFormattedText(text: string): React.ReactNode {
  const lines = text.split("\n");

  return lines.map((line, lineIndex) => {
    const isBullet = /^\s*[-*]\s+/.test(line);
    const content = isBullet ? line.replace(/^\s*[-*]\s+/, "") : line;
    const parts = parseInline(content);

    return (
      <span key={lineIndex}>
        {isBullet && <span className="mr-1.5">•</span>}
        {parts}
        {lineIndex < lines.length - 1 && <br />}
      </span>
    );
  });
}

function parseInline(text: string): React.ReactNode[] {
  // Order matters: bold (**text**) checked before single-asterisk italic
  const tokenRegex = /(\*\*.+?\*\*|\*.+?\*|_.+?_)/g;
  const segments = text.split(tokenRegex).filter((s) => s.length > 0);

  return segments.map((segment, i) => {
    if (segment.startsWith("**") && segment.endsWith("**")) {
      return <strong key={i}>{segment.slice(2, -2)}</strong>;
    }
    if (
      (segment.startsWith("*") && segment.endsWith("*")) ||
      (segment.startsWith("_") && segment.endsWith("_"))
    ) {
      return <em key={i}>{segment.slice(1, -1)}</em>;
    }
    return <span key={i}>{segment}</span>;
  });
}

const SESSION_KEY = "sokolink_agent_session_id";

function getOrCreateSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function ChatWidget() {
  const { token, user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef(getOrCreateSessionId());

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          role: "agent",
          text: `Hi${user?.name ? " " + user.name : ""}! I'm Soko-Link's assistant. Ask me about products, orders, delivery, or payments.`,
        },
      ]);
    }
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setIsSending(true);
    setError("");

    try {
      const res = await fetch(`${env.agentApiBase}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: text,
        }),
      });

      if (!res.ok) {
        throw new Error(`Agent responded with ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => [...prev, { role: "agent", text: data.reply }]);
    } catch (err) {
      setError("Couldn't reach the assistant right now. Please try again in a moment.");
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "Sorry, I'm having trouble connecting right now. Please try again shortly." },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <>
      <button
        onClick={() => setIsOpen((v) => !v)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-2xl transition-transform hover:scale-105 active:scale-95 md:bottom-6 md:right-6"
      >
        {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
      </button>

      {isOpen && (
        <div className="fixed bottom-24 right-5 z-50 flex h-[70vh] max-h-[560px] w-[92vw] max-w-sm flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl md:bottom-28 md:right-6">
          <div className="flex items-center justify-between border-b border-border bg-brand px-4 py-3 text-white">
            <div>
              <p className="text-sm font-bold">Soko-Link Assistant</p>
              <p className="text-xs opacity-80">{user ? "Signed in" : "Guest"} · usually replies instantly</p>
            </div>
            <button onClick={() => setIsOpen(false)} aria-label="Close chat">
              <X size={20} />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-brand text-white rounded-br-sm"
                      : "bg-surface-soft text-text rounded-bl-sm"
                  }`}
                >
                  {m.role === "agent" ? renderFormattedText(m.text) : m.text}
                </div>
              </div>
            ))}
            {isSending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm bg-surface-soft px-3 py-2 text-sm text-text-muted">
                  <Loader2 size={14} className="animate-spin" />
                  Thinking…
                </div>
              </div>
            )}
          </div>

          {error && <p className="px-4 pb-1 text-xs text-red-500">{error}</p>}

          <div className="flex items-center gap-2 border-t border-border p-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about products, orders, delivery…"
              className="flex-1 rounded-xl border border-border bg-surface-soft px-3 py-2 text-sm outline-none focus:border-brand"
              disabled={isSending}
            />
            <button
              onClick={handleSend}
              disabled={isSending || !input.trim()}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand text-white disabled:opacity-50"
              aria-label="Send"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
