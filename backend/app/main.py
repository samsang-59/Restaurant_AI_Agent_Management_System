"""FastAPI server exposing the restaurant agent to the frontend.

POST /api/chat streams Server-Sent Events: one `step` event per graph node as
it finishes, then a `final` event with the host's reply and session state.
"""

import json
import logging
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config
from .brain import ClaudeBrain
from .graph import build_graph
from .menu import RESTAURANT_NAME, menu_store

log = logging.getLogger("restaurant")

app = FastAPI(title=f"{RESTAURANT_NAME} Agent")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

_graph = None
_graph_lock = threading.Lock()
_ended_sessions: set[str] = set()


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = build_graph(ClaudeBrain())
        return _graph


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=1000)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/api/menu")
def get_menu():
    return {"restaurant": RESTAURANT_NAME, "items": menu_store.snapshot(), "max_attempts": config.MAX_ATTEMPTS_PER_STAGE}


@app.post("/api/menu/reset")
def reset_menu():
    menu_store.reset()
    return {"items": menu_store.snapshot()}


@app.post("/api/session")
def new_session():
    return {"session_id": str(uuid.uuid4())}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if req.session_id in _ended_sessions:
        raise HTTPException(409, "This session has ended. Start a new session.")
    graph = get_graph()
    run_config = {"configurable": {"thread_id": req.session_id}}

    def events():
        try:
            for chunk in graph.stream({"user_input": req.message}, run_config, stream_mode="updates"):
                for update in chunk.values():
                    if update and "step" in update:
                        yield _sse({"type": "step", **update["step"]})
            state = graph.get_state(run_config).values
            ended = state.get("session_status") == "ended"
            if ended:
                _ended_sessions.add(req.session_id)
            yield _sse({
                "type": "final",
                "reply": state.get("reply", ""),
                "show_menu": state.get("show_menu", False),
                "menu": menu_store.snapshot(),
                "session_status": "ended" if ended else "active",
                "end_reason": state.get("end_reason"),
                "counters": {s: state.get(f"{s}_failures", 0) for s in ("take_order", "cook", "serve")},
                "next_session_id": str(uuid.uuid4()) if ended else None,
            })
        except Exception as exc:  # surface failures (e.g. missing API key) to the UI
            log.exception("chat turn failed")
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
