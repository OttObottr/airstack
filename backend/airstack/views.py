# spec: AS-012 AS-013 AS-030 AS-040 AS-044 AS-062 AS-072 AS-130 AS-294
"""Read-only views for the local MCP server. This module must never import Spark."""
from .evaluate import evaluate, hold_reason, is_rules_hold
from .store import utcnow
PUBLIC = "public"     # public routes and MCP only ever read records explicitly marked public
REFERENCE_SCOPE = ("Reference scenario: these verdicts are for example seats, not for you. "
                   "Call review_stack with your own requirements to get yours.")
REPLAY_LABEL = "Historical replay: reconstructed from the verdict revisions and evidence AirStack recorded, not from memory"

def _human(c):
    if c["kind"] in ("capability_gain", "entity_fact"):
        return f"recheck when {c['text']}"
    state = "becomes unmet" if c["covered_at_issue"] else "becomes met"
    return f"recheck when '{c['text']}' {state}"

def verdict_view(v, status=None, now=None):
    st = status or v.status
    if st == "CURRENT" and now and v.fresh_until < now:
        st = "OVERDUE"                       # past its recheck deadline: not current advice, even if no worker has run
    hold = is_rules_hold(v)
    out = {"tool": v.entity_id, "context": v.context, "action": v.action, "status": st,
            "reason": hold_reason(v.action, v.uncovered) if hold else v.reason,
            "issued_at": v.issued_at, "last_verified_at": v.last_verified_at, "fresh_until": v.fresh_until,
            "depends_on": {k: (h[:8] if h else None) for k, h in v.depends_on.items()},
            "recheck_if": [_human(c) for c in v.expires_when], "uncovered": v.uncovered,
            "evidence": [{k: e.get(k) for k in ("ref", "key", "url", "ts", "ts_kind", "observed_at", "effective_at", "hash", "kind")} for e in v.evidence],
            "counter_evidence_checked": v.counter_checked, "supersedes": v.supersedes_id, "judge_output": v.judge_output,
            "basis": ("provisional hold: the alternative fails " + "; ".join(v.uncovered) + ". The incumbent's own coverage is not separately verified.")
                     if v.action == "KEEP" and v.requirements else None,
            "judged_by": {"model": ("fixture (no model call)" if v.call_ids and all(str(c).startswith("fake-") for c in v.call_ids) else "muse-spark-1.3"),
                          "call_ids": v.call_ids, "kind": "re-verified by rules after a 'not material' classification (no judge)" if hold else "judged"}}
    if hold and v.reason != out["reason"]:
        out["stored_reason"] = v.reason                  # what the row recorded; carried over from an older revision, kept for the audit trail
    return out

def get_verdict(store, tool, seat=None, as_of=None, now=None):
    now = now or utcnow()
    ctxs = [f"seat:{seat}"] if seat else sorted({v.context for v in store.verdicts(tool, visibility=PUBLIC)})
    if as_of:
        out = []
        for c in ctxs:
            v, st = store.verdict_as_of(tool, c, as_of + "T23:59:59Z", visibility=PUBLIC)
            if v:
                out.append(verdict_view(v, st, now=as_of + "T23:59:59Z"))
        return {"tool": tool, "replay": True, "label": REPLAY_LABEL, "as_of": as_of, "verdicts": out}
    out = []
    for c in ctxs:
        live = [v for v in store.verdicts(tool, c, visibility=PUBLIC) if v.status in ("CURRENT", "LAPSED")]
        if live:
            out.append(verdict_view(live[-1], now=now))
    res = {"tool": tool, "replay": False, "verdicts": out}
    if not seat:
        res["scope"] = REFERENCE_SCOPE
    return res

def get_evidence(store, tool):
    return {"tool": tool, "facts": [{"ref": f"f{f.id}", "key": f.key, "value": f.value, "url": f.url, "source": f.source,
                                     "source_ts": f.source_ts, "observed_at": f.observed_at, "hash": f.value_hash[:8]}
                                    for f in store.facts_for(tool)]}

def changes_since(store, since):
    ts = since if "T" in since else since + "T00:00:00Z"
    facts = store.facts_since(ts)
    lapsed = [verdict_view(v) for v in store.verdicts(visibility=PUBLIC) if (v.lapsed_at and v.lapsed_at > ts) or (v.superseded_at and v.superseded_at > ts)]
    return {"since": ts, "facts": [{"ref": f"f{f.id}", "key": f.key, "url": f.url, "observed_at": f.observed_at, "hash": f.value_hash[:8]} for f in facts],
            "verdict_changes": lapsed}

def get_entity(store, tool):
    e = store.entity(tool)
    return e or None

def review_stack(store, items, now=None):
    out = []
    for it in items:
        if it.get("requirements"):
            ev = evaluate(store, it["tool"], it["requirements"], it.get("entitlements", ()), now=now or utcnow())
            out.append({"tool": it["tool"], "seat": it.get("seat"), "computed": True, "action": ev.action or "INSUFFICIENT_EVIDENCE", "uncovered": ev.uncovered, "gates": ev.gates,
                        "evidence": [{k: e[k] for k in ("ref", "key", "url", "ts", "hash")} for e in ev.evidence]})
        else:
            out.append({"tool": it["tool"], "seat": it.get("seat"), "computed": False, **get_verdict(store, it["tool"], it.get("seat"), now=now)})
    return out
