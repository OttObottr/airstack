# spec: AS-274 AS-327
"""Builds data/airstack-market.db: the meeting-notes market, researched by Muse Spark from each vendor's own pages.

  code fetches each page (cached, conditional) -> shells are refused -> Muse `catalog` extracts facts with verbatim quotes
  (memoised: a second run costs nothing) -> code verifies every quote and value on the page -> admitted facts carry provenance.

Usage:  ../.venv/bin/python tools/build_market.py            # replay from the memo and page cache only: $0, no network for Muse
        ../.venv/bin/python tools/build_market.py --live     # real calls for inputs not yet in the memo, inside --cap (default $3)
Options: --limit N (pages), --cap DOLLARS, --refetch (conditional re-fetch of pages)"""
import argparse, json, sys
from airstack.budget import BudgetGuard, BudgetExceeded
from airstack.corpus import Corpus, chunks
from airstack.spark import FakeSpark, GuardedSpark, ReplayMiss, memo_key
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
DB = paths.MARKET_DB
LANE = "meeting-notes"
ENTITIES = {  # id: (name, maker, role in the market)
    "fireflies": ("Fireflies", "Fireflies.ai", "incumbent"), "otter": ("Otter", "Otter.ai", "incumbent"),
    "fathom": ("Fathom", "Fathom Video", "incumbent"), "tldv": ("tl;dv", "tldx Solutions", "incumbent"),
    "readai": ("Read AI", "Read AI", "incumbent"), "zoom": ("Zoom", "Zoom Communications", "platform"),
    "teams": ("Microsoft Teams", "Microsoft", "platform"),
}
PAGES = [  # (entity, kind, url): the vendor's own pages and its store listings
    ("fireflies", "home", "https://fireflies.ai/"), ("fireflies", "pricing", "https://fireflies.ai/pricing"),
    ("fireflies", "integrations", "https://fireflies.ai/integrations"), ("fireflies", "security", "https://fireflies.ai/security"),
    ("fireflies", "chrome", "https://chromewebstore.google.com/detail/fireflies-ai-meeting-note/meimoidfecamngeoanhnpdjjdcefoldn"),
    ("otter", "home", "https://otter.ai/"), ("otter", "pricing", "https://otter.ai/pricing"), ("otter", "integrations", "https://otter.ai/integrations"),
    ("otter", "chrome", "https://chromewebstore.google.com/detail/otterai-record-transcribe/bnmojkbbkkonlmlfgejehefjldooiedp"),
    ("fathom", "home", "https://fathom.ai/"), ("fathom", "pricing", "https://fathom.ai/pricing"), ("fathom", "integrations", "https://fathom.ai/integrations"),
    ("fathom", "chrome", "https://chromewebstore.google.com/detail/fathom-ai-note-taker-for/nhocmlminaplaendbabmoemehbpgdemn"),
    ("tldv", "home", "https://tldv.io/"), ("tldv", "integrations", "https://tldv.io/integrations/"),
    ("readai", "home", "https://read.ai/"), ("readai", "pricing", "https://read.ai/pricing"), ("readai", "integrations", "https://read.ai/integrations"),
    ("readai", "chrome", "https://chromewebstore.google.com/detail/read-ai/aiamjjeggglngiggkmmbnpnpeejjejaf"),
    ("zoom", "features", "https://www.zoom.com/en/products/ai-assistant/features/ai-note-taking/"), ("zoom", "pricing", "https://zoom.us/pricing"),
    ("teams", "help", "https://learn.microsoft.com/en-us/microsoftteams/intelligent-recap-calls-meetings"),
    ("teams", "help", "https://learn.microsoft.com/en-us/microsoftteams/enhanced-teams-experience"),
    ("teams", "help", "https://support.microsoft.com/en-us/teams/copilot/catch-up-on-meetings-with-microsoft-365-copilot-in-teams"),
]
# Platform pages get one focused question as a SECOND input (a new memo key, so nothing already paid for is repeated):
# what you already pay for decides the answer, so the plans and licenses that include AI meeting notes must be captured exactly.
PLATFORM_QUESTION = ("Which plans or licenses include AI meeting notes, summaries or recap? Put them in x.notes_plans, names exactly as written, "
                     "with the sentence that says so as the quote. If a plan has a limit (for example a number of meetings per month), "
                     "or in-person capture has terms, put those words in x.in_person_terms.")
PAGES += [(e, k + "-plans", u) for e, k, u in PAGES if e in ("zoom", "teams")]

def run(spark, store, corpus, now, pages=PAGES, refetch=False, fetch=None):
    rep = {"pages": 0, "shells": [], "calls": 0, "cached": 0, "produced": 0, "admitted": 0, "rejected": [], "stopped": None,
           "incomplete": False}
    for e, (name, maker, role) in ENTITIES.items():
        store.ensure_entity(e, kind=role, name=name, maker=maker, lane_id=LANE)
    for entity, kind, url in pages:
        have = corpus.c.execute("SELECT 1 FROM raw_items WHERE url=? AND status=200", (url,)).fetchone()
        page = corpus.fetch(url, now, fetch=fetch, kind=kind) if (refetch or not have) else _cached(corpus, url)
        rep["pages"] += 1
        if page["shell"]:
            rep["shells"].append(url); continue
        for i, text in enumerate(chunks(page["text"])):
            payload = {"product": ENTITIES[entity][0], "maker": ENTITIES[entity][1], "page_kind": kind, "page_url": url, "part": i + 1, "text": text}
            if kind.endswith("-plans"):
                payload["question"] = PLATFORM_QUESTION
            was_cached = corpus.get(memo_key("catalog", payload)) is not None
            try:
                res = spark.call("catalog", payload, tool=entity)
            except ReplayMiss:
                rep["rejected"].append((url, "call not in the offline memo")); rep["stopped"] = "replay_miss"; rep["incomplete"] = True
                for e in ENTITIES: spark.guard.end_tool(e)
                return rep
            except BudgetExceeded as ex:
                rep["stopped"] = f"{ex.reason}: stopped before {url}"; rep["incomplete"] = True
                for e in ENTITIES: spark.guard.end_tool(e)
                return rep
            except Exception as ex:                                                 # one bad page never stops the batch
                rep["rejected"].append((url, f"call failed: {type(ex).__name__}")); rep["incomplete"] = True; continue
            rep["cached" if was_cached else "calls"] += 1
            facts = res.data["facts"]
            rep["produced"] += len(facts)
            ok, bad = corpus.admit(entity, page, facts, res.call_id, now, kind)
            rep["admitted"] += len(ok)
            rep["rejected"] += [(url, f"{m}: {why}") for m, why in bad]
    for e in ENTITIES: spark.guard.end_tool(e)
    return rep

def _cached(corpus, url):
    r = corpus.c.execute("SELECT status, text, fetched_at FROM raw_items WHERE url=?", (url,)).fetchone()
    return {"url": url, "status": r[0], "text": r[1], "fetched_at": r[2], "cached": True, "shell": len(r[1] or "") < 500}

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--live", action="store_true"); a.add_argument("--limit", type=int); a.add_argument("--cap", default="3")
    a.add_argument("--refetch", action="store_true"); args = a.parse_args(argv)
    store = Store(str(DB)); corpus = Corpus(store); now = utcnow()
    if args.live:
        import preflight; preflight.load_env(ROOT / ".env")
        from airstack.spark import LiveSpark
        inner = LiveSpark()
    else:
        inner = FakeSpark({}, cost="0", replay_only=True)
    guard = BudgetGuard(store, utcnow, job_cap="0.50", day_cap=args.cap, total_cap=args.cap, tool_calls=40, tool_searches=0)
    spark = GuardedSpark(inner, store, guard, utcnow, memo=corpus)
    rep = run(spark, store, corpus, now, pages=PAGES[: args.limit] if args.limit else PAGES, refetch=args.refetch)
    rate = rep["admitted"] / rep["produced"] if rep["produced"] else 0
    print(json.dumps({**rep, "rejected": rep["rejected"][:40], "pass_rate": round(rate, 3)}, indent=1))
    return rep

if __name__ == "__main__":
    sys.exit(1 if main().get("incomplete") else 0)
