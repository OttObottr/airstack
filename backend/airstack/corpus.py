# spec: AS-137 AS-140 AS-233 AS-274 AS-327 AS-355
"""The market corpus: fetched pages, the model memo, and the gate a fact must pass to exist.

Order, cheapest first: fetch once (conditional GET; a 304 costs nothing) -> refuse shells -> ask Muse `catalog` once per distinct
input (memo) -> CODE checks every quote on the page text, every list item on the page text, every number in its quote -> admit.
Muse never writes a fact directly; a fact exists only if code found its words on the page it came from."""
import hashlib, html, json, re
from .schemas import CATALOG_METRICS, PROFILE_METRICS

from airstack.fetch import UA, get as _get   # one honest name; robots.txt obeyed (AS-274)
SHELL_CHARS = 500                     # less readable text than this is a JavaScript shell or an error page: never sent to a model
CHUNK_CHARS = 15000                   # fits the request envelope with the system prompt and schema
MAX_CHUNKS = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_items(url TEXT PRIMARY KEY, status INTEGER, fetched_at TEXT, etag TEXT, last_modified TEXT,
  body_hash TEXT, text TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS model_memo(key TEXT PRIMARY KEY, role TEXT, call_ref TEXT, output_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS verifications(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, metric TEXT, value_json TEXT, quote TEXT, ok INTEGER, why TEXT,
  call_ref TEXT, checked_at TEXT, UNIQUE(url, metric, value_json, quote, call_ref));   -- one row per claim; a better checker updates it, the model's raw output stays in model_memo
CREATE TABLE IF NOT EXISTS rechecks(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, checked_at TEXT, status INTEGER, outcome TEXT, body_hash TEXT,
  quotes_total INTEGER, quotes_ok INTEGER, note TEXT);   -- the "re-checked" link of the chain of custody: append-only, one row per page per run
CREATE TABLE IF NOT EXISTS fact_provenance(fact_id INTEGER PRIMARY KEY, call_ref TEXT, quote TEXT, page_kind TEXT);
"""

def page_text(raw):
    """Readable text of an HTML page, line breaks kept at block boundaries."""
    s = re.sub(r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr|/section|/article)[^>]*>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return "\n".join(l for l in (re.sub(r"[ \t ]+", " ", l).strip() for l in s.splitlines()) if l)

def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()

class Corpus:
    def __init__(self, store):
        self.store, self.c = store, store._c
        self.c.executescript(SCHEMA)

    # ---- pages: fetched once, re-fetched conditionally, never deleted ----
    def fetch(self, url, now, fetch=None, kind="page"):
        old = self.c.execute("SELECT status, etag, last_modified, text, fetched_at FROM raw_items WHERE url=?", (url,)).fetchone()
        headers = {"User-Agent": UA, "Accept-Language": "en-US,en"}
        if old and old[1]: headers["If-None-Match"] = old[1]
        if old and old[2]: headers["If-Modified-Since"] = old[2]
        status, body, hdrs = (fetch or _get)(url, headers)
        if status == 304 and old:
            return {"url": url, "status": old[0], "text": old[3], "fetched_at": old[4], "cached": True, "shell": len(old[3] or "") < SHELL_CHARS}
        text = page_text(body) if status == 200 else ""
        self.c.execute("INSERT OR REPLACE INTO raw_items(url,status,fetched_at,etag,last_modified,body_hash,text,kind) VALUES(?,?,?,?,?,?,?,?)",
                       (url, status, now, hdrs.get("etag"), hdrs.get("last-modified"), hashlib.sha256(body.encode()).hexdigest(), text, kind))
        self.c.commit()
        return {"url": url, "status": status, "text": text, "fetched_at": now, "cached": False, "shell": status != 200 or len(text) < SHELL_CHARS}

    # ---- the memo GuardedSpark consults before it reserves a cent ----
    def get(self, key):
        with self.store._lock:                                              # one lock for every statement on this connection (threads share it)
            r = self.c.execute("SELECT output_json FROM model_memo WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None
    def put(self, key, out):
        with self.store._lock:
            self.c.execute("INSERT OR IGNORE INTO model_memo(key,role,call_ref,output_json,created_at) VALUES(?,?,?,?,datetime('now'))",
                           (key, "", out["call_ref"], json.dumps(out)))

    # ---- the gate ----
    def admit(self, entity, page, facts, call_ref, now, page_kind):
        """Returns (admitted, rejected). A fact is admitted only if code finds its quote on the page, and its value is supported there."""
        with self.store._lock:
            return self._admit(entity, page, facts, call_ref, now, page_kind)
    def _admit(self, entity, page, facts, call_ref, now, page_kind):
        text = norm(page["text"])
        out, bad = [], []
        for f in facts:
            ok, why, value = check(f, text)
            metric = f["metric"]
            if ok and isinstance(value, tuple):                                     # a derived metric (see check): ("x.integrations_count", 100)
                metric, value = value
            self.c.execute("""INSERT INTO verifications(url,metric,value_json,quote,ok,why,call_ref,checked_at) VALUES(?,?,?,?,?,?,?,?)
                              ON CONFLICT(url,metric,value_json,quote,call_ref) DO UPDATE SET ok=excluded.ok, why=excluded.why, checked_at=excluded.checked_at""",
                           (page["url"], f["metric"], f["value_json"], f["quote"], int(ok), why, call_ref, now))   # a replay re-checks; it doesn't re-count
            if not ok:
                bad.append((f["metric"], why)); continue
            same = [x for x in self.store.facts_for(entity) if x.metric == metric and x.url == page["url"] and x.value == value]
            fact = same[0] if same else self.store.append_fact(entity_id=entity, metric=metric, value=value, source="muse.catalog", url=page["url"],
                                                               source_ts=f.get("source_ts") or None, observed_at=page["fetched_at"])   # one row per (entity, metric, value, page)
            self.c.execute("INSERT OR IGNORE INTO fact_provenance(fact_id,call_ref,quote,page_kind) VALUES(?,?,?,?)", (fact.id, call_ref, f["quote"], page_kind))
            out.append(fact)
        return out, bad

CODE = re.compile(r"[{}]|=>|;\s*$|\bawait\b|\bimport\b|\bconst\b|\w\.\w+\(")

def failing_now(conn):
    """Claims admitted under OLDER rules that today's check() rejects, found by replaying the stored page text (free, no model).
    Public projections skip them with is_bad(); the stored rows stay as the record."""
    have = lambda t, col: col in {r[0] for r in conn.execute("SELECT name FROM pragma_table_info(?)", (t,))}
    bad = set()
    if not (have("raw_items", "text") and have("verifications", "quote")):
        return bad                                                                    # a bare test database: nothing to replay
    pages = {u: norm(t) for u, t in conn.execute("SELECT url, text FROM raw_items WHERE text IS NOT NULL")}
    for url, metric, vj, quote in conn.execute("SELECT url, metric, value_json, quote FROM verifications WHERE ok=1"):
        t = pages.get(url)
        if t is not None and not check({"metric": metric, "value_json": vj, "quote": quote}, t)[0]:
            bad.add((url, quote, metric))
    return bad

def is_bad(bad, url, quote, metric):
    """Not shown: rejected by today's check, or from a page whose terms or robots.txt don't allow it (AS-274)."""
    from airstack.fetch import published
    return (url, quote, metric) in bad or (metric == "x.integrations_count" and (url, quote, "x.integrations") in bad) or not published(url)

QUOTE_WORDS = 25

def check(f, text):
    """(ok, why, value). `text` is the normalised page text."""
    if f["metric"] not in CATALOG_METRICS and f["metric"] not in PROFILE_METRICS:
        return False, "metric not in the vocabulary", None
    q = norm(f["quote"])
    if len(q.split()) > QUOTE_WORDS:
        return False, f"quote longer than {QUOTE_WORDS} words", None                  # a short quote is evidence; a long one is copying
    if len(q) < 3 or q not in text:
        return False, "quote not found on the page", None
    try:
        v = json.loads(f["value_json"])
    except ValueError:
        v = f["value_json"].strip()                                                     # a bare value: shapes are repaired here, truth is checked against the page below
    m = f["metric"]
    LISTS = ("x.joins_meeting_apps", "x.devices", "x.integrations", "x.compliance", "x.plan_names", "x.notes_plans",
             "x.deployment", "x.platforms", "x.sdk_languages", "x.models_supported")
    if m in LISTS and isinstance(v, str):                                              # one name, or "A, B and C": split it; every piece must still appear on the page
        v = [x for x in re.split(r"\s*(?:,|;|\band\b|&)\s*", v) if x.strip()]
    if m in ("x.in_person_capture", "x.free_plan", "x.bot_free", "x.open_source") and isinstance(v, str) and v.lower() in ("true", "false"):
        v = v.lower() == "true"
    if m in ("x.languages_count", "x.store_users", "x.integrations_count", "x.founded_year") and isinstance(v, str) and v.replace(",", "").isdigit():
        v = int(v.replace(",", ""))
    if m == "x.integrations" and isinstance(v, int) and not isinstance(v, bool):        # "100+ apps": a count, not names
        return (True, "ok", ("x.integrations_count", v)) if str(v) in re.sub(r"\D", "", q) else (False, "the number is not in its quote", None)
    if m in LISTS:
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False, "expected a list of names", None
        kept = sorted({x.strip() for x in v if x.strip() and norm(x) in text})          # every name must appear on the page
        return (True, "ok", kept) if kept else (False, "no listed name appears on the page", None)
    if m in ("x.languages_count", "x.store_users", "x.integrations_count", "x.founded_year"):
        if isinstance(v, bool) or not isinstance(v, int):
            return False, "expected an integer", None
        digits = re.sub(r"\D", "", q)
        if m == "x.store_users" and "user" not in q:                                     # a ratings count is not a user count: the quote must say users
            return False, "the quote does not say users", None
        return (True, "ok", v) if str(v) in digits or f"{v:,}" in q else (False, "the number is not in its quote", None)
    if m in ("x.in_person_capture", "x.free_plan", "x.bot_free", "x.open_source"):
        if not isinstance(v, bool):
            return False, "expected true or false", None
        if m == "x.free_plan" and v is True:                                              # a free PLAN, not a trial and not one-time credits
            zero_a_month = re.search(r"\$\s?0\b", q) and re.search(r"/\s?mo|month|forever", q)           # "Forever $0 /mo", "$0 / month"
            if not (re.search(r"\bfree\b", q) or zero_a_month):
                return False, "the quote never says free or $0 a month (no credit card required is not a free plan)", None
            if re.search(r"trial|credits\b|credit\b(?!\s+card)", q) and not re.search(r"month|monthly|forever|always|\bplan\b|\btier\b", q):
                return False, "free credits or a trial, not a free plan", None
        return True, "ok", v
    if m == "x.what_it_does" and CODE.search(f["quote"]):
        return False, "not a description (code)", None                                    # a code fragment is not what the product does
    if m in ("x.what_it_does", "x.in_person_terms", "x.license", "x.pricing_basis", "x.customers_claimed"):
        return True, "ok", f["quote"].strip()                                            # the value IS the page's own words, whatever shape the model gave it
    if m == "x.store_rating":                                                           # {rating, count}, a bare 4.6, or "4.8 / 5"
        r = v.get("rating") if isinstance(v, dict) else v
        if isinstance(r, str):
            mm = re.match(r"\s*(\d(?:\.\d)?)", r); r = float(mm.group(1)) if mm else None
        if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 <= r <= 5:
            return False, "expected a rating out of 5", None
        if f"{r:g}" not in q:
            return False, "the rating is not in its quote", None
        count = str(v.get("count", "")).strip() if isinstance(v, dict) else ""
        return True, "ok", {"rating": float(r), "count": count}
    return False, "unhandled metric", None

def chunks(text, size=CHUNK_CHARS, limit=MAX_CHUNKS):
    out, cur = [], ""
    lines = (l[i:i + size] for l in text.splitlines() for i in range(0, max(len(l), 1), size))   # a page that ships its text as one long line still fits the envelope
    for line in lines:
        if len(cur) + len(line) + 1 > size and cur:
            out.append(cur); cur = ""
            if len(out) == limit:
                break
        cur += line + "\n"
    if cur and len(out) < limit:
        out.append(cur)
    return out
