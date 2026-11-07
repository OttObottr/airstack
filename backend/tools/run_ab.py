# spec: AS-055 AS-306
"""The A/B: the SAME Muse Spark agent and question, three runs without AirStack and three runs where it may call AirStack's
get_verdict (the real MCP tool, answered from data/airstack-demo.db at the real clock). Every answer is saved verbatim.

Resumable and append-only: runs already in data/ab-runs.json are never repeated or discarded; only missing runs are made.
Every call goes through the account ledger (reserve the maximum first). Usage: ../.venv/bin/python tools/run_ab.py --live"""
import json, sys
from datetime import datetime, timezone
from airstack.mcp_server import McpServer, DESCRIPTIONS
from airstack.spark import final_text
from airstack.store import Store
from airstack import paths

ROOT = paths.ROOT
OUT = paths.DATA / "ab-runs.json"
# A second, neutral case (review: the first question told the model about Meet's feature, and its right answer was Keep either way).
# The question never names the competing feature; the right answer today (4 Nov 2026) is Retire.
CASES = {"standard": {"out": paths.DATA / "ab-runs-2.json", "seat": "A",
                      "question": ("Our team holds its meetings in person, in English, and records them on Android phones. Our Google Workspace plan is "
                                   "Business Standard. We pay for Fireflies to take notes in those in-person meetings. Should we keep paying for "
                                   "Fireflies, or retire it? (Our AirStack seat id is A.)")}}
DB = paths.DEMO_DB
RUNS = 3
SYSTEM = "You advise teams on which software subscriptions to keep paying for. Answer KEEP or RETIRE, with one sentence of reason."
QUESTION = ("Our team holds its meetings in person, in English, and records them on Android phones. Our Google Workspace plan is Business Starter. "
            "We pay for Fireflies to take notes in those in-person meetings. Google Meet now has a 'Take notes for me' feature for in-person meetings. "
            "Should we keep paying for Fireflies, or retire it? (Our AirStack seat id is B.)")
ANSWER = {"type": "object", "additionalProperties": False, "required": ["action", "reason"],
          "properties": {"action": {"type": "string", "enum": ["KEEP", "RETIRE"]}, "reason": {"type": "string"}}}
TOOL = {"type": "function", "name": "get_verdict", "description": DESCRIPTIONS["get_verdict"], "strict": True,
        "parameters": {"type": "object", "additionalProperties": False, "required": ["tool", "seat"],
                       "properties": {"tool": {"type": "string", "description": "lowercase tool key, e.g. fireflies"},
                                      "seat": {"type": "string", "description": "the AirStack seat id"}}}}
FORMAT = {"format": {"type": "json_schema", "name": "answer", "schema": ANSWER, "strict": True}}
now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load(path=OUT, question=QUESTION):
    return json.loads(path.read_text()) if path.exists() else {"question": question, "system": SYSTEM, "model": "muse-spark-1.3", "runs": []}

def save(data, path=OUT):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))           # written after EVERY run: nothing paid for is ever lost

def _rec(r, cost, tin, tout, ms):
    return {"id": getattr(r, "id", ""), "tokens_in": tin, "tokens_out": tout, "ms": ms, "cost": str(cost)}

def without(spark, question=QUESTION):
    r, *u = spark.respond("ab_without", input=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}], text=FORMAT)
    ans = json.loads(final_text(r, list(r.output or [])))
    return {"side": "without", "answer": ans, "tool_calls": [], "calls": [_rec(r, *u)]}

MAX_ROUNDS = 3                                                               # model calls per "with" run, at most

def _ask(mcp, args):
    try:
        out = mcp.call_tool("get_verdict", args)
    except Exception as e:                                                    # a bad argument is the agent's mistake: show it the error
        out = {"error": f"{type(e).__name__}: {e}"}
    v = (out.get("verdicts") or [{}])[0] if isinstance(out, dict) else {}
    seen = {"arguments": args, "verdict": {k: v.get(k) for k in ("action", "status", "issued_at", "last_verified_at")} if v else None,
            "evidence_urls": [e["url"] for e in v.get("evidence", [])] if v else [], "error": out.get("error") if isinstance(out, dict) else None}
    return out, seen

def with_airstack(spark, mcp, question=QUESTION):
    """Meta's Responses API accepts only tool_choice "auto", so the agent decides; we answer every get_verdict it asks for, up to MAX_ROUNDS."""
    items = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    calls, seen = [], []
    for _ in range(MAX_ROUNDS):
        r, *u = spark.respond("ab_with", input=items, tools=[TOOL], tool_choice="auto", text=FORMAT)
        calls.append(_rec(r, *u))
        fcs = [i for i in (r.output or []) if getattr(i, "type", "") == "function_call"]
        if not fcs:
            return {"side": "with", "answer": json.loads(final_text(r, list(r.output or []))), "tool_calls": seen, "calls": calls}
        for fc in fcs:
            out, rec = _ask(mcp, json.loads(fc.arguments)); seen.append(rec)
            items += [{"type": "function_call", "call_id": fc.call_id, "name": fc.name, "arguments": fc.arguments},
                      {"type": "function_call_output", "call_id": fc.call_id, "output": json.dumps(out)}]
    return {"side": "with", "answer": None, "tool_calls": seen, "calls": calls, "note": f"no final answer within {MAX_ROUNDS} model calls"}

def main(spark, store, path=OUT, runs=RUNS, question=QUESTION):
    data = load(path, question)
    mcp = McpServer(store)
    for side, fn in (("without", lambda: without(spark, question)), ("with", lambda: with_airstack(spark, mcp, question))):
        while sum(1 for x in data["runs"] if x["side"] == side) < runs:     # resume: only the missing runs are made
            run = fn()
            run.update(n=sum(1 for x in data["runs"] if x["side"] == side) + 1, at=now())
            data["runs"].append(run); save(data, path)
    data["spend"] = str(sum(float(c["cost"]) for x in data["runs"] for c in x["calls"]))
    save(data, path)
    return data

if __name__ == "__main__":
    if "--live" not in sys.argv:
        sys.exit("real Muse calls: pass --live (needs MODEL_API_KEY in ../.env; every call is reserved in the account ledger first)")
    import preflight; preflight.load_env(ROOT / ".env")
    from airstack.spark import LiveSpark
    case = next((CASES[a.split("=", 1)[1]] for a in sys.argv if a.startswith("--case=")), None)
    d = main(LiveSpark(), Store(str(DB)), path=case["out"], question=case["question"]) if case else main(LiveSpark(), Store(str(DB)))
    for x in d["runs"]:
        print(x["side"], x["n"], x["answer"]["action"], "| tool:", [t["verdict"] for t in x["tool_calls"]] or "-", "|", x["answer"]["reason"][:150])
    print("spend", d["spend"])
