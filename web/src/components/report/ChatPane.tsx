import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "../Icon";

export type ChatMessage = { id: number; role: string; body: string; meta?: Record<string, unknown> | null };

// The chat window shared by report threads and Q&A (design: report chat). One message at a time:
// while the AI writes, the box stays open for typing but Send waits. Enter sends, Shift+Enter breaks
// the line. `note` renders extra lines under an AI message (blocked changes, citations).
export function ChatPane({
  messages,
  busy,
  onSend,
  placeholder = "Ask the AI",
  disabled = false,
  disabledReason,
  context,
  note,
  maxLength,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onSend: (text: string) => void;
  placeholder?: string;
  disabled?: boolean;
  disabledReason?: string;
  context?: ReactNode;
  note?: (m: ChatMessage) => ReactNode;
  maxLength?: number;
}) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, busy]);
  const canSend = !busy && !disabled && text.trim().length > 0;
  const send = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };
  return (
    <section className="card chat-pane" aria-label="Chat with the AI">
      <div className="chat-log" role="log" aria-live="polite">
        {messages.length === 0 && <p className="muted chat-empty">No messages yet.</p>}
        {messages.map((m) => (
          <div key={m.id} className={`chat-msg chat-${m.role === "ai" ? "ai" : "me"}`}>
            <span className="chat-who">{m.role === "ai" ? "AI" : "You"}</span>
            <p className="chat-body">{m.body}</p>
            {note?.(m)}
          </div>
        ))}
        {busy && (
          <div className="chat-msg chat-ai chat-writing" aria-label="The AI is writing">
            <span className="chat-who">AI</span>
            <span className="pulse-bar short" aria-hidden="true" />
            <span className="muted">Writing, the draft is read-only until it finishes.</span>
          </div>
        )}
        <div ref={end} />
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        {context}
        <textarea
          aria-label="Message"
          placeholder={disabled ? disabledReason : placeholder}
          value={text}
          maxLength={maxLength}
          disabled={disabled}
          rows={2}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button type="submit" className="btn-primary" disabled={!canSend} aria-label="Send">
          <Icon name="play" />
          Send
        </button>
      </form>
    </section>
  );
}
