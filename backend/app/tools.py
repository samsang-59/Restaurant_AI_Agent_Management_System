"""The three restaurant tools: take_order, cook and serve.

Each returns a dict with `success: bool` plus details the graph and the LLM
use to decide what happens next. Cook and serve failures are a random
simulation controlled by COOK_FAILURE_RATE / SERVE_FAILURE_RATE.
"""

import random
import time

from langchain_core.tools import tool

from . import config
from .menu import menu_store

# Swappable for deterministic tests.
rng = random.Random()

COOK_FAILURE_REASONS = [
    "the dish got burnt on the tawa",
    "a key ingredient turned out to be spoiled",
    "the tandoor lost heat midway through cooking",
    "the gravy split and could not be rescued",
]

SERVE_FAILURE_REASONS = [
    "the waiter slipped and the plate fell",
    "the plate cracked on the way to the table",
    "the dish went cold while waiting at the pass",
]


@tool
def take_order(dish_name: str, quantity: int) -> dict:
    """Check that `dish_name` is on the menu and `quantity` portions can be served.

    On success the portions are reserved from stock.
    """
    item = menu_store.find(dish_name)
    if item is None:
        return {"success": False, "reason": "dish_not_found", "dish_name": dish_name, "quantity": quantity}
    if quantity < 1:
        return {"success": False, "reason": "invalid_quantity", "dish_name": item.name, "quantity": quantity}
    if not menu_store.reserve(item.name, quantity):
        return {
            "success": False,
            "reason": "insufficient_quantity",
            "dish_name": item.name,
            "quantity": quantity,
            "available": menu_store.find(item.name).available,
        }
    return {"success": True, "dish_name": item.name, "quantity": quantity, "price": item.price * quantity}


@tool
def cook(dish_name: str, quantity: int) -> dict:
    """Send the order to the kitchen and cook `quantity` portions of `dish_name`."""
    time.sleep(config.COOK_DELAY_SECONDS)
    if rng.random() < config.COOK_FAILURE_RATE:
        return {"success": False, "reason": rng.choice(COOK_FAILURE_REASONS), "dish_name": dish_name, "quantity": quantity}
    return {"success": True, "dish_name": dish_name, "quantity": quantity}


@tool
def serve(dish_name: str, quantity: int) -> dict:
    """Carry the cooked `dish_name` to the guest's table."""
    time.sleep(config.SERVE_DELAY_SECONDS)
    if rng.random() < config.SERVE_FAILURE_RATE:
        return {"success": False, "reason": rng.choice(SERVE_FAILURE_REASONS), "dish_name": dish_name, "quantity": quantity}
    return {"success": True, "dish_name": dish_name, "quantity": quantity}
