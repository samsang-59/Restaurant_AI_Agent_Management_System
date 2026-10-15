import { useEffect, useRef, useState } from "react";
import MenuGrid from "./MenuGrid.jsx";

const SUGGESTIONS = ["Show me the menu", "2 Butter Chicken", "1 Mango Lassi", "20 Paneer Tikka"];

export default function ChatPanel({ messages, busy, disabled, status, onSend }) {
  const [text, setText] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const submit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <section className="panel chat">
      <div className="panel-head">
        <h2>Your table</h2>
        <span className="panel-sub">Chat with the AI host</span>
      </div>

      <div className="messages">
        {messages.map((m) => {
          if (m.role === "divider") return <div key={m.id} className="divider"><span>{m.text}</span></div>;
          if (m.role === "system") return <div key={m.id} className={`banner banner-${m.reason === "served" ? "ok" : "end"}`}>{m.text}</div>;
          if (m.role === "error") return <div key={m.id} className="banner banner-error">⚠ {m.text}</div>;
          return (
            <div key={m.id} className={`row row-${m.role}`}>
              {m.role === "host" && <div className="avatar">AI</div>}
              <div className={`bubble bubble-${m.role}`}>
                <p>{m.text}</p>
                {m.menu && <MenuGrid items={m.menu} compact />}
              </div>
            </div>
          );
        })}
        {busy && (
          <div className="row row-host">
            <div className="avatar">AI</div>
            <div className="bubble bubble-host typing">
              <span className="typing-dots"><i /><i /><i /></span>
              <span className="typing-text">{status}</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="suggestion" disabled={busy || disabled} onClick={() => onSend(s)}>{s}</button>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={disabled ? "Preparing a fresh session…" : "e.g. 2 Hyderabadi Chicken Biryani"}
          disabled={busy || disabled}
          maxLength={1000}
          aria-label="Message"
        />
        <button type="submit" className="btn-primary" disabled={busy || disabled || !text.trim()}>Send</button>
      </form>
    </section>
  );
}
