"""Flow tests for the LangGraph agent, using a scripted brain instead of the real LLM
and a scripted RNG instead of random cook/serve failures."""

import uuid

import pytest

from app import config, tools
from app.brain import Intent
from app.graph import build_graph
from app.menu import menu_store


class FakeBrain:
    def __init__(self, intents):
        self.intents = list(intents)
        self.situations = []

    def understand(self, user_input, menu, pending_offer, history):
        self.last_offer = pending_offer
        return self.intents.pop(0)

    def reply(self, situation, menu, history):
        self.situations.append(situation)
        return f"reply:{situation['situation']}"


class ScriptedRng:
    """random() returns 0.0 (fail) or 0.99 (succeed) from a script; defaults to succeed."""

    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)

    def random(self):
        return 0.0 if (self.outcomes and self.outcomes.pop(0) == "fail") else 0.99

    def choice(self, seq):
        return seq[0]


def order(dish, qty):
    return Intent(intent="order", dish_name=dish, quantity=qty)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    menu_store.reset()
    monkeypatch.setattr(config, "COOK_DELAY_SECONDS", 0)
    monkeypatch.setattr(config, "SERVE_DELAY_SECONDS", 0)
    monkeypatch.setattr(tools, "rng", ScriptedRng())


def run(graph, thread, text):
    return graph.invoke({"user_input": text}, {"configurable": {"thread_id": thread}})


def stock(name):
    return menu_store.find(name).available


def test_happy_path_serves_and_ends_session():
    brain = FakeBrain([order("Butter Chicken", 2)])
    graph = build_graph(brain)
    state = run(graph, "t", "2 butter chicken please")
    assert state["session_status"] == "ended"
    assert state["end_reason"] == "served"
    assert stock("Butter Chicken") == 8


def test_invalid_query_ends_session():
    graph = build_graph(FakeBrain([Intent(intent="invalid", dish_name=None, quantity=None)]))
    state = run(graph, "t", "what is the capital of india")
    assert state["session_status"] == "ended"
    assert state["end_reason"] == "invalid"


def test_need_info_asks_without_consuming_attempt():
    graph = build_graph(FakeBrain([Intent(intent="need_info", dish_name=None, quantity=None)]))
    state = run(graph, "t", "hi, what do you have?")
    assert state.get("session_status") != "ended"
    assert state["show_menu"] is True
    assert state.get("take_order_failures", 0) == 0


def test_dish_not_found_then_limit_after_three():
    brain = FakeBrain([order("Pizza", 1), order("Burger", 1), order("Sushi", 1)])
    graph = build_graph(brain)
    for i in range(2):
        state = run(graph, "t", "x")
        assert state["take_order_failures"] == i + 1
        assert state.get("session_status") != "ended"
        assert brain.situations[-1]["reason"] == "dish_not_found"
    state = run(graph, "t", "x")
    assert state["session_status"] == "ended"
    assert state["end_reason"] == "limit_take_order"


def test_insufficient_quantity_offer_then_yes():
    brain = FakeBrain([order("Paneer Tikka", 20), order("Paneer Tikka", 8)])
    graph = build_graph(brain)
    state = run(graph, "t", "20 paneer tikka")
    assert state["pending_offer"] == {"dish_name": "Paneer Tikka", "available": 8}
    assert brain.situations[-1]["available"] == 8
    state = run(graph, "t", "yes")
    assert brain.last_offer == {"dish_name": "Paneer Tikka", "available": 8}
    assert state["end_reason"] == "served"
    assert stock("Paneer Tikka") == 0


def test_cook_failure_returns_to_guest_and_releases_stock(monkeypatch):
    monkeypatch.setattr(tools, "rng", ScriptedRng(["fail"]))
    brain = FakeBrain([order("Dal Makhani", 3), order("Dal Makhani", 3)])
    graph = build_graph(brain)
    state = run(graph, "t", "3 dal makhani")
    assert state["cook_failures"] == 1
    assert brain.situations[-1]["situation"] == "cook_failed"
    assert stock("Dal Makhani") == 12  # released
    state = run(graph, "t", "3 dal makhani again")
    assert state["end_reason"] == "served"
    assert stock("Dal Makhani") == 9


def test_cook_limit_ends_session(monkeypatch):
    monkeypatch.setattr(tools, "rng", ScriptedRng(["fail"] * 3))
    graph = build_graph(FakeBrain([order("Garlic Naan", 1)] * 3))
    for _ in range(2):
        assert run(graph, "t", "naan").get("session_status") != "ended"
    state = run(graph, "t", "naan")
    assert state["end_reason"] == "limit_cook"
    assert stock("Garlic Naan") == 30


def test_serve_failure_recooks_automatically(monkeypatch):
    # cook ok, serve fail, cook ok, serve ok
    monkeypatch.setattr(tools, "rng", ScriptedRng(["ok", "fail", "ok", "ok"]))
    graph = build_graph(FakeBrain([order("Masala Dosa", 2)]))
    state = run(graph, "t", "2 dosa")
    assert state["serve_failures"] == 1
    assert state["end_reason"] == "served"
    assert stock("Masala Dosa") == 13


def test_serve_limit_ends_session_and_releases_stock(monkeypatch):
    monkeypatch.setattr(tools, "rng", ScriptedRng(["ok", "fail"] * 3))
    graph = build_graph(FakeBrain([order("Mango Lassi", 1)]))
    state = run(graph, "t", "lassi")
    assert state["serve_failures"] == 3
    assert state["end_reason"] == "limit_serve"
    assert stock("Mango Lassi") == 15


def test_sessions_are_isolated():
    brain = FakeBrain([order("Pizza", 1), order("Pizza", 1)])
    graph = build_graph(brain)
    run(graph, str(uuid.uuid4()), "pizza")
    state = run(graph, str(uuid.uuid4()), "pizza")
    assert state["take_order_failures"] == 1
