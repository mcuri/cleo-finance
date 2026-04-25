import { useState, useEffect, useRef } from "react";
import { api } from "../api";
import type { ChatMessage } from "../types";

const STORAGE_KEY = "cleo_chat_history";
const MAX_FILE_BYTES = 10 * 1024 * 1024;

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
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [attachError, setAttachError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const attachFile = (file: File | null | undefined) => {
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setAttachError("File too large (max 10 MB).");
      return;
    }
    setAttachError("");
    setAttachedFile(file);
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const file = e.clipboardData.files[0];
    if (file?.type.startsWith("image/")) {
      e.preventDefault();
      attachFile(file);
    }
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && !attachedFile) || loading) return;

    let attachment: ChatMessage["attachment"] | undefined;
    if (attachedFile) {
      if (attachedFile.type.startsWith("image/")) {
        attachment = {
          type: "image",
          label: attachedFile.name,
          dataUrl: URL.createObjectURL(attachedFile),
        };
      } else {
        attachment = { type: "pdf", label: attachedFile.name };
      }
    }

    const userMsg: ChatMessage = {
      role: "user",
      content: text || "[File attached]",
      attachment,
    };
    const history = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    const fileToSend = attachedFile;
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setLoading(true);

    try {
      const form = new FormData();
      form.append("message", text || "[File attached]");
      form.append("history", JSON.stringify(history.map(m => ({ role: m.role, content: m.content }))));
      if (fileToSend) form.append("file", fileToSend);
      const { reply } = await api.chatForm(form);
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
    <div
      style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", height: "calc(100vh - 100px)" }}
      onPaste={handlePaste}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "1rem", borderBottom: "1px solid var(--border)", marginBottom: "1rem" }}>
        <h1 style={{ margin: 0 }}>✦ Chat</h1>
        <button onClick={clearHistory} style={{ background: "none", border: "1px solid var(--border)", color: "var(--text-muted)", borderRadius: 6, padding: "0.25rem 0.75rem", fontSize: "0.85rem" }}>
          Clear history
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.75rem", paddingBottom: "0.5rem" }}>
        {messages.length === 0 && (
          <p style={{ textAlign: "center", marginTop: "3rem", color: "var(--text-muted)" }}>
            Paste expenses, attach an image, or upload a bank statement PDF.<br />
            <span style={{ fontSize: "0.85rem" }}>Or ask anything about your finances.</span>
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
              {msg.attachment?.type === "image" && msg.attachment.dataUrl && (
                <img
                  src={msg.attachment.dataUrl}
                  alt="attachment"
                  style={{ maxWidth: 200, maxHeight: 150, borderRadius: 6, display: "block", marginBottom: "0.5rem" }}
                />
              )}
              {msg.attachment?.type === "pdf" && (
                <div style={{ fontSize: "0.8rem", color: "#a5b4fc", marginBottom: "0.25rem" }}>
                  📄 {msg.attachment.label}
                </div>
              )}
              {msg.content !== "[File attached]" && msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{ padding: "0.75rem 1rem", borderRadius: "12px 12px 12px 2px", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-muted)", fontSize: "1.2rem", letterSpacing: 4 }}>
              ···
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
        {attachError && (
          <p style={{ color: "var(--expense)", fontSize: "0.8rem", margin: "0 0 0.5rem" }}>{attachError}</p>
        )}
        {attachedFile && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            {attachedFile.type.startsWith("image/") ? (
              <img
                src={URL.createObjectURL(attachedFile)}
                alt="preview"
                style={{ height: 60, borderRadius: 6, border: "1px solid var(--border)" }}
              />
            ) : (
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", background: "var(--surface)", border: "1px solid var(--border)", padding: "0.25rem 0.5rem", borderRadius: 6 }}>
                📄 {attachedFile.name}
              </span>
            )}
            <button
              onClick={() => { setAttachedFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
              style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.1rem", padding: "0 0.25rem" }}
            >
              ×
            </button>
          </div>
        )}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "0.75rem" }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf"
            style={{ display: "none" }}
            onChange={e => attachFile(e.target.files?.[0])}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="Attach image or PDF"
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.2rem", padding: "0 0.25rem", flexShrink: 0 }}
          >
            📎
          </button>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Paste expenses or ask anything... (Cmd+Enter to send)"
            rows={2}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--text-primary)", fontSize: "0.9rem", resize: "none", maxHeight: 200, width: "auto", margin: 0, padding: 0 }}
          />
          <button
            onClick={send}
            disabled={loading || (!input.trim() && !attachedFile)}
            style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "0.5rem 1.25rem", fontWeight: 600, fontSize: "0.9rem", flexShrink: 0 }}
          >
            Send ↑
          </button>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", margin: "0.25rem 0 0", textAlign: "right" }}>
          Cmd+Enter to send · 📎 attach image or PDF
        </p>
      </div>
    </div>
  );
}
