# spec: AS-027
"""Reconcile what we think we spent with what Meta says, before and after every paid run. No model call, no key.

Usage: python tools/reconcile.py --credits-left 145.39 --requests 421 [--grant 150]
  --credits-left  "Free credits in use" on dev.meta.ai/billing
  --requests      "Requests" on dev.meta.ai/usage (all keys, all models, the full date range), exactly as shown: 421, or 4.8k once
                  Meta rounds it (then the check is that the ledger falls inside what the rounded figure can mean, and the result says so)
Prints our account ledger (every reservation, at its maximum and at its settled cost) and our stored calls beside Meta's
figures, flags any gap, and appends one dated line to ~/.airstack/reconciliation.log (private: never committed)."""
import argparse, json, pathlib, sqlite3, sys
from datetime import datetime, timezone
from decimal import Decimal
from airstack import paths

ROOT = paths.ROOT
from airstack.account_guard import AccountGuard, account_cap

def ours():
    g = AccountGuard()
    rows = g._c.execute("SELECT state, reserved, spent FROM ledger").fetchall()
    by = {}
    for st, _, _ in rows: by[st] = by.get(st, 0) + 1
    spent = sum((Decimal(s) for _, _, s in rows if s), Decimal(0))
    calls = {}
    for db in ("airstack-market", "airstack-demo"):
        c = sqlite3.connect(f"file:{paths.DATA / (db + '.db')}?mode=ro", uri=True)
        sent = c.execute("SELECT count(*), coalesce(sum(cost),0), coalesce(sum(in_tok),0), coalesce(sum(out_tok),0) FROM calls WHERE kind != 'cached'").fetchone()
        calls[db] = {"sent": sent[0], "cost": round(float(sent[1]), 4), "in": sent[2], "out": sent[3]}
    return {"ledger_rows": len(rows), "by_state": by, "committed_at_maximum": str(g.committed()), "settled_cost": str(spent),
            "cap": str(account_cap()), "stopped": g.stopped(), "stored_calls": calls}

def shown(v):
    """Meta's request count as displayed: '421' is exact; '4.8k' means anything that rounds to it, 4,750 to 4,849."""
    v = v.strip().lower()
    if not v.endswith("k"):
        return int(v), int(v)
    d = Decimal(v[:-1]); step = Decimal(1).scaleb(d.as_tuple().exponent) * 1000
    return int(d * 1000 - step / 2), int(d * 1000 + step / 2) - 1

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--credits-left", type=Decimal, required=True); ap.add_argument("--requests", type=shown, required=True)
    ap.add_argument("--grant", type=Decimal, default=Decimal("150")); a = ap.parse_args()
    o = ours(); used = a.grant - a.credits_left
    lo, hi = a.requests
    req_gap = 0 if lo <= o["ledger_rows"] <= hi else (lo - o["ledger_rows"] if o["ledger_rows"] < lo else hi - o["ledger_rows"])
    cost_gap = Decimal(o["settled_cost"]) - used
    print(json.dumps(o, indent=1))
    meta = f"{lo}" if lo == hi else f"{lo} to {hi} (Meta rounds the count)"
    print(f"\nMeta: {meta} requests, ${used} of credits used (${a.credits_left} of ${a.grant} left)")
    print(f"requests: ledger {o['ledger_rows']} vs Meta {meta} (gap {req_gap:+d})   cost: settled ${o['settled_cost']} vs Meta ${used} (gap {cost_gap:+.2f})")
    ok = abs(req_gap) <= 2 and cost_gap >= -Decimal("0.05")
    print("RECONCILED: counts agree and we never under-count spend" if ok else "NOT RECONCILED: stop live work until the gap is explained")
    log = pathlib.Path.home() / ".airstack" / "reconciliation.log"; log.parent.mkdir(exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "meta_requests": [lo, hi], "meta_credits_left": str(a.credits_left),
                            "ledger_rows": o["ledger_rows"], "settled": o["settled_cost"], "committed_max": o["committed_at_maximum"], "ok": ok}) + "\n")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
