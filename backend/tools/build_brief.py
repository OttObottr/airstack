# spec: AS-350
"""Today's brief: a few plain sentences written by Muse Wonder from facts AirStack already computed (movers against their own
recent level, coverage, registry agreement), each sentence citing the facts it uses. Code checks every number in every sentence
against the facts it cites, and refuses dollar amounts, unknown citations and banned words; a brief that fails is not published.
One call a day, memoised on its exact facts (a re-run of the same facts costs nothing).
The fact contract (AS-350): each number in a sentence is tied to a number in a fact it cites, with the same value, its unit (% or the
words after it), its direction (+ or -, written as a sign or a word such as rose or below; a count has none) and its subject (the tool
the fact is about, the cited tool named last before the number). A sentence that fails is withheld with why, never with its numbers;
the brief is not published when its headline fails or nothing is left.

Usage:  ../.venv/bin/python tools/build_brief.py                      # replay: $0 (fails if today's facts were never written up)
        ../.venv/bin/python tools/build_brief.py --recheck            # $0: hold the stored brief to the contract again, from its own facts
        ../.venv/bin/python tools/build_brief.py --live --cap 30      # one Muse Wonder call, reserved in the account ledger first"""
import argparse, json, re, sys
from datetime import date
from airstack.budget import BudgetGuard
from airstack.config import ROLE_MODELS
from airstack.corpus import Corpus
from airstack.files import atomic_write_text
from airstack.spark import FakeSpark, GuardedSpark
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
OUT = paths.BRIEF
BANNED = re.compile(r"[$€£]|\bseats?\b|\bguarantee|\bwill (?:rise|fall|grow|keep)", re.I)

def facts():
    """The day's facts, each a short sentence with its numbers, and the tool it is about when there is one."""
    site, market = paths.read_js(paths.SITE_DATA), paths.read_js(paths.MARKET_DATA)
    chain = json.loads(paths.CHAIN_DATA.read_text()).get("summary", {})
    rows = market["movers"]["rows"]
    pct = lambda x: f"{x:+.1f}%"
    D = site.get("dir") or {"products": 0, "orgs": 0, "types": 0}
    out = [{"text": f"{len(site['index'])} tools are tracked: {len(site['lanes'])} developer and AI lanes and {len(site.get('cats', []))} business software categories."},
           {"text": f"The directory lists {D['products']:,} more software products and {D['orgs']:,} organizations that make them, from Wikidata, across {D['types']:,} types of software."},
           {"text": f"{len(market['profiles']):,} products have facts from their own pages; {market['fleet']['passed']:,} quotes were found on those pages by code."},
           {"text": f"{chain.get('registry_second_record', 0)} claims match the vendor's own registry record and {chain.get('registry_disputed', 0)} are disputed by one."}]
    solid = sorted([r for r in rows if r["dl"]["delta"] is not None and r["dl"]["value"] >= 5000 and r["dl"].get("vsBase") is not None and r["dl"]["vsBase"] >= 0],
                   key=lambda r: -r["dl"]["delta"])[:5]
    rebounds = sorted([r for r in rows if r["dl"]["delta"] is not None and r["dl"]["delta"] > 0 and r["dl"].get("vsBase") is not None and r["dl"]["vsBase"] < 0],
                      key=lambda r: -r["dl"]["delta"])[:3]
    for r in solid:
        out.append({"tool": r["id"], "text": f"{r['name']} ({r['laneName']}): {r['dl']['value']:,} {r['dl']['registry']} downloads in the last 7 days, "
                                              f"{pct(r['dl']['delta'])} on the week before and {pct(r['dl']['vsBase'])} against its own 4-week level."})
    for r in rebounds:
        out.append({"tool": r["id"], "text": f"{r['name']} ({r['laneName']}): {pct(r['dl']['delta'])} on the week before, but {pct(r['dl']['vsBase'])} against its own "
                                              f"4-week level: a rebound, not growth."})
    return {f"d{i + 1}": f for i, f in enumerate(out)}

CLAIM = re.compile(r"(?<![\w.])([+\-−]?)(\d[\d,]*(?:\.\d+)?)(%?)")     # a sign only where it starts a word: the 4 in "4-week" or "GPT-4" has none
UNIT = re.compile(r"[^\d,.;:!?()]*")                                       # a number's unit runs to the next punctuation or number
FILLER = {"a", "an", "the", "and", "or", "of", "in", "on", "to", "by", "for", "its", "their", "more", "than", "are", "is", "was", "were", "over", "about"}
UP = {"up", "rose", "rise", "rises", "rising", "gained", "gain", "gains", "grew", "grow", "grows", "growth", "increased", "increase", "higher", "above", "jumped", "climbed"}
DOWN = {"down", "fell", "fall", "falls", "falling", "dropped", "drop", "drops", "declined", "decline", "lower", "below", "under", "shrank", "slipped"}

def words(s):
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 1 and w not in FILLER]

def claims(text):
    """Each number in a sentence: its value, its unit, the sign written on it, and the direction it is given (sign, else the nearest of
    the two words before or after it that says up or down)."""
    for m in CLAIM.finditer(text):
        before, after = re.findall(r"[a-z]+", text[:m.start()].lower())[::-1][:2], re.findall(r"[a-z]+", text[m.end():].lower())[:2]
        near = [w for pair in zip(before + [""] * 2, after + [""] * 2) for w in pair]
        sign = m[1].replace("−", "-") or None
        yield {"n": m[2].replace(",", ""), "at": m.start(), "unit": "%" if m[3] else words(UNIT.match(text, m.end()).group()), "sign": sign,
               "dir": sign or next(("+" if w in UP else "-" for w in near if w in UP | DOWN), None)}

def owner(low, at, names):
    """The tool a number belongs to: of the names given, the one written last before it (a longer name wins over one it contains)."""
    found = [(low.rfind(n, 0, at) + len(n), len(n), n) for n in names if n in low[:at]]
    return max(found)[2] if found else None

def problems(text, cites, F, where="the facts it cites"):
    """Why one sentence may not be published (empty = publishable): each number must be tied to a number in a fact it cites with the
    same value, unit and direction, written after that fact's subject and after no other cited tool."""
    unknown = [c for c in cites if c not in F]
    if unknown:
        return [f"cites unknown facts {unknown}"]
    name = lambda f: F[f]["text"].split(" (")[0].lower()
    low, names, bad = text.lower(), {name(f) for f in cites if F[f].get("tool")}, []
    for c in claims(text):
        unit, who = c["unit"] if c["unit"] == "%" else (c["unit"] or [None])[0], owner(low, c["at"], names)
        misses = [[a for a, ok in (("unit", unit == x["unit"] or (x["unit"] != "%" and unit in x["unit"])),
                                   ("direction", c["dir"] == x["sign"] if x["sign"] else not c["dir"]),
                                   ("subject", not F[f].get("tool") or who == name(f))) if not ok]
                  for f in cites for x in claims(F[f]["text"]) if x["n"] == c["n"]]
        if not misses:
            bad.append(f"{c['n']} is not in {where}")
        elif all(misses):
            bad.append(f"{c['n']} does not name its {' or '.join(min(misses, key=len))}")
    if BANNED.search(text):
        bad.append("banned wording")
    return bad

def check(brief, F):
    """Every reason the brief or one of its sentences may not be published (empty = all publishable)."""
    return ([f"headline: {r}" for r in problems(brief["headline"], list(F), F, "any fact")]
            + [f"item {i}: {r}" for i, it in enumerate(brief["items"], 1) for r in problems(it["text"], it["cites"], F)])

def publish(B, F, note=""):
    """Write data/brief.json with only the sentences that hold to the contract; the rest are withheld with why (neither their text nor
    their numbers are kept: the file ships in the page data). Nothing is written when the headline fails or no sentence is left."""
    head = [f"headline: {r}" for r in problems(B["headline"], list(F), F, "any fact")]
    keep, held = [], list(B.get("withheld", []))
    for it in B["items"]:
        why = problems(it["text"], it["cites"], F)
        if why:
            held.append({"cites": it["cites"], "why": [CLAIM.sub("a number", w) for w in why]})
        else:
            keep.append(it)
    if head or not keep:
        print("NOT PUBLISHED:\n  " + "\n  ".join(head + [w for h in held for w in h["why"]] or ["no sentence holds to the fact contract"])); return 1
    atomic_write_text(OUT, json.dumps({**{k: B[k] for k in ("date", "model", "call_ref", "headline")}, "items": keep, "facts": F,
                                      **({"withheld": held} if held else {})}, indent=1, ensure_ascii=False) + "\n")
    print(f"data/brief.json: {len(keep)} items published, {len(held)} withheld; every number tied to a cited fact's value, unit, direction and subject{note}")
    return 0

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--live", action="store_true"); a.add_argument("--cap", default="30"); a.add_argument("--recheck", action="store_true")
    args = a.parse_args(argv)
    if args.recheck:                                                       # no call, no cost: the stored brief against the facts it was written from
        B = json.loads(OUT.read_text()); return publish(B, B["facts"])
    F = facts()
    payload = {"date": date.today().isoformat(), "facts": [{"id": k, "text": v["text"]} for k, v in F.items()]}
    store = Store(str(paths.MARKET_DB)); corpus = Corpus(store)
    if args.live:
        import preflight; preflight.load_env(ROOT / ".env")
        from airstack.spark import LiveSpark
        inner = LiveSpark()
    else:
        inner = FakeSpark({}, cost="0", replay_only=True)
    guard = BudgetGuard(store, utcnow, job_cap="0.50", day_cap=args.cap, total_cap=args.cap, tool_calls=2, tool_searches=0)
    spark = GuardedSpark(inner, store, guard, utcnow, memo=corpus)
    try:
        res = spark.call("brief", payload, tool="brief")
    finally:
        guard.end_tool("brief")
    return publish({"date": payload["date"], "model": ROLE_MODELS["brief"], "call_ref": res.call_id, **res.data}, F, f" ({res.cost} this run)")

if __name__ == "__main__":
    sys.exit(main())
