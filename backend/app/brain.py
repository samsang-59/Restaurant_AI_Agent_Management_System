"""The LLM side of the agent: understanding the guest and writing replies.

`Brain` is the interface the graph depends on. `OpenAIBrain` implements it with
OpenAI through langchain-openai; tests substitute a scripted fake.
"""

import json
from typing import Literal, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from . import config
from .menu import RESTAURANT_NAME


class Intent(BaseModel):
    intent: Literal["order", "need_info", "invalid"] = Field(
        description=(
            "order: the guest wants a specific dish in a specific quantity (including saying yes to an "
            "offered available quantity). need_info: restaurant-related but no complete order can be placed "
            "yet (greeting, asking for the menu, declining an offer, dish or quantity missing or ambiguous). "
            "invalid: unrelated to ordering food at this restaurant."
        )
    )
    dish_name: str | None = Field(
        description="Exact menu name if the guest clearly means a menu dish, otherwise the dish as the guest wrote it. Null unless intent is order.",
    )
    quantity: int | None = Field(description="Number of portions. Null unless intent is order.")


class Brain(Protocol):
    def understand(self, user_input: str, menu: list[dict], pending_offer: dict | None, history: list[dict]) -> Intent: ...

    def reply(self, situation: dict, menu: list[dict], history: list[dict]) -> str: ...


UNDERSTAND_SYSTEM = f"""You are the order-intake brain of {RESTAURANT_NAME}, an Indian restaurant.
Classify the guest's latest message and extract the order arguments for the take_order tool.

Rules:
- Exactly one dish per order. If the guest asks for several dishes, use need_info.
- If the guest refers to a menu dish with a casual or misspelled name and only one menu dish fits, use that exact menu name.
- If the dish could match several menu dishes, or the quantity is not stated, use need_info.
- If the guest names a dish that is not on the menu, still use order with the dish as they wrote it; the take_order tool decides.
- If there is a pending offer and the guest agrees to it (e.g. "yes", "ok, fine"), use order with the offered dish and the offered available quantity. If they decline it without a new order, use need_info.
- Anything not about ordering food here (general knowledge, coding, chit-chat unrelated to the restaurant) is invalid."""

REPLY_SYSTEM = f"""You are the warm, concise host of {RESTAURANT_NAME}, an Indian restaurant, chatting with a guest.
Write the next message to the guest based on the SITUATION JSON. Use only facts from SITUATION, MENU and the conversation; never invent dishes, prices, stock or reasons.
Keep it to 1-4 short sentences. Plain text, no markdown headings or tables.
When SITUATION.show_menu is true, the full menu with live availability is displayed right below your message, so refer to it instead of listing every dish.
Situations:
- need_info: help the guest finish their order (one dish and a quantity).
- take_order_failed: reason dish_not_found -> say the dish isn't on the menu and ask them to choose a dish and quantity from the menu. reason insufficient_quantity -> say only `available` portions are left; ask them to reply yes to take that many, or no / choose something else. If available is 0, say it is sold out. reason invalid_quantity -> ask for a valid quantity. Mention attempts_left.
- cook_failed: apologise that the kitchen had a problem (give the reason), and ask them to choose a dish and quantity again. Mention attempts_left.
- served: tell them their food has been served, wish them a good meal, and say the order is complete.
- limit_reached: apologise that the order could not be completed after the maximum attempts at the given stage, and say a fresh session is starting.
- invalid: politely say you can only help with food orders at this restaurant and that this session is ending."""


class OpenAIBrain:
    def __init__(self):
        kwargs = {"model": config.OPENAI_MODEL}
        if config.OPENAI_REASONING_EFFORT:
            kwargs["reasoning_effort"] = config.OPENAI_REASONING_EFFORT
        llm = ChatOpenAI(**kwargs)
        self._llm = llm
        # json_schema uses OpenAI structured outputs, so the reply always matches Intent.
        self._intent_llm = llm.with_structured_output(Intent, method="json_schema", strict=True)

    def understand(self, user_input, menu, pending_offer, history):
        context = {
            "menu": [{"name": m["name"], "category": m["category"]} for m in menu],
            "pending_offer": pending_offer,
            "recent_conversation": history[-10:],
            "latest_guest_message": user_input,
        }
        return self._intent_llm.invoke(
            [SystemMessage(UNDERSTAND_SYSTEM), HumanMessage(json.dumps(context, ensure_ascii=False))]
        )

    def reply(self, situation, menu, history):
        context = {"SITUATION": situation, "MENU": menu, "recent_conversation": history[-10:]}
        response = self._llm.invoke([SystemMessage(REPLY_SYSTEM), HumanMessage(json.dumps(context, ensure_ascii=False))])
        return response.text.strip()
