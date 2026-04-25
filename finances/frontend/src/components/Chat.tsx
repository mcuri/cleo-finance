import { useState, useEffect, useRef } from "react";
import { api } from "../api";
import type { ChatMessage } from "../types";

const STORAGE_KEY = "cleo_chat_history";

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const history = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const { reply } = await api.chat(text, history);
      setMessages(prev => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Something went wrong. Please try again.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  };

  const clearHistory = () => {
    if (!confirm("Clear chat history?")) return;
    setMessages([]);
  };

  return (
    <div style={{
      maxWidth: 720,
      margin: "0 auto",
      display: "flex",
      flexDirection: "column",
      height: "calc(100vh - 100px)",
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: "1rem",
        borderBottom: "1px solid var(--border)",
        marginBottom: "1rem",
      }}>
        <h1 style={{ margin: 0 }}>✦ Chat</h1>
        <button onClick={clearHistory} style={{
          background: "none",
          border: "1px solid var(--border)",
          color: "var(--text-muted)",
          borderRadius: 6,
          padding: "0.25rem 0.75rem",
          fontSize: "0.85rem",
        }}>
          Clear history
        </button>
      </div>

      <div style={{
        flex: 1,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        paddingBottom: "0.5rem",
      }}>
        {messages.length === 0 && (
          <p style={{ textAlign: "center", marginTop: "3rem", color: "var(--text-muted)" }}>
            Paste expenses or ask anything about your finances.<br />
            <span style={{ fontSize: "0.85rem" }}>e.g. "Stanford FCU charge $15.66 at The Brazilian Spot" or "how much did I spend on food this month?"</span>
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "75%",
              padding: "0.75rem 1rem",
              borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: msg.role === "user" ? "#312e81" : "var(--surface)",
              border: msg.role === "assistant" ? "1px solid var(--border)" : "none",
              color: msg.role === "user" ? "#e2e8f0" : "var(--text-secondary)",
              fontSize: "0.9rem",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{
              padding: "0.75rem 1rem",
              borderRadius: "12px 12px 12px 2px",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: "1.2rem",
              letterSpacing: 4,
            }}>
              ···
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
        <div style={{
          display: "flex",
          gap: "0.75rem",
          alignItems: "flex-end",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: "0.75rem",
        }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Paste expenses or ask anything... (Cmd+Enter to send)"
            rows={2}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text-primary)",
              fontSize: "0.9rem",
              resize: "none",
              maxHeight: 200,
              width: "auto",
              margin: 0,
              padding: 0,
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              background: "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "0.5rem 1.25rem",
              fontWeight: 600,
              fontSize: "0.9rem",
              flexShrink: 0,
            }}
          >
            Send ↑
          </button>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", margin: "0.25rem 0 0", textAlign: "right" }}>
          Cmd+Enter to send
        </p>
      </div>
    </div>
  );
}
