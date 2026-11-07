# spec: AS-012 AS-030 AS-032 AS-040 AS-044
"""One evaluate() for public verdicts, seats and erosion. Evidence decides; models only explain."""
from dataclasses import dataclass, field

OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "includes": lambda a, b: isinstance(a, (list, tuple, str)) and b in a,
    "gte": lambda a, b: isinstance(a, (int, float)) and not isinstance(a, bool) and a >= b,
}

def requirement_covered(req, facts, entitlements=(), now=None):
    return requirement_status(req, facts, entitlements, now) == "pass"

def requirement_status(req, facts, entitlements=(), now=None):
    """pass: the evidence says yes. fail: the evidence says no. unknown: no fact yet, or not yet effective.
    An entitlement requirement needs the SEAT to hold it: a product's eligibility list is not ownership."""
    if req.get("entitlement") and req["entitlement"] not in entitlements:
        return "fail"
    status = "pass"
    for c in req.get("all") or []:
        f = facts.get(c["key"])
        if f is None or (now and f.effective_at and f.effective_at > now):
            status = "unknown"
        elif not OPS[c["op"]](f.value, c["value"]):
            return "fail"
    return status

def evidence_entry(f):
    kind = "web_search" if f.source == "web_search" else "fact"
    return {"fact_id": f.id, "ref": f"f{f.id}", "key": f.key, "url": f.url, "ts": f.source_ts or f.observed_at,
            "ts_kind": "source" if f.source_ts else "fetched", "observed_at": f.observed_at, "effective_at": f.effective_at,
            "hash": f.value_hash[:8], "kind": kind}

@dataclass
class Evaluation:
    action: str
    uncovered: list
    evidence: list
    depends_on: dict
    expires_when: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    basis: str = ""

def evaluate(store, tool, requirements, entitlements=(), *, as_of=None, now=None, watch=(), extra_evidence=(), default_action="KEEP"):
    """RETIRE only when evidence covers EVERY declared requirement ; else KEEP + the uncovered list."""
    facts = store.latest_facts(as_of)
    evidence, seen, uncovered, conds, deps, gates = [], set(), [], [], {}, []
    for req in requirements:
        status = requirement_status(req, facts, entitlements, now or as_of)
        gates.append({"id": req["id"], "text": req["text"], "status": status})
        ok = status == "pass"
        if not ok:
            uncovered.append(req["text"])
        for c in req.get("all") or []:
            f = facts.get(c["key"])
            deps[c["key"]] = f.value_hash if f else None      # absence is a dependency too (hash None)
            if f and f.id not in seen:
                evidence.append(evidence_entry(f)); seen.add(f.id)
        conds.append({"kind": "requirement", "id": req["id"], "text": req["text"], "all": req.get("all"),
                      "entitlement": req.get("entitlement"), "covered_at_issue": ok})
    conds.extend(dict(w) for w in watch)
    for e in extra_evidence:
        if e["fact_id"] not in seen:
            evidence.append(e); seen.add(e["fact_id"])
    statuses = {g["status"] for g in gates}
    if not requirements:
        action, uncovered = default_action, []
    elif "fail" in statuses:
        action = "KEEP"                       # decisive: the evidence says the alternative fails a requirement
    elif "unknown" in statuses:
        action = None                         # insufficient evidence: no new verdict may be published
        if not uncovered:
            uncovered = ["evidence for every requirement"]
    else:
        action = "RETIRE"
    basis = ""
    if action == "KEEP" and requirements:
        basis = "provisional hold: the alternative fails " + "; ".join(g["text"] for g in gates if g["status"] == "fail") + \
                ". The incumbent's own coverage is not separately verified."
    return Evaluation(action, uncovered, evidence, deps, conds, gates, basis)


def hold_reason(action, uncovered):
    """The reason a re-verified (unchanged) verdict carries, derived from the rules at re-check time. Never the old text: the facts that
    reason described may have changed (that is why the verdict lapsed in the first place)."""
    if uncovered:
        return f"Re-verified {action}: still not covered: " + "; ".join(uncovered) + "."
    return f"Re-verified {action}: every declared requirement is covered."

def is_rules_hold(v):
    """A verdict re-issued by the rules after a 'not material' classification: no judge ran on it."""
    return v.supersedes_id is not None and v.judge_output is None and not v.counter_checked
