# spec: AS-080 AS-365
import os
import pytest
from airstack import paths
ROOT = paths.ROOT
# Scripts the tests start as child processes import `airstack` like this process does, installed or not (pyproject.toml `pythonpath`).
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend"), str(ROOT / "backend" / "tools"), *filter(None, [os.environ.get("PYTHONPATH")])])
from airstack.budget import BudgetGuard
from airstack.engine import Obs
from airstack.evaluate import evaluate
from airstack.spark import FakeSpark, GuardedSpark
from airstack.store import Store


def pytest_sessionstart(session):
    if not paths.SITE_DATA.exists():
        pytest.exit(f"The published datasets are not in {paths.SITE}. Data is not stored in the repository: run tools/data_pull.sh first.", returncode=2)


def pytest_collection_modifyitems(config, items):
    """Data is not in the repository (docs/OWNER.md). A fresh checkout fetches the published datasets (tools/data_pull.sh) but neither the
    private data (saved responses and databases: restore from tools/backup.sh). A test marked for
    data that is absent is skipped, with the reason; nothing else is ever skipped, and with the data present nothing is."""
    absent = {"private_data": (not paths.MARKET_DB.exists(), "needs the saved responses and databases in data/, which are not in the repository (restore from tools/backup.sh)")}
    for item in items:
        for name, (missing, why) in absent.items():
            if missing and item.get_closest_marker(name):
                item.add_marker(pytest.mark.skip(reason=why))

POST = "https://workspaceupdates.googleblog.com/2026/08/take-notes-with-me-for-in-person-meetings-is-now-available.html"
HELP_1 = "https://support.google.com/meet/answer/17020724"
HELP_2 = "https://support.google.com/meet/answer/14754931"
LANGS = ["English", "French", "German", "Italian", "Japanese", "Korean", "Portuguese", "Spanish"]
EDITIONS = ["Business Standard", "Business Plus", "Enterprise Standard", "Enterprise Plus", "Frontline Plus"]
T0, T_EVENT = "2026-08-01T12:00:00Z", "2026-08-13T18:00:00Z"   # event inside the 14-day freshness window

REQ_IN_PERSON = {"id": "in_person", "text": "Notes for in-person meetings", "all": [{"key": "meet.in_person_notes", "op": "eq", "value": True}]}
REQ_OUTPUT = {"id": "output", "text": "Summary and action items in a Doc", "all": [{"key": "meet.notes_output", "op": "eq", "value": "doc_summary_action_items_transcript"}]}
REQ_EN = {"id": "lang_en", "text": "English is a supported language", "all": [{"key": "meet.supported_languages", "op": "includes", "value": "English"}]}
REQ_EDITION = {"id": "edition", "text": "Seat holds Business Standard, a listed edition", "entitlement": "workspace:business_standard",
               "all": [{"key": "meet.listed_editions", "op": "includes", "value": "Business Standard"}]}
REQ_PLATFORM = {"id": "platform", "text": "Available on Android", "all": [{"key": "meet.in_person_notes_platforms", "op": "includes", "value": "Android"}]}
REQ_EDITION_STARTER = {"id": "edition", "text": "Seat holds Business Starter, a listed edition", "entitlement": "workspace:business_starter",
                       "all": [{"key": "meet.listed_editions", "op": "includes", "value": "Business Starter"}]}
SEAT_A = [REQ_IN_PERSON, REQ_PLATFORM, REQ_OUTPUT, REQ_EN, REQ_EDITION]      # an Android seat on Business Standard
SEAT_B = [REQ_EDITION_STARTER if r is REQ_EDITION else r for r in SEAT_A]    # the same seat on Business Starter, which Google doesn't list
ENT = ["workspace:business_standard"]
ENTS = {"A": ["workspace:business_standard"], "B": ["workspace:business_starter"]}
B_GAP = "Seat holds Business Starter, a listed edition"
PUBLIC_WATCH = [{"kind": "capability_gain", "text": "an already-owned platform gains in-person notes", "metric": "in_person_notes", "value": True, "scope": "*"}]

class Clock:
    def __init__(self, t=T0): self.t = t
    def __call__(self): return self.t
    def set(self, t): self.t = t

@pytest.fixture
def clock(): return Clock()
@pytest.fixture
def store(): return Store()

def recordings(*, label="capability_shock", material=True, confidence=0.9, judge_action=None, results=None):
    res = [{"url": HELP_2, "title": "Take notes for me", "snippet": "Supported languages: English, French, German...", "published": ""}] if results is None else results
    def judge(p):
        return {"action": judge_action or p["proposed_action"], "reason": f"Recorded reason ({p['context']}).", "confidence": confidence,
                "citations": [e["id"] for e in p["evidence"]]}
    return {"classify": {"label": label, "material": material, "rationale": "recorded"}, "search": {"results": res}, "judge": judge,
            "extract": {"facts": [{"metric": "description", "value_json": "\"recorded\"", "source_url": "https://example.com/a", "source_ts": "2026-11-01T00:00:00Z"}]}}

def make_spark(store, clock, *, rec=None, cost="0.001", search_executed=True, grounded=True, **guard_kw):
    fake = FakeSpark(rec or recordings(), cost=cost, search_executed=search_executed, grounded=grounded)
    return GuardedSpark(fake, store, BudgetGuard(store, clock, **guard_kw), clock), fake

def meet_before_obs(earlier_state=True):
    earlier = [Obs("meet", "in_person_notes", False, "illustrative.snapshot", "https://example.invalid/illustrative-earlier-state")] if earlier_state else []
    return earlier + [Obs("meet", "supported_languages", LANGS, "google.meet.help", HELP_2),
            Obs("meet", "notes_output", "doc_summary_action_items_transcript", "google.meet.help", HELP_1),
            Obs("meet", "listed_editions", EDITIONS, "workspace.updates", POST, "2026-08-13T17:50:38Z")]

def seed_before(store, t0=T0, earlier_state=True):
    for o in meet_before_obs(earlier_state):
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts, observed_at=t0)
    store.append_fact(entity_id="fireflies", metric="multi_language_mode", value={"status": "beta", "plans": ["Business", "Enterprise"]},
                      source="fireflies.kb", url="https://guide.fireflies.ai/articles/2585231364", source_ts=None, observed_at=t0)

def issue_seats(store, now=T0):
    ids = {}
    for seat, reqs in (("A", SEAT_A), ("B", SEAT_B)):
        ev = evaluate(store, "fireflies", reqs, ENTS[seat])
        v = store.put_verdict(entity_id="fireflies", context=f"seat:{seat}", action=ev.action, reason=f"Issued for seat {seat}.", depends_on=ev.depends_on,
                              expires_when=ev.expires_when, evidence=ev.evidence, uncovered=ev.uncovered, issued_at=now, requirements=reqs,
                              entitlements=ENTS[seat], visibility="public")
        ids[seat] = v.id
    return ids

def issue_public(store, now=T0):
    f = store.latest_fact("fireflies.multi_language_mode")
    from airstack.evaluate import evidence_entry
    return store.put_verdict(entity_id="fireflies", context="public", action="KEEP", reason="In-person notes still need a dedicated tool.",
                             depends_on={f.key: f.value_hash}, expires_when=PUBLIC_WATCH, evidence=[evidence_entry(f)], uncovered=[], issued_at=now,
                             visibility="public")

def meet_event_obs():
    return [Obs("meet", "in_person_notes", True, "workspace.updates", POST, "2026-08-13T17:50:38Z"),
            Obs("meet", "in_person_notes_platforms", ["Android"], "workspace.updates", POST, "2026-08-13T17:50:38Z")]

@pytest.fixture(autouse=True)
def _isolated_account_ledger(request, tmp_path, monkeypatch):
    """Tests never touch the real account ledger (~/.airstack). Only the opt-in live smoke test uses it."""
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv("AIRSTACK_ACCOUNT_LEDGER", str(tmp_path / "account-ledger.sqlite"))
    monkeypatch.setenv("AIRSTACK_STOP_FILE", str(tmp_path / "STOP"))
    monkeypatch.setenv("AIRSTACK_HARD_CEILING_USD", "9")       # private in production; tests use an isolated, arbitrary ceiling
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "9")        # production default is off; behaviour tests need explicit authorization
