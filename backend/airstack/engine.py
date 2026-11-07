# spec: AS-012 AS-030 AS-032 AS-040 AS-044 AS-134 AS-232
"""Lifecycle: ingest facts -> LAPSE matching verdicts FIRST -> only then ask Spark to re-judge.
A verdict lapses on STRUCTURED invalidation conditions matched against incoming facts (including facts it never saw before),
not merely because an existing dependency's hash moved."""
import hashlib, json
from dataclasses import dataclass, field
from .budget import BudgetExceeded
from .config import MIN_CONFIDENCE
from .evaluate import evaluate, requirement_covered, evidence_entry, hold_reason
from .publication import uncitable
from .store import value_hash

@dataclass(frozen=True)
class Obs:
    entity_id: str
    metric: str
    value: object
    source: str
    url: str
    source_ts: object = None
    effective_at: object = None

@dataclass
class Outcome:
    kind: str                 # reissued | weak | failed
    detail: str = ""
    new_id: object = None

@dataclass
class SyncReport:
    changed: list = field(default_factory=list)
    lapsed: list = field(default_factory=list)
    rejudged: list = field(default_factory=list)      # (old_id, new_id)
    still_lapsed: list = field(default_factory=list)  # (id, why)
    failed: list = field(default_factory=list)

def _sha8(s):
    return hashlib.sha256(s.encode()).hexdigest()[:8]

def append_counter(store, tool, r, now):
    """A web-search result becomes a fact once: same URL and same content is never appended twice."""
    key, value = f"{tool}.counter.{_sha8(r['url'])}", {"title": r["title"], "snippet": r["snippet"]}
    latest = store.latest_fact(key)
    if latest and latest.value_hash == value_hash(key, value):
        return latest
    return store.append_fact(entity_id=tool, metric=f"counter.{_sha8(r['url'])}", value=value, source="web_search",
                             url=r["url"], source_ts=r.get("published") or None, observed_at=now)

def ingest(store, observations, now):
    """An observation's identity is its source, value and timestamps, not the value alone (review C03, X02).
    Returns (changed, observed): `changed` holds facts whose value or applicability moved, the only ones that may cost work.
    - new value: appended and changed
    - same value, corrected effective time: appended and changed (applicability moved); "not stated" never erases a known date
    - same value from another source: appended as corroboration, NOT changed (no lapse, no model call)
    - identical re-poll: nothing appended"""
    changed, observed = [], set()
    for o in observations:
        key = f"{o.entity_id}.{o.metric}"
        observed.add(key)
        store.touch_check(key, now)
        latest = store.latest_fact(key)
        append = lambda: store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url,
                                           source_ts=o.source_ts, observed_at=now, effective_at=o.effective_at)
        if latest is None or latest.value_hash != value_hash(key, o.value):
            changed.append(append())
        elif o.effective_at is not None and o.effective_at != latest.effective_at:
            changed.append(append())
        elif not any(f.metric == o.metric and f.url == o.url and f.value_hash == latest.value_hash for f in store.facts_for(o.entity_id)):
            append()                                                         # corroboration from a new source: kept, not a change
    return changed, observed

def _gain(cond, f):
    scope = cond.get("scope", "*")
    return f.metric == cond["metric"] and f.value == cond["value"] and (scope == "*" or f.entity_id in scope)

def _entity_fact(cond, f):
    return f.entity_id == cond["entity"] and not f.metric.startswith("counter.")

def should_lapse(v, changed, facts, now=None):
    keys = {f.key for f in changed}
    req_keys = set()
    for c in v.expires_when:
        if c["kind"] == "capability_gain":
            if any(_gain(c, f) for f in changed):
                return True
        elif c["kind"] == "entity_fact":                                   # any NEW fact about the entity, even one never seen before
            if any(_entity_fact(c, f) for f in changed):
                return True
        elif c["kind"] == "requirement":
            ck = {x["key"] for x in (c.get("all") or [])}
            req_keys |= ck
            if ck & keys and requirement_covered(c, facts, v.entitlements, now) != c["covered_at_issue"]:
                return True
    return bool((set(v.depends_on) - req_keys) & keys)                    # dependencies with no condition lapse on any change

def lapse_dependents(store, changed, now):
    """Runs BEFORE any Spark call."""
    facts, lapsed = store.latest_facts(), []
    for v in store.verdicts(status="CURRENT"):
        if should_lapse(v, changed, facts, now):
            store.lapse_verdict(v.id, now, "new or changed fact matched a recheck condition: " + ", ".join(sorted({f.key for f in changed})))
            lapsed.append(v.id)
    return lapsed

def triggers(store, v):
    """Facts recorded since this verdict was issued that bear on it."""
    out = []
    for f in store.facts_since(v.issued_at):
        if f.key in v.depends_on or (f.entity_id == v.entity_id and f.metric.startswith("counter.")) \
           or any(c["kind"] == "capability_gain" and _gain(c, f) for c in v.expires_when) \
           or any(c["kind"] == "entity_fact" and _entity_fact(c, f) for c in v.expires_when) \
           or any(c["kind"] == "requirement" and f.key in {x["key"] for x in (c.get("all") or [])} for c in v.expires_when):
            out.append(f)
    return out

def grounded_results(s):
    """Only search results the PROVIDER itself returned or cited count. Generated URLs with no provider record are dropped."""
    cited = set(s.citations or [])
    return [r for r in s.data["results"] if r["url"] in cited]

def _packet(store, evidence):
    """What the Judge sees: typed values, sources and dates, not just ids."""
    out = []
    for e in evidence:
        f = store.get_fact(e["fact_id"]) if isinstance(e["fact_id"], int) else None
        out.append({"id": e["ref"], "key": e["key"], "value": f.value if f else None, "source_url": e["url"], "published": f.source_ts if f else None,
                    "observed": f.observed_at if f else None, "effective": f.effective_at if f else None})
    return out

def _shared(memo, kind, tool, changes, make):
    """classify and search see only the tool and the public changes, never the seat, so one answer serves every lapsed verdict of
    that tool in this run: the same question is asked once (consistent across seats, and half the cost)."""
    key = (kind, tool, json.dumps(changes, sort_keys=True, default=str))
    if key not in memo:
        memo[key] = make()
    return memo[key]

def rejudge(store, spark, v, now, memo=None):
    """Rules first. If the rules change the action, the change is material by definition: search -> judge -> publish.
    If the rules keep the action, classify asks whether the change matters; a clean 'not material' re-verifies the same action
    (no search, no judge), anything else goes on to search -> judge. Anything weak, failed, ungrounded or raced stays LAPSED."""
    memo = {} if memo is None else memo
    tool = v.entity_id
    try:
        spark.guard.begin_tool(tool, purpose=f"reassess:{v.id}", dedupe_key=f"reassess:{v.id}")
    except BudgetExceeded as e:
        return Outcome("failed", f"budget: {e.reason}")
    mark = store.max_fact_id()                                              # inputs as of the start of this reassessment
    try:
        trig = triggers(store, v)
        ev = evaluate(store, tool, v.requirements, v.entitlements, now=now,
                      watch=[c for c in v.expires_when if c["kind"] in ("capability_gain", "entity_fact")],
                      extra_evidence=[evidence_entry(f) for f in trig])
        if v.requirements and ev.action is None:
            return Outcome("weak", "insufficient evidence: a requirement is unknown, so no new verdict is published")
        changes = [{"key": f.key, "value": f.value, "url": f.url, "ts": f.source_ts or f.observed_at} for f in trig if not f.metric.startswith("counter.")]
        own = set()                                                          # facts this reassessment wrote itself
        still_valid = lambda: not any(f.id > mark and f.id not in own for f in triggers(store, v))
        calls = []
        if ev.action == v.action:                                            # the rules keep the answer: does the change matter at all?
            c = _shared(memo, "classify", tool, changes, lambda: spark.call("classify", {"tool": tool, "changes": changes}, tool=tool))
            calls.append(c.call_id)
            if not c.data["material"] or c.data["label"] == "minor":         # clean and not material: re-verified, same action
                new = store.publish_successor(v.id, still_valid, entity_id=tool, context=v.context, action=v.action, reason=hold_reason(v.action, ev.uncovered),
                                              depends_on=ev.depends_on, expires_when=ev.expires_when, evidence=list(ev.evidence), uncovered=ev.uncovered,
                                              issued_at=now, call_ids=calls, requirements=v.requirements, entitlements=v.entitlements,
                                              counter_checked=False, visibility=v.visibility, judge_output=None)
                return Outcome("reissued", new_id=new.id) if new else Outcome("weak", "inputs changed or another worker published first")
        s = _shared(memo, "search", tool, changes,
                    lambda: spark.call("search", {"tool": tool, "topic": "counter-evidence", "changes": changes}, tool=tool))   # public research: no seat context
        if not s.search_executed:
            return Outcome("weak", "web search was not actually executed; refusing an ungrounded verdict")
        results = grounded_results(s)
        if s.data["results"] and not results:
            return Outcome("weak", "search results were not grounded in provider-returned sources")
        web = [append_counter(store, tool, r, now) for r in results]
        own |= {f.id for f in web}
        evidence = list(ev.evidence) + [evidence_entry(f) for f in web if f.id not in {e["fact_id"] for e in ev.evidence}]
        offered = {e["ref"]: e for e in evidence}
        fresh_ids = {f"f{f.id}" for f in trig} | {f"f{f.id}" for f in web}
        j = spark.call("judge", {"tool": tool, "context": v.context, "proposed_action": ev.action, "uncovered": ev.uncovered,
                                 "requirements": [{"text": g["text"], "status": g["status"]} for g in ev.gates], "entitlements": list(v.entitlements),
                                 "new_evidence": sorted(fresh_ids & set(offered)), "evidence": _packet(store, evidence)}, tool=tool)
        d = j.data
        if v.requirements:
            if d["action"] != ev.action:
                return Outcome("weak", f"judge said {d['action']} but the evidence decides {ev.action}")
        elif d["action"] == "RETIRE":
            return Outcome("weak", "RETIRE needs declared requirements to be covered")
        if d["confidence"] < MIN_CONFIDENCE:
            return Outcome("weak", f"judge confidence {d['confidence']} below threshold {MIN_CONFIDENCE}; not published")
        if any(ref not in offered for ref in d["citations"]):
            return Outcome("weak", "judge cited evidence that does not exist")
        if held := uncitable(d["citations"], evidence, tool):                # AS-232: a verdict rests only on citable sources
            return Outcome("weak", "held: the judge cited a source that is not the vendor, the platform maker, a store, a registry or a regulator or court: "
                           + ", ".join(held))
        if not (set(d["citations"]) & fresh_ids):
            return Outcome("weak", "judge did not cite the new evidence")
        final = ev.action if v.requirements else d["action"]
        new = store.publish_successor(v.id, still_valid, entity_id=tool, context=v.context, action=final, reason=d["reason"],
                                      depends_on=ev.depends_on, expires_when=ev.expires_when, evidence=evidence, uncovered=ev.uncovered,
                                      issued_at=now, call_ids=calls + [s.call_id, j.call_id], requirements=v.requirements,
                                      entitlements=v.entitlements, counter_checked=True, visibility=v.visibility,
                                      judge_output={k: d[k] for k in ("action", "reason", "confidence", "citations")})
        if new is None:
            return Outcome("weak", "inputs changed or another worker published first; not publishing an answer built on older evidence")
        return Outcome("reissued", new_id=new.id)
    except BudgetExceeded as e:
        return Outcome("failed", f"budget: {e.reason}")
    except Exception as e:                                                   # schema errors, network errors, anything else
        return Outcome("failed", f"{type(e).__name__}: {e}")
    finally:
        spark.guard.end_tool(tool)

def recheck_due(store, spark, v, now, memo=None):
    """Freshness deadline reached: the verdict LAPSES FIRST, then is re-checked. Only a clean, grounded check re-issues it."""
    store.lapse_verdict(v.id, now, "scheduled recheck is due")
    memo = {} if memo is None else memo
    tool = v.entity_id
    if held := uncitable((v.judge_output or {}).get("citations", []), v.evidence, tool):   # AS-232: never re-issued as is if it rests on an uncitable source
        return "lapsed", "held: the verdict cites a source that is not citable: " + ", ".join(held)
    try:
        spark.guard.begin_tool(tool, purpose=f"recheck:{v.id}", dedupe_key=f"recheck:{v.id}")
        s = _shared(memo, "search", tool, [], lambda: spark.call("search", {"tool": tool, "topic": "counter-evidence", "changes": []}, tool=tool))
        if not s.search_executed:
            return "failed", "search not executed"
        results = grounded_results(s)
        if s.data["results"] and not results:
            return "failed", "search results not grounded"
        found = [append_counter(store, tool, r, now) for r in results]
        calls = [s.call_id]
        if found:
            ch = [{"key": f.key, "value": f.value, "url": f.url, "ts": f.source_ts or f.observed_at} for f in found]
            c = _shared(memo, "classify", tool, ch, lambda: spark.call("classify", {"tool": tool, "changes": ch}, tool=tool))
            calls.append(c.call_id)
            if c.data["material"] and c.data["label"] != "minor":
                return "lapsed", "material counter-evidence found; stays lapsed for reassessment"
        ev = [*v.evidence, *(evidence_entry(f) for f in found if f.id not in {e["fact_id"] for e in v.evidence})]
        new = store.publish_successor(v.id, lambda: True, entity_id=tool, context=v.context, action=v.action, reason=v.reason,
                                      depends_on=v.depends_on, expires_when=v.expires_when, evidence=ev, uncovered=v.uncovered, issued_at=now,
                                      call_ids=calls, requirements=v.requirements, entitlements=v.entitlements, counter_checked=True,
                                      visibility=v.visibility, judge_output=v.judge_output)
        return ("reissued", new.id) if new else ("failed", "could not publish")
    except Exception as e:
        return "failed", f"{type(e).__name__}: {e}"
    finally:
        spark.guard.end_tool(tool)

def run_sync(store, connectors, spark, now):
    rep, observations = SyncReport(), []
    for c in connectors:
        try:
            observations.extend(c.fetch())
        except Exception as e:
            rep.failed.append((getattr(c, "name", "connector"), f"fetch: {e}"))      # a failed fetch is NOT an unchanged source
    changed, observed = ingest(store, observations, now)                    # polling is recorded per key (sync_checks)
    rep.changed = [f.key for f in changed]
    rep.lapsed = lapse_dependents(store, changed, now)                       # LAPSE FIRST, before any Spark call
    memo = {}                                                                # one classify / one search per tool and question, per run
    for v in store.verdicts(status="CURRENT"):
        if v.fresh_until < now:                                              # semantic recheck deadline; unchanged polls never renew it
            kind, detail = recheck_due(store, spark, v, now, memo)
            rep.lapsed.append(v.id)
            if kind == "reissued":
                rep.rejudged.append((v.id, detail))
            elif kind == "failed":
                rep.failed.append((v.id, detail))
    for v in store.verdicts(status="LAPSED"):
        if store.has_successor(v.id) or v.id in {o for o, _ in rep.rejudged}:
            continue
        out = rejudge(store, spark, v, now, memo)
        if out.kind == "reissued":
            rep.rejudged.append((v.id, out.new_id))
        else:
            rep.still_lapsed.append((v.id, out.detail))
    return rep
