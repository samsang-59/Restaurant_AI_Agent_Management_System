"""SSE endpoint test with the brain and kitchen faked out."""

import json

import pytest
from fastapi.testclient import TestClient

from app import config, main, tools
from app.brain import Intent
from app.graph import build_graph
from app.menu import menu_store

from .test_graph import FakeBrain, ScriptedRng


@pytest.fixture
def client(monkeypatch):
    menu_store.reset()
    monkeypatch.setattr(config, "COOK_DELAY_SECONDS", 0)
    monkeypatch.setattr(config, "SERVE_DELAY_SECONDS", 0)
    monkeypatch.setattr(tools, "rng", ScriptedRng(["ok", "fail", "ok", "ok"]))
    brain = FakeBrain([Intent(intent="order", dish_name="Veg Biryani", quantity=1)])
    monkeypatch.setattr(main, "_graph", build_graph(brain))
    return TestClient(main.app)


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def test_chat_streams_steps_then_final(client):
    sid = client.post("/api/session").json()["session_id"]
    evs = events(client.post("/api/chat", json={"session_id": sid, "message": "1 veg biryani"}))
    nodes = [(e["node"], e["status"]) for e in evs if e["type"] == "step"]
    assert nodes == [("understand", "info"), ("take_order", "success"), ("cook", "success"),
                     ("serve", "failure"), ("cook", "success"), ("serve", "success"), ("served", "success")]
    final = evs[-1]
    assert final["type"] == "final" and final["session_status"] == "ended" and final["next_session_id"]
    assert final["counters"]["serve"] == 1
    # an ended session no longer accepts messages
    assert client.post("/api/chat", json={"session_id": sid, "message": "hi"}).status_code == 409
