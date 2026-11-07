# spec: AS-013 AS-066 AS-101 AS-102 AS-104 AS-131 AS-134 AS-223 AS-237 AS-248 AS-306
"""Writes ../site-data.js: the page's data, generated ONLY from data/airstack-demo.db (+ its export and data/ab-runs.json).
The page is a static snapshot of the database. Nothing here calls a model.

THE FACE RULE: every sentence a visitor reads comes from the HUMAN text below, built from the database's own facts and the rules
engine's own results. Raw keys, hashes, call ids and the model's verbatim output appear only in the Execution and raw views.
Answers for every plan x device are precomputed with the SAME evaluate() the engine uses, so flipping a chip on the page is a lookup.
Usage: ../.venv/bin/python tools/build_site_data.py"""
import json, re
from datetime import datetime, timezone, timedelta
from airstack import views
from airstack.evaluate import evaluate
from airstack.store import Store, add_days
from airstack.config import FRESH_DAYS
from airstack import paths
from airstack.mcp_server import DESCRIPTIONS as MCP_DESCRIPTIONS

ROOT = paths.ROOT
EXPORT = paths.DEMO_EXPORT
DB = paths.DEMO_DB
AB = paths.DATA / "ab-runs.json"
MODEL = "muse-spark-1.3"
PT = timezone(timedelta(hours=-7))                                       # PDT in August

CFG = paths.config("site")                                      # config/site.json
SOURCE = CFG["source_names"]
SHORT = CFG["source_short"]
ANY = object()
# (fact key, url fragment, value or ANY) -> (one short line, the phrase verify_references.py must find on that page)
CLAIMS = [
    ("meet.in_person_notes", "9to5google.com", False, "Announced at Cloud Next, not yet available", "expanding beyond the virtual realm to in-person meetings"),
    ("meet.in_person_notes", "workspaceupdates", True, "Meet takes notes in in-person meetings", "Take Notes for me for in-person meetings is now available"),
    ("meet.in_person_notes_platforms", "workspaceupdates", ANY, "Android first; iPhone no sooner than 31 Aug 2026", "starting no sooner than August 31, 2026"),
    ("meet.in_person_notes_ios_earliest", "workspaceupdates", ANY, "iPhone no sooner than 31 Aug 2026", "starting no sooner than August 31, 2026"),
    ("meet.listed_editions", "workspaceupdates", ANY, "8 Google plans listed; Business Starter isn't one", "Frontline Plus"),
    ("meet.supported_languages", "14754931", ANY, "8 languages, including English", "Italian Japanese Korean Portuguese Spanish"),
    ("meet.in_person_notes_platforms", "17020724", ANY, "Steps for Android, iPhone and computer", "On your iPhone or iPad, open the Google Meet app"),
    ("meet.listed_editions", "13952129", ANY, "7 plans include it; Business Starter isn't one",
     "Take notes for me Business Standard Business Plus Enterprise Standard Enterprise Plus Frontline Plus"),
]
# the three questions on the page
PLANS = CFG["plans"]
DEVICES = [tuple(d) for d in CFG["devices"]]
DEFAULT = tuple(CFG["default"])
EXAMPLES = {k: tuple(v) for k, v in CFG["examples"].items()}
MCP_TOOLS = sorted(MCP_DESCRIPTIONS)

def fd(iso):
    """13 Aug 2026 on every face; ISO only in raw views."""
    return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%-d %b %Y") if iso else ""

def pt(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(PT)

def claim(f):
    key = f"{f['entity_id']}.{f['metric']}"
    for k, frag, val, text, expect in CLAIMS:
        if k == key and frag in f["url"] and (val is ANY or f["value"] == val):
            return text, expect
    return None, None

def requirements(plan, platform):
    """What you use it for, as the engine's predicates: the same shape as the recorded examples' requirements."""
    ent = "plan:" + plan.lower().replace(" ", "_")
    return [{"id": "in_person", "text": "Notes for in-person meetings", "all": [{"key": "meet.in_person_notes", "op": "eq", "value": True}]},
            {"id": "platform", "text": f"Available on {platform}", "all": [{"key": "meet.in_person_notes_platforms", "op": "includes", "value": platform}]},
            {"id": "lang_en", "text": "English is a supported language", "all": [{"key": "meet.supported_languages", "op": "includes", "value": "English"}]},
            {"id": "edition", "text": f"{plan} is a listed plan", "entitlement": ent,
             "all": [{"key": "meet.listed_editions", "op": "includes", "value": plan}]}], [ent]

TOPIC = {"meet.in_person_notes": "launch", "meet.listed_editions": "plans", "meet.in_person_notes_platforms": "devices"}
ORDER = ["meet.in_person_notes", "meet.listed_editions", "meet.in_person_notes_platforms"]

def assess(store, facts, product, plan, device, platform, now, source_record):
    """One product's answer in one context, AT an explicit evaluation time (review C04: a future-effective fact must not count).
    Action and validity are separate, and unknown stays unknown (review C01): only a FAILED requirement may produce a negative claim."""
    if not now:
        raise ValueError("an evaluation time is required at every publication boundary")
    reqs, ents = requirements(plan, platform)
    ev = evaluate(store, product, reqs, ents, now=now)
    gates = {g["id"]: g["status"] for g in ev.gates}
    used = {e["key"]: facts[e["fact_id"]] for e in ev.evidence if isinstance(e["fact_id"], int)}
    on = {"Computer": "a computer"}.get(device, device)                       # a sentence says "on a computer", the chip says Computer
    label = {"in_person": "Notes in in-person meetings", "platform": f"On {on}", "lang_en": "In English",
             "edition": "A Google Workspace or Google AI plan" if plan == "No Google plan" else f"With {plan}"}
    basis = None
    if ev.action == "RETIRE":
        action, reason, changes = "retire", f"Google Meet takes notes in in-person meetings on {on}, and {plan} includes it.", f"Google drops it from {plan}, or you change plans."
    elif ev.action is None:                                                    # unresolved: no current recommendation, ever
        missing = [label.get(g["id"], g["text"]) for g in ev.gates if g["status"] == "unknown"]
        action, reason, changes = "unknown", "No verified, effective source yet for: " + ", ".join(missing) + ".", "A source confirms it either way."
    else:
        action = "keep"
        basis = "Provisional: this checks what you already have, not the app itself."
        if gates.get("edition") == "fail":
            reason = ("Meet's in-person notes need a Google Workspace or Google AI plan." if plan == "No Google plan"
                      else f"Meet's in-person notes aren't included in {plan}.")
            changes = "You move to a plan that includes it." if plan == "No Google plan" else f"Google adds {plan} to Meet's in-person notes."
        elif gates.get("platform") == "fail":
            reason, changes = f"Meet's in-person notes aren't on {on} yet.", f"Google brings them to {on}."
        else:
            reason, changes = "Meet can't take notes in in-person meetings yet.", "Google ships in-person notes."
    return {"action": action, "line": {"retire": "You can stop paying for this.", "keep": "Nothing you already have does this yet.",
                                       "unknown": "Not enough evidence yet."}[action],
            "reason": reason, "changesIf": changes, "basis": basis, "uncovered": ev.uncovered,
            "needs": [{"label": label.get(g["id"], g["text"]), "status": {"pass": "covered", "fail": "unmet"}.get(g["status"], "unknown")} for g in ev.gates],
            "covered": sum(1 for x in gates.values() if x == "pass"), "unmet": sum(1 for x in gates.values() if x == "fail"),
            "unknown": sum(1 for x in gates.values() if x == "unknown"),
            "sources": [{**source_record(used[key]), "label": SHORT.get(used[key]["source"], used[key]["source"]) + " · " + TOPIC[key]}
                        for key in ORDER if key in used],
            "evaluatedAt": now, "freshUntil": add_days(now, FRESH_DAYS)}

def products():
    """Every checked app: Fireflies, plus the market's incumbents when the market corpus exists. Data, not code: a new row is a new product."""
    out = [("fireflies", "Fireflies")]
    db = paths.MARKET_DB
    if db.exists():
        import sqlite3
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out += [(r[0], r[1]) for r in c.execute("SELECT id, name FROM entities WHERE kind='incumbent' AND lane_id='meeting-notes' ORDER BY rowid") if r[0] != "fireflies"]
        from airstack.fetch import host
        users = {e: max((json.loads(v) for v, u in c.execute("SELECT value, url FROM facts WHERE entity_id=? AND metric='x.store_users'", (e,))
                         if host(u) == "chromewebstore.google.com"), default=-1) for e, _ in out}
        out.sort(key=lambda x: -users[x[0]])                                 # ordered by the data (Chrome Web Store users), never hand-picked
    return out

def directory_counts():
    p = paths.DIRECTORY
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    researched = sum(1 for v in json.loads(paths.PROFILES.read_text()).values() if v.get("facts")) if paths.PROFILES.exists() else 0   # products with facts from their own pages
    return {"products": len(d["products"]), "orgs": sum(1 for o in d["orgs"].values() if o[5] != "person"), "types": len(d["types"]), "researched": researched,
            "fetched_at": d["source"]["fetched_at"]}

def build_answers(store, facts, checked, source_record):
    """Precompute every rules-only answer and intern identical values for the compact first-paint snapshot."""
    checked_products = products()
    answer_grid = {product: {plan: {device: assess(store, facts, product, plan, device, platform, checked, source_record)
                                    for device, platform in DEVICES} for plan in PLANS}
                   for product, _ in checked_products}
    pool, indexes = [], {}

    def intern(answer):
        key = json.dumps(answer, sort_keys=True)
        if key not in indexes:
            indexes[key] = len(pool)
            pool.append(answer)
        return indexes[key]

    answers = {product: {plan: {device: intern(answer_grid[product][plan][device]) for device in answer_grid[product][plan]}
                         for plan in answer_grid[product]} for product in answer_grid}
    return checked_products, answer_grid, pool, answers

def build_examples(answer_grid, current, calls, live):
    """Connect the two visible examples to their stored verdict and model-call receipts."""
    examples = {}
    for context, (plan, device) in EXAMPLES.items():
        verdict = current[context]
        answer = answer_grid["fireflies"][plan][device]
        assert answer["action"] == verdict["action"].lower(), (context, answer["action"], verdict["action"])
        call_refs = [ref for ref in verdict["call_ids"] if ref in calls]
        judged = verdict["judge_output"] is not None
        examples[f"fireflies|{plan}|{device}"] = {
            "ctx": context, "verdictId": verdict["id"], "kind": ("judged" if judged else "reverified") if live else "recorded",
            "calls": len(call_refs), "roles": [calls[ref]["role"] for ref in call_refs],
            "tokens": sum((calls[ref]["in_tok"] or 0) + (calls[ref]["out_tok"] or 0) for ref in call_refs),
            "ms": sum(calls[ref]["latency_ms"] or 0 for ref in call_refs),
            "confidence": (verdict["judge_output"] or {}).get("confidence"), "on": verdict["issued_at"][:10],
            "recheckBy": verdict["fresh_until"][:10]}
    return examples

def discovery_data():
    """Build the compact movers, registry and catalog index needed before lazy datasets load."""
    import build_market_data as market_data
    movers = market_data.movers()
    if movers:
        def substantial(row):
            return row["dl"]["value"] >= 5000 and not (row["dl"].get("vsBase") is not None and row["dl"]["vsBase"] < 0)

        top = sorted([row for row in movers["rows"] if row["dl"]["delta"] is not None],
                     key=lambda row: (not substantial(row), -row["dl"]["delta"]))[:12]
        def compact(row):
            return {"id": row["id"], "name": row["name"], "lane": row["lane"], "laneName": row["laneName"],
                    "dl": {key: row["dl"].get(key) for key in ("value", "delta", "vsBase", "baseWeeks", "registry", "url")},
                    "hn": {key: row["hn"][key] for key in ("value", "delta", "query")},
                    "gh": {key: row["gh"][key] for key in ("stars", "release", "released", "url")}}
        movers = {"window": movers["window"], "generated": movers["generated"], "lanes": movers["lanes"],
                  "rows": [compact(row) for row in top], "partial": True, "total": len(movers["rows"])}
    universe = json.loads(paths.UNIVERSE.read_text())
    lanes = [{"id": lane, "name": market_data.LANES.get(lane, lane), "n": sum(tool["lane"] == lane for tool in universe)}
             for lane in dict.fromkeys(tool["lane"] for tool in universe)]
    from airstack.catalog import CATEGORIES, entries as catalog_entries
    known = {tool["id"] for tool in universe} | {tool["name"].lower() for tool in universe}
    catalog = [entry for entry in catalog_entries() if entry["id"] not in known and entry["name"].lower() not in known]
    categories = [{"id": key, "name": name, "tools": sum(entry["category"] == key for entry in catalog)}
                  for key, name in CATEGORIES.items()]
    index = [[tool["id"], tool["name"], tool["lane"]] for tool in universe]
    index += [[entry["id"], entry["name"], entry["category"], entry.get("aliases") or []] for entry in catalog]
    return index, categories, lanes, movers

def build_lifecycle(snapshot, verdicts, replay, checked, live, facts_for, historical_source):
    """Render the four-step replay and each example's append-only revision history."""
    histories = {context: sorted([verdict for verdict in snapshot["verdicts"] if verdict["context"] == context],
                                 key=lambda verdict: verdict["id"]) for context in EXAMPLES}
    events = sorted(snapshot["verdict_events"], key=lambda event: event["id"])
    context_by_verdict = {verdict["id"]: verdict["context"] for verdict in snapshot["verdicts"]}
    withheld = {verdict_id: reason for report in (snapshot.get("sync_report", {}), snapshot.get("check_report", {}))
                for verdict_id, reason in report.get("still_lapsed", [])}

    def state_after(count):
        state = {}
        for event in events[:count]:
            context = context_by_verdict[event["verdict_id"]]
            if context not in EXAMPLES:
                continue
            if event["event"] == "PUBLISHED":
                state[context] = {"action": verdicts[event["verdict_id"]]["action"].lower(), "state": "current",
                                  "verdictId": event["verdict_id"]}
            elif event["event"] == "LAPSED" and state.get(context, {}).get("verdictId") == event["verdict_id"]:
                state[context] = {**state[context], "state": "lapsed"}
        return state

    event_cut = lambda predicate: max(index for index, event in enumerate(events) if predicate(event)) + 1
    first_event = events[0]["at"]
    cuts = [("before", fd(first_event), event_cut(lambda event: event["at"] == first_event)),
            ("change", fd(replay), event_cut(lambda event: event["at"] == replay and event["event"] == "LAPSED")),
            ("reassessed", fd(replay), event_cut(lambda event: event["at"] == replay)),
            ("checked", fd(checked), len(events))]

    def note(step, context, state, previous):
        verdict = verdicts[state["verdictId"]]
        if step == "before":
            return "Meet can't take in-person notes yet"
        if step == "change":
            return "Needs a second look"
        if state["state"] == "lapsed":
            reason = withheld.get(state["verdictId"], "")
            return "Muse wasn't confident enough: nothing published" if "confidence" in reason else "Still needs a second look"
        if previous and previous.get("verdictId") == state["verdictId"]:
            return "Unchanged"
        if verdict["judge_output"]:
            return f"Muse Spark judged {state['action'].title()}" if live else f"Judged {state['action'].title()} (recorded)"
        plan = EXAMPLES[context][0]
        return f"Re-checked: still not included in {plan}" if verdict["uncovered"] else "Re-checked: still covered"

    steps, previous = [], {}
    for name, day, count in cuts:
        state = state_after(count)
        steps.append({"step": name, "date": day, "clock": "live" if name == "checked" and live else "replay",
                      "rows": [{**state[context], "note": note(name, context, state[context], previous.get(context))}
                               for context in EXAMPLES]})
        previous = state
    announced = next(fact for fact in facts_for("meet.in_person_notes") if fact["value"] is False)
    shipped = next(fact for fact in facts_for("meet.in_person_notes") if fact["value"] is True)
    reread = [fact for fact in facts_for("meet.in_person_notes_platforms") if "17020724" in fact["url"]]
    captions = {"before": {"text": "Meet's in-person notes announced, not yet available", "source": historical_source(announced)},
                "change": {"text": "Google: Meet now takes notes in in-person meetings, Android first",
                           "source": historical_source(shipped), "at": pt(shipped["source_ts"]).strftime("%-I:%M %p PT")},
                "reassessed": {"text": "Each plan re-checked against the new facts", "source": None},
                "checked": {"text": "Google's help pages re-read: iPhone and computer added" if reread else "Scheduled re-check",
                            "source": historical_source(reread[-1]) if reread else None}}
    for step in steps:
        step["caption"] = captions[step["step"]]
    life = {"labels": [f"{plan} · {device}" for plan, device in EXAMPLES.values()], "steps": steps}

    history = []
    for context, (plan, device) in EXAMPLES.items():
        rows = []
        for verdict in histories[context]:
            for event in [event for event in events if event["verdict_id"] == verdict["id"]]:
                if event["event"] == "SUPERSEDED":
                    continue
                what = {"PUBLISHED": verdict["action"].title(), "LAPSED": "Needs a second look"}[event["event"]]
                cause = ("first answer" if event["cause"] == "first issue" else "re-checked on schedule" if "scheduled" in event["cause"]
                         else "a fact it depends on changed" if event["event"] == "LAPSED" else
                         ("Muse Spark judged it" if verdict["judge_output"] else "re-checked by the rules"))
                rows.append({"date": fd(event["at"]), "clock": "live" if event["at"][:10] == checked[:10] and live else "replay",
                             "what": what, "why": cause, "verdictId": verdict["id"]})
            if verdict["id"] in withheld:
                reason = withheld[verdict["id"]]
                rows.append({"date": fd(replay if verdict["lapsed_at"] and verdict["lapsed_at"][:10] == replay[:10] else checked),
                             "clock": "replay", "what": "Withheld",
                             "why": "Muse's confidence was below 0.7" if "confidence" in reason else reason, "verdictId": verdict["id"]})
        history.append({"label": f"{plan} · {device}", "rows": rows})
    return life, history, withheld

def build_sources(snapshot):
    """Publish only human-labelled facts, marking every row superseded by a later value."""
    newest = {f"{fact['entity_id']}.{fact['metric']}": fact["id"] for fact in snapshot["facts"]}
    sources = []
    for fact in snapshot["facts"]:
        text, expected = claim(fact)
        if not text:
            continue
        key = f"{fact['entity_id']}.{fact['metric']}"
        sources.append({"fact": text, "source": SOURCE.get(fact["source"], fact["source"]), "published": (fact["source_ts"] or "")[:10],
                        "observed": fact["observed_at"][:10], "url": re.sub(r"^https://", "", fact["url"]), "expect": expected, "real": True,
                        "key": key, "value": fact["value"], "hash": fact["value_hash"][:8], "superseded": newest[key] != fact["id"]})
    return sources

def main():
    snapshot = json.loads(EXPORT.read_text())
    store = Store(str(DB))
    facts = {fact["id"]: fact for fact in snapshot["facts"]}
    calls = {call["call_ref"]: call for call in snapshot["calls"]}
    verdicts = {verdict["id"]: verdict for verdict in snapshot["verdicts"]}
    live = any(call["model"] == MODEL for call in snapshot["calls"])
    replay = snapshot["about"]["replay_clock"]
    checked = snapshot["about"].get("checked_at") or replay
    current = {verdict["context"]: verdict for verdict in snapshot["verdicts"]
               if verdict["status"] == "CURRENT" and verdict["entity_id"] == "fireflies"}
    facts_for = lambda key: [fact for fact in snapshot["facts"] if f"{fact['entity_id']}.{fact['metric']}" == key]
    def source_record(fact):
        # "date" is when the page was last REALLY re-read (tools/verify_references.py --record), never the replay clock and never a publication date;
        # when the page states a publication date it travels separately as "published".
        last_checked = max((fact["observed_at"] or "")[:10], (store.last_polled(f"{fact['entity_id']}.{fact['metric']}") or "")[:10])
        return {"label": SOURCE.get(fact["source"], fact["source"]), "date": last_checked, "dated": "checked",
                "published": (fact["source_ts"] or "")[:10] or None, "url": fact["url"]}

    def historical_source(fact):                                    # the timeline uses the source's event time, not its last re-read
        return {**source_record(fact), "date": (fact["source_ts"] or fact["observed_at"] or "")[:10]}

    # ---- every plan x device, answered by the rules over today's facts (no model call) ---------------------------------------
    checked_products, answer_grid, pool, answers = build_answers(store, facts, checked, source_record)
    examples = build_examples(answer_grid, current, calls, live)
    life, history, withheld = build_lifecycle(snapshot, verdicts, replay, checked, live, facts_for, historical_source)
    sources = build_sources(snapshot)

    # ---- execution: the receipt, the calls, the judge's own words, what search returned, the A/B, MCP ---------------------------
    example_verdict = current["seat:A"]
    citations = (example_verdict["judge_output"] or {}).get("citations", [])
    judge = {"verdictId": example_verdict["id"], "output": example_verdict["judge_output"],
             "cited": [{"ref": ref, "fact": (claim(facts[int(ref[1:])])[0] or facts[int(ref[1:])]["value"].get("title", "")
                                                   if isinstance(facts[int(ref[1:])]["value"], dict) else claim(facts[int(ref[1:])])[0]),
                        "url": facts[int(ref[1:])]["url"]} for ref in citations if ref[1:].isdigit() and int(ref[1:]) in facts]}
    searched = [{"title": fact["value"]["title"], "url": fact["url"], "seen": fact["observed_at"][:10]}
                for fact in snapshot["facts"] if fact["metric"].startswith("counter.")]
    rows = [{"ref": call["call_ref"], "role": call["role"], "model": call["model"], "ts": call["ts"],
             "tin": call["in_tok"] or 0, "tout": call["out_tok"] or 0, "ms": call["latency_ms"] or 0, "cost": call["cost"]}
            for call in snapshot["calls"]]
    ab = []                                                                     # every A/B set, newest first; none is ever dropped
    for f, label in ((paths.DATA / "ab-runs-2.json", "Business Standard · the question doesn't mention Meet's feature"),
                     (AB, "Business Starter · first run; its question named Meet's feature")):
        if f.exists():
            ab.append({**json.loads(f.read_text()), "label": label})
    ab = ab or None
    mcp = {"request": {"method": "tools/call", "params": {"name": "assess", "arguments": {"app": "Fireflies", "plan": EXAMPLES["seat:B"][0], "meeting": "in_person", "device": EXAMPLES["seat:B"][1], "needs": ["nothing else"]}}},
           "response": views.get_verdict(store, "fireflies", "B", now=checked), "as_of": checked, "tools": MCP_TOOLS}
    sync_report, check_report = snapshot.get("sync_report", {}), snapshot.get("check_report", {})
    status = {"changed": len(sync_report.get("changed", [])) + len(check_report.get("changed", [])),
              "lapsed": len(sync_report.get("lapsed", [])) + len(check_report.get("lapsed", [])),
              "rejudged": len(sync_report.get("rejudged", [])) + len(check_report.get("rejudged", [])), "withheld": len(withheld),
              "calls": len(rows), "credits": f"{sum(float(r['cost']) for r in rows):.4f}"}

    search_index, categories, lanes, movers = discovery_data()
    data = {"index": search_index, "cats": categories,
            "dir": directory_counts(),                                       # the Wikidata directory loads on demand (directory.json); its counts ship at first paint
            "brief": (json.loads(paths.BRIEF.read_text()) if paths.BRIEF.exists() else None),   # published only after its numbers were checked
            "lanes": lanes, "moversTop": movers, "meta": {"model": MODEL, "live": live, "generated_from": "data/airstack-demo.db",
                     "dataset_version": snapshot["about"]["dataset_version"], "generated_at": snapshot["about"]["generated_at"],
                     "replay_clock": replay, "checked_at": checked, "spark": snapshot["about"]["spark"]},
            "tools": [{"key": key, "name": name, "cat": "Meeting notes", "aliases": ["fireflies.ai"] if key == "fireflies" else []}
                      for key, name in checked_products],
            "plans": PLANS, "devices": [d for d, _ in DEVICES], "default": list(DEFAULT), "answers": answers, "pool": pool, "examples": examples,
            "life": life, "history": history, "sources": sources, "status": status,
            "execution": {"rows": rows, "judge": judge, "searched": searched, "ab": ab, "mcp": mcp}}
    from airstack.publication import hold
    data = hold(data)                                              # the publication hold: commentary sources and allegation sentences never reach the page (stored records are untouched)
    out = paths.SITE_DATA
    import sys; sys.path.insert(0, str(ROOT / "tools")); import spec_audit
    cited = spec_audit.citing("site-data.js")
    out.write_text(f"// spec: {' '.join(cited)}\n// GENERATED by backend/tools/build_site_data.py from data/airstack-demo.db. Do not edit by hand.\n"
                   "window.AIRSTACK_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")   # compact: it is render-blocking
    print(f"site-data.js: {len(checked_products)} products x {len(PLANS)}x{len(DEVICES)} answers, {len(sources)} sources, {len(rows)} calls, live={live}, ab={len(ab) if ab else 0} sets")
    return data

if __name__ == "__main__":
    main()
