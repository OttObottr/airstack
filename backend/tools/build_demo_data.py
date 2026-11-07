# spec: AS-030 AS-055 AS-130
"""Builds data/airstack-demo.db and data/airstack-demo-export.json so reviewers can inspect the DATA, not just the code.
Inputs: REAL, sourced facts (9to5Google Cloud Next coverage, Google's recorded feed entry, Google Meet Help pages) + EXAMPLE seats.
Two syncs: the 13 Aug 2026 event (replayed at Google's own timestamps), then a CHECK that re-reads Google's current help pages
(platforms, and the Meet row of the edition table) at the real clock, so the current verdicts are verified today, not in August.
Spark: recorded FIXTURE responses by default (labelled 'fixture (no model call)'), or --live for real Muse Spark calls
(needs MODEL_API_KEY in ../.env; capped at $0.50 per job and $2 for the day).
Two clocks: the ENGINE replays the event at its source times; MONEY and call logs always use the real clock.
Usage: ../.venv/bin/python tools/build_demo_data.py [--live]"""
import json, sys
from pathlib import Path
from airstack.budget import BudgetGuard
from airstack.connectors.workspace_updates import StaticConnector, WorkspaceUpdatesConnector
from airstack.engine import Obs, ingest, run_sync
from airstack.evaluate import evaluate
from airstack.spark import FakeSpark, GuardedSpark
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
OUT = paths.DATA; OUT.mkdir(exist_ok=True)
DB = OUT / "airstack-demo.db"
NEXT = "https://9to5google.com/2026/04/22/google-workspace-next-2026/"
H2 = "https://support.google.com/meet/answer/14754931"
FEED = (ROOT / "backend/tests/fixtures/workspace_updates_2026-08.atom").read_text()
T0, T_EVENT = "2026-08-01T12:00:00Z", "2026-08-13T18:00:00Z"
T_CHECK = "2026-11-04T05:00:00Z"       # fixture builds: when Google's help pages were re-read (3 Nov 2026, PT). --live uses the real clock.
IOS_HELP = "https://support.google.com/meet/answer/17020724?co=GENIE.Platform%3DiOS&hl=en"
EDITION_TABLE = "https://support.google.com/meet/answer/13952129?co=GENIE.Platform%3DDesktop&hl=en"
MEET_EDITIONS = ["Business Standard", "Business Plus", "Enterprise Standard", "Enterprise Plus", "Frontline Plus", "Google AI Pro", "Google AI Ultra"]
CHECK_OBS = [Obs("meet", "in_person_notes_platforms", ["Android", "iOS", "Web"], "google.meet.help", IOS_HELP),   # the page has Android, iPhone/iPad and computer steps
             Obs("meet", "listed_editions", MEET_EDITIONS, "google.meet.help", EDITION_TABLE)]                    # Meet row of "Compare Gemini features"; Business Starter absent
LANGS = ["English", "French", "German", "Italian", "Japanese", "Korean", "Portuguese", "Spanish"]

def req(id, text, *conds, entitlement=None):
    r = {"id": id, "text": text, "all": [{"key": k, "op": op, "value": v} for k, op, v in conds]}
    return {**r, "entitlement": entitlement} if entitlement else r
ENTS = {"seat:A": ["workspace:business_standard"], "seat:B": ["workspace:business_starter"]}   # example inputs: the plan each seat holds
SEAT_A = [req("in_person", "Notes for in-person meetings", ("meet.in_person_notes", "eq", True)),
          req("platform", "Available on Android", ("meet.in_person_notes_platforms", "includes", "Android")),
          req("lang_en", "English is a supported language", ("meet.supported_languages", "includes", "English")),
          req("edition", "Business Standard is a listed edition", ("meet.listed_editions", "includes", "Business Standard"),
              entitlement="workspace:business_standard")]
SEAT_B = [req("edition", "Business Starter is a listed edition", ("meet.listed_editions", "includes", "Business Starter"),
              entitlement="workspace:business_starter") if r["id"] == "edition" else r for r in SEAT_A]   # the same seat on Business Starter
BEFORE = {c: "Meet's in-person notes were announced at Cloud Next but not yet available, so this seat still needs a separate note-taker." for c in ("seat:A", "seat:B")}
REASONS = {"seat:A": "Meet's 'Take notes for me' now covers in-person meetings on Android, and every requirement this seat declared is met.",
           "seat:B": "Google doesn't list Business Starter for Meet's 'Take notes for me', so this seat still needs a separate note-taker."}

def _env_key():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("MODEL_API_KEY=") and len(line) > 22:
                import os; os.environ.setdefault("MODEL_API_KEY", line.split("=", 1)[1].strip())

class PaidDataProtected(RuntimeError):
    """Raised instead of deleting a database that holds paid Muse Spark calls."""

def holds_live_calls(db):
    import sqlite3
    if not Path(db).exists():
        return False
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return c.execute("SELECT 1 FROM calls WHERE model = 'muse-spark-1.3' LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False

def main(live=False, out=None, force=False):
    """out: folder for the .db and export (default data/). Tests pass a temp folder so the working data never changes.
    A database that already holds paid Muse calls is NEVER deleted or rebuilt unless force=True (--force-new-live-run):
    paid results are kept and reused, not thrown away and bought again."""
    out = Path(out) if out else OUT
    db = out / "airstack-demo.db"
    if holds_live_calls(db) and not force:
        raise PaidDataProtected(f"{db} holds paid Muse Spark calls; refusing to overwrite it. Regenerate the page with build_site_data.py, "
                                "or pass --force-new-live-run to spend again on purpose.")
    if db.exists(): db.unlink()
    store = Store(str(db))
    # earlier state: announced at Cloud Next on 2026-04-22, "rolling out over the coming weeks", i.e. not yet available
    ingest(store, [Obs("meet", "in_person_notes", False, "press.9to5google", NEXT, "2026-04-22T12:01:00Z"),
                   Obs("meet", "supported_languages", LANGS, "google.meet.help", H2)], T0)
    for ctx, reqs in (("seat:A", SEAT_A), ("seat:B", SEAT_B)):
        ev = evaluate(store, "fireflies", reqs, ENTS[ctx], now=T0)
        store.put_verdict(entity_id="fireflies", context=ctx, action=ev.action, reason=BEFORE[ctx],
                          depends_on=ev.depends_on, expires_when=ev.expires_when, evidence=ev.evidence, uncovered=ev.uncovered,
                          issued_at=T0, requirements=reqs, entitlements=ENTS[ctx], visibility="public")   # explicit public EXAMPLE seats
    rec = {"classify": {"label": "capability_shock", "material": True, "rationale": "fixture: Meet gained in-person notes"},
           "search": {"results": [{"url": H2, "title": "Take notes for me in Google Meet", "snippet": "Supported languages: English, French, German, Italian, Japanese, Korean, Portuguese, Spanish", "published": ""}]},
           "judge": lambda p: {"action": p["proposed_action"], "reason": REASONS[p["context"]], "confidence": 0.9, "citations": [e["id"] for e in p["evidence"]]}}
    if live:
        from airstack.spark import LiveSpark
        _env_key()
        spark = GuardedSpark(LiveSpark(), store, BudgetGuard(store, utcnow, job_cap="0.50", day_cap="2"), utcnow)
    else:
        spark = GuardedSpark(FakeSpark(rec, cost="0"), store, BudgetGuard(store, utcnow, day_cap="10"), utcnow)
    rep = run_sync(store, [WorkspaceUpdatesConnector(fetch_text=lambda u: FEED)], spark, T_EVENT)
    check_at = utcnow() if live else T_CHECK                                 # the check is real time: its verdicts are fresh from today
    rep2 = run_sync(store, [StaticConnector("google.meet.help", CHECK_OBS)], spark, check_at)
    q = lambda sql: [dict(r) for r in store._q(sql).fetchall()]
    verdicts = q("SELECT * FROM verdicts ORDER BY id")
    for v in verdicts:
        for k in ("depends_on", "expires_when", "evidence", "uncovered", "call_ids", "requirements", "entitlements"):
            v[k] = json.loads(v[k])
        v["judge_output"] = json.loads(v["judge_output"]) if v["judge_output"] else None
    import hashlib
    content = json.dumps([q("SELECT entity_id,metric,value_hash,source_ts,effective_at FROM facts ORDER BY id"),
                          [{k: v[k] for k in ("context", "action", "reason", "status", "issued_at")} for v in verdicts]], sort_keys=True)
    export = {
        "about": {"dataset_version": hashlib.sha256(content.encode()).hexdigest()[:12], "generated_at": utcnow(),
                  "replay_clock": T_EVENT, "checked_at": check_at, "visibility": "every verdict here is an explicit PUBLIC example; no private seat is stored","generated_from": "backend/tools/build_demo_data.py" + (" --live" if live else ""), "facts": "all real and sourced",
                  "seats": "example inputs, not real customers",
                  "spark": "real Muse Spark calls (see calls[])" if live else "RECORDED FIXTURE responses; no live Muse call has been made yet (cost 0)",
                  "replay": "historical replay reconstructed from source timestamps",
                  "clocks": "times on 2026-08-01 and 2026-08-13 replay Google's own timestamps; checked_at is the real time Google's current help pages were re-read and the verdicts re-checked; calls.ts and budget_ledger.at are always real time"},
        "sync_report": {"changed": rep.changed, "lapsed": rep.lapsed, "rejudged": rep.rejudged, "still_lapsed": rep.still_lapsed},
        "check_report": {"changed": rep2.changed, "lapsed": rep2.lapsed, "rejudged": rep2.rejudged, "still_lapsed": rep2.still_lapsed},
        "facts": [{**f, "value": json.loads(f["value"])} for f in q("SELECT * FROM facts ORDER BY id")],
        "verdicts": verdicts,
        "verdict_events": q("SELECT * FROM verdict_events ORDER BY id"),
        "watches": [{"verdict_id": v["id"], "context": v["context"], **c} for v in verdicts for c in v["expires_when"]],
        "calls": q("SELECT * FROM calls ORDER BY id"),
        "budget_ledger": q("SELECT * FROM budget_ledger ORDER BY id"),
    }
    (out / "airstack-demo-export.json").write_text(json.dumps(export, indent=2, ensure_ascii=False))
    print(f"{db.name}: {len(export['facts'])} facts, {len(verdicts)} verdicts, {len(export['verdict_events'])} events, "
          f"{len(export['watches'])} watches, {len(export['calls'])} calls")
    return export

if __name__ == "__main__":
    try:
        main(live="--live" in sys.argv, force="--force-new-live-run" in sys.argv)
    except PaidDataProtected as e:
        sys.exit(f"refused: {e}")
