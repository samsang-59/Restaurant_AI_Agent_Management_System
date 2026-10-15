# Saffron & Spice — Restaurant AI Agent

A restaurant ordering agent built with **LangGraph** and **Claude**, with a FastAPI backend and a React frontend that shows the agent working live.

## How it works

A guest's message goes to the LLM, which decides whether it's a food order. Orders then run through three tools:

| Tool | Success | Failure |
|---|---|---|
| `take_order(dish_name, quantity)` | Dish is on the menu and in stock → stock reserved → `cook` | Back to the LLM: it shows the menu and asks the guest to choose again. If the quantity was the problem, it tells them how many are left and they can reply **yes** to take that many. |
| `cook(dish_name, quantity)` | → `serve` | Back to the LLM: apologises, reserved stock is released, and the guest chooses a dish and quantity again (this goes through `take_order` again). |
| `serve(dish_name, quantity)` | Order complete → session ends | Sent straight back to `cook`. |

- **Off-topic queries** (e.g. "what is the capital of India") end the session right away.
- Each stage has its **own limit of 3 failures** per session. Hitting any limit makes the agent apologise and end the session.
- When a session ends (order served, off-topic query, or limit reached), the UI starts a **new session automatically**.
- The **menu** is fixed at startup (`backend/app/menu.py`, 11 Indian dishes). Stock goes down as orders are served.
- **Cook and serve failures are random.** Set how often they happen with `COOK_FAILURE_RATE` / `SERVE_FAILURE_RATE`.
- Each order is **one dish**. If the guest asks for several dishes, the host asks them to order one at a time.
- If a message is food-related but no order can be placed yet (a greeting, asking for the menu, saying "no" to an offer, or a missing quantity), the host replies with the menu. This does not use up an attempt.

```
understand ──invalid──────────────────────────────▶ end_session
    │ need_info ──▶ respond
    ▼ order
take_order ──fail──▶ (limit? end_session : respond)
    ▼ ok
  cook ◀──────────────────────┐
    │ fail ──▶ (limit? end_session : respond)
    ▼ ok                      │
  serve ──fail──▶ (limit? end_session : cook)
    ▼ ok
 served (session complete)
```

The graph runs once per guest message. Between messages, an `InMemorySaver` checkpointer (keyed by session id) keeps the session's attempt counters, any pending quantity offer, and the conversation.

## Project layout

```
backend/
  app/menu.py     predefined menu + thread-safe stock store
  app/tools.py    take_order / cook / serve LangChain tools
  app/brain.py    Claude: intent + argument extraction, guest replies
  app/graph.py    LangGraph StateGraph wiring the flow above
  app/main.py     FastAPI; /api/chat streams each graph step over SSE
  tests/          flow tests with a scripted LLM and kitchen
frontend/         React (Vite) UI: chat, live agent pipeline, retry meters, trace
```

## Running it

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173 (proxies /api to :8000)
```

Tests:

```bash
cd backend && pytest
```

## Configuration (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model |
| `ANTHROPIC_EFFORT` | `low` | Reasoning effort for the LLM calls |
| `MAX_ATTEMPTS_PER_STAGE` | `3` | Failure limit for each of take_order / cook / serve |
| `COOK_FAILURE_RATE` / `SERVE_FAILURE_RATE` | `0.2` | Chance of a simulated failure |
| `COOK_DELAY_SECONDS` / `SERVE_DELAY_SECONDS` | `1.5` / `1.0` | Simulated work time |
