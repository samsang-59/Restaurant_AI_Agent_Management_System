import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMenu, newSession, sendMessage } from "./api.js";
import ChatPanel from "./components/ChatPanel.jsx";
import AgentPanel from "./components/AgentPanel.jsx";
import MenuGrid from "./components/MenuGrid.jsx";
import { describeStep } from "./steps.js";

const IDLE_PIPELINE = { understand: "idle", take_order: "idle", cook: "idle", serve: "idle" };
const ZERO_COUNTERS = { take_order: 0, cook: 0, serve: 0 };
const RESET_DELAY_MS = 2800;

const END_REASON_TEXT = {
  served: "Order served",
  invalid: "Query was not about ordering food",
  limit_take_order: "Order-taking limit reached",
  limit_cook: "Cooking limit reached",
  limit_serve: "Serving limit reached",
};

let nextId = 1;
const msg = (role, text, extra = {}) => ({ id: nextId++, role, text, ...extra });

const WELCOME = (name) =>
  msg("host", `Namaste and welcome to ${name}! I'm your AI host. Tell me which dish you'd like and how many portions — for example "2 Butter Chicken".`);

// Which node lights up next after a step, so the pipeline shows the agent moving forward.
function nextActive(step) {
  if (step.node === "understand" && step.intent === "order" && step.dish_name && step.quantity != null) return "take_order";
  if (step.node === "take_order" && step.status === "success") return "cook";
  if (step.node === "cook" && step.status === "success") return "serve";
  if (step.node === "serve" && step.status === "failure") return "cook";
  return null;
}

export default function App() {
  const [restaurant, setRestaurant] = useState("Saffron & Spice");
  const [menu, setMenu] = useState([]);
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [sessionId, setSessionId] = useState(null);
  const [sessionNo, setSessionNo] = useState(1);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [pipeline, setPipeline] = useState(IDLE_PIPELINE);
  const [counters, setCounters] = useState(ZERO_COUNTERS);
  const [trace, setTrace] = useState([]);
  const [status, setStatus] = useState("Waiting for your order");
  const [menuOpen, setMenuOpen] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const [m, sid] = await Promise.all([fetchMenu(), newSession()]);
        setRestaurant(m.restaurant);
        setMenu(m.items);
        setMaxAttempts(m.max_attempts);
        setSessionId(sid);
        setMessages([WELCOME(m.restaurant)]);
      } catch (e) {
        setMessages([msg("error", `Could not reach the agent server: ${e.message}`)]);
      }
    })();
  }, []);

  const addTrace = useCallback((step) => {
    setTrace((t) => [...t, { id: nextId++, time: new Date(), ...step, text: describeStep(step, maxAttempts) }]);
  }, [maxAttempts]);

  const startNewSession = useCallback((sid) => {
    setSessionId(sid);
    setSessionNo((n) => n + 1);
    setPipeline(IDLE_PIPELINE);
    setCounters(ZERO_COUNTERS);
    setTrace([]);
    setStatus("Waiting for your order");
    setMessages((m) => [...m, msg("divider", "New session started"), WELCOME(restaurant)]);
    setResetting(false);
  }, [restaurant]);

  const handleSend = useCallback(async (text) => {
    if (!text.trim() || busy || resetting || !sessionId) return;
    setMessages((m) => [...m, msg("guest", text)]);
    setBusy(true);
    setPipeline({ ...IDLE_PIPELINE, understand: "active" });
    setStatus("AI host is reading your message…");
    try {
      await sendMessage(sessionId, text, (ev) => {
        if (ev.type === "step") {
          addTrace(ev);
          setStatus(describeStep(ev, maxAttempts));
          if (["understand", "take_order", "cook", "serve"].includes(ev.node)) {
            setPipeline((p) => {
              const nxt = { ...p, [ev.node]: ev.node === "understand" ? "success" : ev.status };
              const a = nextActive(ev);
              if (a) nxt[a] = "active";
              return nxt;
            });
          } else if (ev.node === "respond" || ev.node === "end_session" || ev.node === "served") {
            setPipeline((p) => ({ ...p, understand: ev.node === "end_session" ? "failure" : "success" }));
          }
          if (ev.attempt) setCounters((c) => ({ ...c, [ev.node]: ev.attempt }));
        } else if (ev.type === "final") {
          setMenu(ev.menu);
          setCounters(ev.counters);
          setMessages((m) => [...m, msg("host", ev.reply, { menu: ev.show_menu ? ev.menu : null })]);
          if (ev.session_status === "ended") {
            setStatus(END_REASON_TEXT[ev.end_reason] || "Session ended");
            setResetting(true);
            setMessages((m) => [...m, msg("system", `Session ended · ${END_REASON_TEXT[ev.end_reason] || ev.end_reason}. Starting a fresh session…`, { reason: ev.end_reason })]);
            setTimeout(() => startNewSession(ev.next_session_id), RESET_DELAY_MS);
          } else {
            setStatus("Waiting for your reply");
          }
        } else if (ev.type === "error") {
          setMessages((m) => [...m, msg("error", ev.message)]);
          setStatus("Something went wrong");
        }
      });
    } catch (e) {
      setMessages((m) => [...m, msg("error", e.message)]);
      setStatus("Something went wrong");
    } finally {
      setBusy(false);
    }
  }, [busy, resetting, sessionId, addTrace, maxAttempts, startNewSession]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" alt="" className="brand-mark" />
          <div>
            <h1>{restaurant}</h1>
            <p className="tagline">Autonomous dining · LangGraph agent</p>
          </div>
        </div>
        <div className="topbar-right">
          <span className="chip"><span className={`dot ${busy ? "dot-live" : ""}`} />Session #{sessionNo}</span>
          <button className="btn-ghost" onClick={() => setMenuOpen((o) => !o)}>{menuOpen ? "Hide menu" : "View menu"}</button>
        </div>
      </header>

      {menuOpen && (
        <section className="menu-drawer">
          <MenuGrid items={menu} />
        </section>
      )}

      <main className="layout">
        <ChatPanel
          messages={messages}
          busy={busy}
          disabled={resetting || !sessionId}
          status={status}
          onSend={handleSend}
        />
        <AgentPanel pipeline={pipeline} counters={counters} maxAttempts={maxAttempts} trace={trace} status={status} busy={busy} />
      </main>
    </div>
  );
}
