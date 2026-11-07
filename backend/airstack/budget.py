# spec: AS-020 AS-027 AS-055
"""Budget enforcement for model calls.
Every call reserves its maximum possible cost inside a durable, uniquely identified job.
Committed money = settled + in-flight + uncertain, checked atomically at the job, day and lifetime level."""
import json
from decimal import Decimal, ROUND_UP
from .config import (JOB_BUDGET, DAILY_BUDGET, TOTAL_BUDGET, TOOL_MAX_CALLS, TOOL_MAX_SEARCHES, MAX_INPUT_CHARS,
                     TOKENS_PER_BYTE_CEILING, INPUT_TOKEN_OVERHEAD, MAX_OUTPUT_TOKENS, SEARCH_QUERY_ALLOWANCE,
                     PRICE_PER_SEARCH, MODEL, MODEL_PRICES)

class BudgetExceeded(Exception):
    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason

def max_cost(role, payload, system_prompt="", model=MODEL):
    """Worst-case dollars for one call on `model`: every input token, the full output allowance, and (for search) the query allowance.
    Raises if the input is larger than the envelope allows, or if the model has no known price."""
    text = system_prompt + json.dumps(payload, ensure_ascii=False)
    chars = len(text)
    if chars > MAX_INPUT_CHARS:
        raise BudgetExceeded("input_too_large", f"{chars} characters > {MAX_INPUT_CHARS}")
    if model not in MODEL_PRICES:
        raise BudgetExceeded("unknown_model", f"no reviewed price for {model!r}")
    rate_in, rate_out = MODEL_PRICES[model]
    tokens_in = len(text.encode()) * TOKENS_PER_BYTE_CEILING + INPUT_TOKEN_OVERHEAD   # symbols and non-Latin scripts cost more than a token a character
    cost = (Decimal(tokens_in) * rate_in + Decimal(MAX_OUTPUT_TOKENS) * rate_out) / Decimal(1_000_000)
    if role == "search":
        cost += Decimal(SEARCH_QUERY_ALLOWANCE) * PRICE_PER_SEARCH
    return cost.quantize(Decimal("0.000001"), rounding=ROUND_UP)

class BudgetGuard:
    def __init__(self, store, now_fn, *, job_cap=None, run_cap=None, day_cap=DAILY_BUDGET, total_cap=TOTAL_BUDGET,
                 tool_calls=TOOL_MAX_CALLS, tool_searches=TOOL_MAX_SEARCHES):
        self.store, self.now_fn = store, now_fn
        cap = job_cap if job_cap is not None else run_cap
        self.job_cap = Decimal(JOB_BUDGET if cap is None else cap)        # an explicit zero stays zero
        self.day_cap, self.total_cap = Decimal(day_cap), Decimal(total_cap)
        self.tool_calls, self.tool_searches = tool_calls, tool_searches
        self._job = {}
    def begin_tool(self, tool, purpose="job", dedupe_key=None):
        """Open a durable job with an optional idempotency key."""
        self.end_tool(tool)
        jid = self.store.open_job(tool=tool, purpose=purpose, now=self.now_fn(), dedupe_key=dedupe_key)
        self._job[tool] = {"id": jid, "calls": 0, "searches": 0}
        return jid
    def end_tool(self, tool):
        j = self._job.pop(tool, None)
        if j:
            self.store.close_job(j["id"], self.now_fn())
    def job_id(self, tool):
        return self._job.get(tool, {}).get("id")
    @property
    def run_spent(self):
        return sum((self.store._committed(job_id=j["id"]) for j in self._job.values()), Decimal(0))
    def check(self, tool, kind, est):
        """Reserve `est`, the call's maximum cost, and return the reservation id."""
        est = Decimal(est)
        if tool not in self._job:
            self.begin_tool(tool)
        j = self._job[tool]
        if j["calls"] + 1 > self.tool_calls:
            raise BudgetExceeded("tool_calls", f"{tool} already used {j['calls']} of {self.tool_calls} calls")
        if kind == "search" and j["searches"] + 1 > self.tool_searches:
            raise BudgetExceeded("tool_searches", f"{tool} already used {j['searches']} of {self.tool_searches} searches")
        rid = self.store.reserve(tool=tool, est=est, now=self.now_fn(), day_cap=self.day_cap, total_cap=self.total_cap,
                                 job_id=j["id"], job_cap=self.job_cap)
        j["calls"] += 1
        if kind == "search":
            j["searches"] += 1
        return rid
