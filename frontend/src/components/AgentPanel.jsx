import { useEffect, useRef } from "react";

const NODES = [
  { key: "understand", title: "AI Host", sub: "LLM · understands query", icon: "✦" },
  { key: "take_order", title: "take_order", sub: "Menu & stock check", icon: "📝" },
  { key: "cook", title: "cook", sub: "Kitchen", icon: "🔥" },
  { key: "serve", title: "serve", sub: "To your table", icon: "🍽" },
];

const STATUS_LABEL = { idle: "Idle", active: "Working", success: "Done", failure: "Failed" };

function AttemptMeter({ label, used, max }) {
  return (
    <div className="meter">
      <span className="meter-label">{label}</span>
      <span className="pips">
        {Array.from({ length: max }, (_, i) => <i key={i} className={i < used ? "pip-used" : ""} />)}
      </span>
      <span className="meter-count">{used}/{max}</span>
    </div>
  );
}

export default function AgentPanel({ pipeline, counters, maxAttempts, trace, status, busy }) {
  const logRef = useRef(null);
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [trace]);

  return (
    <aside className="panel agent">
      <div className="panel-head">
        <h2>Agent kitchen</h2>
        <span className={`live ${busy ? "on" : ""}`}><span className="dot" />{busy ? "Live" : "Idle"}</span>
      </div>

      <div className="pipeline">
        {NODES.map((n, i) => (
          <div key={n.key} className="pipe-step">
            <div className={`node node-${pipeline[n.key]}`}>
              <div className="node-icon">{n.icon}</div>
              <div className="node-text">
                <span className="node-title">{n.title}</span>
                <span className="node-sub">{n.sub}</span>
              </div>
              <span className="node-status">{STATUS_LABEL[pipeline[n.key]]}</span>
            </div>
            {i < NODES.length - 1 && <div className={`connector ${pipeline[NODES[i + 1].key] !== "idle" ? "connector-on" : ""}`} />}
          </div>
        ))}
        {pipeline.serve === "failure" && <div className="loop-note">↺ serve failed → sent back to cook</div>}
      </div>

      <div className="status-line">{status}</div>

      <div className="meters">
        <h3>Retry budget this session</h3>
        <AttemptMeter label="take_order" used={counters.take_order} max={maxAttempts} />
        <AttemptMeter label="cook" used={counters.cook} max={maxAttempts} />
        <AttemptMeter label="serve" used={counters.serve} max={maxAttempts} />
      </div>

      <div className="trace">
        <h3>Agent trace</h3>
        <ol ref={logRef}>
          {trace.length === 0 && <li className="trace-empty">Steps will appear here as the agent works.</li>}
          {trace.map((t) => (
            <li key={t.id} className={`trace-${t.status}`}>
              <time>{t.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>
              <code>{t.node}</code>
              <span>{t.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}
