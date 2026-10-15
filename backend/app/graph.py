"""LangGraph workflow for one guest session.

The graph runs once per guest message. State (attempt counters, pending
offers, conversation) persists between messages via the checkpointer, keyed
by session id (`thread_id`).

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
     served  (session complete)
"""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from . import config, tools
from .brain import Brain
from .menu import menu_store

Stage = Literal["take_order", "cook", "serve"]


class OrderState(TypedDict, total=False):
    # Per-message input / output
    user_input: str
    reply: str
    show_menu: bool
    step: dict  # latest step, streamed to the UI
    # Per-session memory
    history: Annotated[list[dict], operator.add]
    take_order_failures: int
    cook_failures: int
    serve_failures: int
    pending_offer: dict | None  # quantity offered after an insufficient_quantity failure
    order: dict | None  # the order currently in the pipeline (reserved stock)
    last_failure: dict | None
    session_status: Literal["active", "ended"]
    end_reason: str | None


def _attempts(state: OrderState, stage: Stage) -> dict:
    used = state.get(f"{stage}_failures", 0)
    return {"attempts_used": used, "attempts_left": config.MAX_ATTEMPTS_PER_STAGE - used}


def build_graph(brain: Brain, checkpointer=None):
    def understand(state: OrderState):
        menu = menu_store.snapshot()
        user_input = state["user_input"]
        intent = brain.understand(user_input, menu, state.get("pending_offer"), state.get("history", []))
        update: OrderState = {
            "history": [{"role": "guest", "content": user_input}],
            "show_menu": False,
            "last_failure": None,
            "step": {"node": "understand", "status": "info", "intent": intent.intent,
                     "dish_name": intent.dish_name, "quantity": intent.quantity},
        }
        if intent.intent == "order" and intent.dish_name and intent.quantity is not None:
            update["order"] = {"dish_name": intent.dish_name, "quantity": intent.quantity}
        else:
            update["order"] = None
        if intent.intent == "invalid":
            update["end_reason"] = "invalid"
        elif update["order"] is None:
            update["last_failure"] = {"situation": "need_info"}
        return update

    def route_understand(state: OrderState):
        if state.get("end_reason") == "invalid":
            return "end_session"
        return "take_order" if state.get("order") else "respond"

    def take_order_node(state: OrderState):
        order = state["order"]
        result = tools.take_order.invoke(order)
        step = {"node": "take_order", "status": "success" if result["success"] else "failure", **result}
        if result["success"]:
            return {"order": {"dish_name": result["dish_name"], "quantity": result["quantity"]},
                    "pending_offer": None, "step": step}
        failures = state.get("take_order_failures", 0) + 1
        offer = None
        if result["reason"] == "insufficient_quantity" and result["available"] > 0:
            offer = {"dish_name": result["dish_name"], "available": result["available"]}
        return {
            "order": None,
            "take_order_failures": failures,
            "pending_offer": offer,
            "last_failure": {"situation": "take_order_failed", **result},
            "step": {**step, "attempt": failures},
        }

    def cook_node(state: OrderState):
        order = state["order"]
        result = tools.cook.invoke(order)
        step = {"node": "cook", "status": "success" if result["success"] else "failure", **result}
        if result["success"]:
            return {"step": step}
        failures = state.get("cook_failures", 0) + 1
        # The guest has to choose again, so the reserved portions go back to stock.
        menu_store.release(order["dish_name"], order["quantity"])
        return {
            "order": None,
            "cook_failures": failures,
            "last_failure": {"situation": "cook_failed", **result},
            "step": {**step, "attempt": failures},
        }

    def serve_node(state: OrderState):
        result = tools.serve.invoke(state["order"])
        step = {"node": "serve", "status": "success" if result["success"] else "failure", **result}
        if result["success"]:
            return {"step": step}
        failures = state.get("serve_failures", 0) + 1
        return {
            "serve_failures": failures,
            "last_failure": {"situation": "serve_failed", **result},
            "step": {**step, "attempt": failures},
        }

    def failure_router(stage: Stage, on_success: str, on_failure: str):
        def route(state: OrderState):
            if state["step"]["status"] == "success":
                return on_success
            if state.get(f"{stage}_failures", 0) >= config.MAX_ATTEMPTS_PER_STAGE:
                return "end_session"
            return on_failure
        return route

    def respond(state: OrderState):
        failure = state.get("last_failure") or {"situation": "need_info"}
        situation = dict(failure)
        if situation["situation"] == "take_order_failed":
            situation.update(_attempts(state, "take_order"))
        elif situation["situation"] == "cook_failed":
            situation.update(_attempts(state, "cook"))
        situation["show_menu"] = True
        text = brain.reply(situation, menu_store.snapshot(), state.get("history", []))
        return {"reply": text, "show_menu": True, "history": [{"role": "host", "content": text}],
                "step": {"node": "respond", "status": "info"}}

    def served(state: OrderState):
        situation = {"situation": "served", **state["order"]}
        text = brain.reply(situation, menu_store.snapshot(), state.get("history", []))
        return {"reply": text, "show_menu": False, "session_status": "ended", "end_reason": "served",
                "history": [{"role": "host", "content": text}],
                "step": {"node": "served", "status": "success", **state["order"]}}

    def end_session(state: OrderState):
        if state.get("end_reason") == "invalid":
            situation = {"situation": "invalid"}
            reason = "invalid"
        else:
            stage = next(s for s in ("take_order", "cook", "serve")
                         if state.get(f"{s}_failures", 0) >= config.MAX_ATTEMPTS_PER_STAGE)
            situation = {"situation": "limit_reached", "stage": stage,
                         "max_attempts": config.MAX_ATTEMPTS_PER_STAGE, "last_failure": state.get("last_failure")}
            reason = f"limit_{stage}"
            order = state.get("order")
            if order:  # serve limit: release the portions that never reached the table
                menu_store.release(order["dish_name"], order["quantity"])
        text = brain.reply(situation, menu_store.snapshot(), state.get("history", []))
        return {"reply": text, "show_menu": False, "session_status": "ended", "end_reason": reason, "order": None,
                "history": [{"role": "host", "content": text}],
                "step": {"node": "end_session", "status": "ended", "reason": reason}}

    g = StateGraph(OrderState)
    g.add_node("understand", understand)
    g.add_node("take_order", take_order_node)
    g.add_node("cook", cook_node)
    g.add_node("serve", serve_node)
    g.add_node("respond", respond)
    g.add_node("served", served)
    g.add_node("end_session", end_session)

    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", route_understand, ["take_order", "respond", "end_session"])
    g.add_conditional_edges("take_order", failure_router("take_order", "cook", "respond"),
                            ["cook", "respond", "end_session"])
    g.add_conditional_edges("cook", failure_router("cook", "serve", "respond"), ["serve", "respond", "end_session"])
    g.add_conditional_edges("serve", failure_router("serve", "served", "cook"), ["served", "cook", "end_session"])
    g.add_edge("respond", END)
    g.add_edge("served", END)
    g.add_edge("end_session", END)

    return g.compile(checkpointer=checkpointer or InMemorySaver())
