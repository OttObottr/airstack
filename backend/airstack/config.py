# spec: AS-020 AS-027 AS-055 AS-206 AS-350
"""Model, pricing and request limits used by the research pipeline."""
import os
from decimal import Decimal

MODEL = "muse-spark-1.3"
BASE_URL = "https://api.meta.ai/v1"                      # Responses API, called by the standard-library client (per spec v3)
# JOB = one bounded research or reassessment task, including every model turn, tool call and retry it needs.
JOB_BUDGET = Decimal(os.environ.get("JOB_BUDGET_USD", os.environ.get("RUN_BUDGET_USD", "0.50")))
DAILY_BUDGET = Decimal(os.environ.get("DAILY_BUDGET_USD", "10"))
def _positive(name):
    try:
        value = Decimal(os.environ.get(name, ""))
    except Exception:
        return Decimal(0)
    return value if value.is_finite() and value > 0 else Decimal(0)

# This secondary database budget is useful in fixtures and local runs. The account guard remains the fail-closed authorization boundary;
# when its private ceiling is present, this lower-level budget cannot exceed it.
_PRIVATE_CEILING = _positive("AIRSTACK_HARD_CEILING_USD")
TOTAL_BUDGET = _positive("TOTAL_BUDGET_USD") or DAILY_BUDGET * 10
if _PRIVATE_CEILING:
    TOTAL_BUDGET = min(TOTAL_BUDGET, _PRIVATE_CEILING)
TOOL_MAX_CALLS = 8                                        # Spark calls per new tool
TOOL_MAX_SEARCHES = 4                                     # web searches per new tool (a search also counts as a call)
MAX_STACK_TOOLS = 25
# ---- bounded request envelope: what one call may consume at most ----
MAX_INPUT_CHARS = 24_000            # payload + system prompt; larger inputs are refused before the call
TOKENS_PER_BYTE_CEILING = 2         # the bound is per UTF-8 byte, not per character: hive.com's dot-art read as 32,334 tokens for 28,587 bytes (1.13 a byte)
INPUT_TOKEN_OVERHEAD = 400          # framing, schema and tool definitions
MAX_OUTPUT_TOKENS = 4096            # sent as max_output_tokens; Meta counts reasoning tokens inside it (dev.meta.ai/docs/reasoning), and 2048 left no room for the answer
REASONING_EFFORT = "low"            # sent as reasoning.effort; "none" is rejected by Muse Spark (HTTP 400). Reasoning tokens bill at the output rate.
SEARCH_QUERY_ALLOWANCE = 10         # Cost estimation only. Live paid web search is disabled because this is not a provider-guaranteed bound.
# Muse Spark 1.3 STANDARD-mode list prices (dev.meta.ai/docs/pricing-rate-limits, checked 2026-11-03), dollars.
# Environment values may raise a reservation after a price change, never lower the reviewed safety floor.
def _rate(name, floor):
    return max(floor, _positive(name))

PRICE_IN_PER_MTOK = _rate("SPARK_PRICE_IN_PER_MTOK", Decimal("1.25"))
PRICE_OUT_PER_MTOK = _rate("SPARK_PRICE_OUT_PER_MTOK", Decimal("4.25"))
PRICE_PER_SEARCH = _rate("SPARK_PRICE_PER_SEARCH", Decimal("0.0025"))
WONDER_MODEL = "muse-wonder-1.0"                          # Meta's most capable model, Standard mode only on pay-as-you-go: used once a day for the brief
ROLE_MODELS = {"brief": WONDER_MODEL}
MODEL_PRICES = {MODEL: (PRICE_IN_PER_MTOK, PRICE_OUT_PER_MTOK),
                WONDER_MODEL: (Decimal("4.00"), Decimal("20.00"))}                                            # dollars per million tokens: input, output
FRESH_DAYS = 14                                           # unchanged inputs can skip inference, but not forever
MIN_CONFIDENCE = 0.7
VERDICT_WORDS = ("BUILD", "BUY", "KEEP", "RETIRE")
