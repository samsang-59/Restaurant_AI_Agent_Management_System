"""Runtime configuration, read from environment variables (or a .env file)."""

import os

from dotenv import load_dotenv

load_dotenv()


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
# Reasoning effort for the LLM calls. Intent extraction and short replies are
# simple tasks, so "low" keeps latency and cost down.
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "low")

# Each stage may fail at most this many times in one session before the
# session is ended and a fresh one is started.
MAX_ATTEMPTS_PER_STAGE = int(os.getenv("MAX_ATTEMPTS_PER_STAGE", 3))

# Random-simulation failure probabilities (0.0 - 1.0) for the kitchen and waiter.
COOK_FAILURE_RATE = _float("COOK_FAILURE_RATE", 0.2)
SERVE_FAILURE_RATE = _float("SERVE_FAILURE_RATE", 0.2)

# Artificial delays (seconds) so the UI can show the agent "working".
COOK_DELAY_SECONDS = _float("COOK_DELAY_SECONDS", 1.5)
SERVE_DELAY_SECONDS = _float("SERVE_DELAY_SECONDS", 1.0)

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
