# spec: AS-010 AS-012 AS-013 AS-020 AS-030 AS-044 AS-072 AS-280
"""SQLite store. Facts are append-only (triggers). Verdict CONTENT is immutable; only lifecycle columns move."""
import hashlib, json, sqlite3, threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from .config import VERDICT_WORDS, FRESH_DAYS
import re

def ident(name):
    """A table or column name for SQL that cannot take it as a bound parameter: a bare identifier or nothing. Every value is a ? parameter."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name):
        raise ValueError(f"not an SQL identifier: {name!r}")
    return f'"{name}"'

def dumps(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

def value_hash(key, value):
    """sha256 of 'key=<compact json>' — identical to what the page computes in the browser."""
    return hashlib.sha256(f"{key}={dumps(value)}".encode("utf-8")).hexdigest()

_FMT = "%Y-%m-%dT%H:%M:%SZ"
def utcnow():
    return datetime.now(timezone.utc).strftime(_FMT)
def add_days(ts, days):
    return (datetime.strptime(ts, _FMT) + timedelta(days=days)).strftime(_FMT)

class AppendOnlyError(Exception): pass
class VerdictContractError(ValueError): pass
class RetireRuleError(VerdictContractError): pass
class EvidenceError(VerdictContractError): pass

@dataclass(frozen=True)
class Fact:
    id: int; entity_id: str; metric: str; value: object; value_hash: str
    source: str; source_ts: object; observed_at: str; url: str; effective_at: object = None
    @property
    def key(self): return f"{self.entity_id}.{self.metric}"

@dataclass
class Verdict:
    id: int; entity_id: str; context: str; action: str; reason: str
    depends_on: dict; expires_when: list; evidence: list; uncovered: list
    status: str; issued_at: str; last_verified_at: str; fresh_until: str
    supersedes_id: object; call_ids: list; lapsed_at: object; superseded_at: object
    requirements: list = field(default_factory=list); entitlements: list = field(default_factory=list)
    counter_checked: bool = False
    judge_output: object = None
    visibility: str = "private"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, kind TEXT, name TEXT, maker TEXT, tier INTEGER DEFAULT 3, lane_id TEXT);
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, source TEXT NOT NULL, metric TEXT NOT NULL,
  value TEXT NOT NULL, value_hash TEXT NOT NULL, source_ts TEXT, observed_at TEXT NOT NULL, url TEXT NOT NULL, effective_at TEXT);
CREATE INDEX IF NOT EXISTS facts_key ON facts(entity_id, metric, id);
CREATE TRIGGER IF NOT EXISTS facts_no_update BEFORE UPDATE ON facts BEGIN SELECT RAISE(ABORT,'facts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS facts_no_delete BEFORE DELETE ON facts BEGIN SELECT RAISE(ABORT,'facts are append-only'); END;
CREATE TABLE IF NOT EXISTS verdicts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, context TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('BUILD','BUY','KEEP','RETIRE')), reason TEXT NOT NULL,
  depends_on TEXT NOT NULL, expires_when TEXT NOT NULL, evidence TEXT NOT NULL, uncovered TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('CURRENT','LAPSED','SUPERSEDED')),
  issued_at TEXT NOT NULL, last_verified_at TEXT NOT NULL, fresh_until TEXT NOT NULL, supersedes_id INTEGER,
  call_ids TEXT NOT NULL, lapsed_at TEXT, superseded_at TEXT, requirements TEXT NOT NULL, entitlements TEXT NOT NULL,
  counter_checked INTEGER NOT NULL DEFAULT 0, judge_output TEXT, visibility TEXT NOT NULL DEFAULT 'private');
CREATE UNIQUE INDEX IF NOT EXISTS one_successor_per_verdict ON verdicts(supersedes_id) WHERE supersedes_id IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS verdicts_immutable BEFORE UPDATE ON verdicts WHEN
  OLD.action IS NOT NEW.action OR OLD.reason IS NOT NEW.reason OR OLD.depends_on IS NOT NEW.depends_on OR
  OLD.expires_when IS NOT NEW.expires_when OR OLD.evidence IS NOT NEW.evidence OR OLD.uncovered IS NOT NEW.uncovered OR
  OLD.issued_at IS NOT NEW.issued_at OR OLD.entity_id IS NOT NEW.entity_id OR OLD.context IS NOT NEW.context OR
  OLD.supersedes_id IS NOT NEW.supersedes_id OR OLD.call_ids IS NOT NEW.call_ids OR OLD.requirements IS NOT NEW.requirements OR
  OLD.entitlements IS NOT NEW.entitlements OR OLD.judge_output IS NOT NEW.judge_output OR OLD.visibility IS NOT NEW.visibility
  BEGIN SELECT RAISE(ABORT,'verdict content is immutable'); END;
CREATE TRIGGER IF NOT EXISTS verdicts_no_delete BEFORE DELETE ON verdicts BEGIN SELECT RAISE(ABORT,'verdicts are never deleted'); END;
CREATE TABLE IF NOT EXISTS calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, model TEXT, effort TEXT, in_tok INTEGER, out_tok INTEGER, cached_tok INTEGER,
  latency_ms INTEGER, cost TEXT, request_json TEXT, response_json TEXT, ts TEXT, tool TEXT, kind TEXT, call_ref TEXT, search_executed INTEGER);
CREATE TABLE IF NOT EXISTS sync_checks(key TEXT PRIMARY KEY, last_checked TEXT);
CREATE TABLE IF NOT EXISTS budget_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT, reserved TEXT NOT NULL, spent TEXT, state TEXT NOT NULL, at TEXT NOT NULL, job_id TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, tool TEXT NOT NULL, purpose TEXT NOT NULL, dedupe_key TEXT, state TEXT NOT NULL, created_at TEXT NOT NULL, closed_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_job_per_key ON jobs(dedupe_key) WHERE state='OPEN' AND dedupe_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS verdict_events(id INTEGER PRIMARY KEY AUTOINCREMENT, verdict_id INTEGER NOT NULL, event TEXT NOT NULL, at TEXT NOT NULL, cause TEXT);
CREATE TRIGGER IF NOT EXISTS verdict_events_no_update BEFORE UPDATE ON verdict_events BEGIN SELECT RAISE(ABORT,'verdict events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS verdict_events_no_delete BEFORE DELETE ON verdict_events BEGIN SELECT RAISE(ABORT,'verdict events are append-only'); END;
"""

class Store:
    def __init__(self, path=":memory:"):
        self._c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._c.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._c.executescript(SCHEMA)

    def _q(self, sql, params=()):
        with self._lock:
            return self._c.execute(sql, params)

    # ---- entities
    def ensure_entity(self, id, kind="tool", name=None, maker=None, tier=3, lane_id=None):
        self._q("INSERT OR IGNORE INTO entities(id,kind,name,maker,tier,lane_id) VALUES(?,?,?,?,?,?)", (id, kind, name or id, maker, tier, lane_id))
    def entity(self, id):
        r = self._q("SELECT * FROM entities WHERE id=?", (id,)).fetchone()
        return dict(r) if r else None

    # ---- facts (append-only)
    @staticmethod
    def _fact(r):
        return Fact(r["id"], r["entity_id"], r["metric"], json.loads(r["value"]), r["value_hash"], r["source"], r["source_ts"], r["observed_at"], r["url"], r["effective_at"])
    def append_fact(self, *, entity_id, metric, value, source, url, source_ts, observed_at, effective_at=None):
        if not url:
            raise EvidenceError("a fact needs a source URL")
        key = f"{entity_id}.{metric}"
        self.ensure_entity(entity_id)
        cur = self._q("INSERT INTO facts(entity_id,source,metric,value,value_hash,source_ts,observed_at,url,effective_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (entity_id, source, metric, dumps(value), value_hash(key, value), source_ts, observed_at, url, effective_at))
        return self._fact(self._q("SELECT * FROM facts WHERE id=?", (cur.lastrowid,)).fetchone())
    def update_fact(self, fact_id, **cols):
        try:
            known = {r[0] for r in self._q("SELECT name FROM pragma_table_info('facts')")}
            if not cols or set(cols) - known:
                raise ValueError(f"unknown fact columns: {sorted(set(cols) - known)}")
            sets = ",".join(f"{ident(k)}=?" for k in cols)
            self._q(f"UPDATE facts SET {sets} WHERE id=?", (*cols.values(), fact_id))  # noqa: S608 (column names checked against the table, values bound)
        except sqlite3.DatabaseError as e:
            raise AppendOnlyError(str(e)) from e
        raise AppendOnlyError("update unexpectedly succeeded")
    def delete_fact(self, fact_id):
        try:
            self._q("DELETE FROM facts WHERE id=?", (fact_id,))
        except sqlite3.DatabaseError as e:
            raise AppendOnlyError(str(e)) from e
        raise AppendOnlyError("delete unexpectedly succeeded")
    def get_fact(self, fid):
        r = self._q("SELECT * FROM facts WHERE id=?", (fid,)).fetchone()
        return self._fact(r) if r else None
    def latest_fact(self, key, as_of=None):
        ent, _, metric = key.partition(".")
        r = self._q("SELECT * FROM facts WHERE entity_id=? AND metric=? AND observed_at<=? ORDER BY id DESC LIMIT 1",
                    (ent, metric, as_of or "9999-12-31T23:59:59Z")).fetchone()
        return self._fact(r) if r else None
    def latest_facts(self, as_of=None):
        rows = self._q("""SELECT f.* FROM facts f JOIN (SELECT entity_id, metric, MAX(id) mid FROM facts WHERE observed_at<=?
                          GROUP BY entity_id, metric) m ON f.id=m.mid""", (as_of or "9999-12-31T23:59:59Z",)).fetchall()
        return {f.key: f for f in map(self._fact, rows)}
    def facts_for(self, entity_id):
        return [self._fact(r) for r in self._q("SELECT * FROM facts WHERE entity_id=? ORDER BY id", (entity_id,)).fetchall()]
    def facts_since(self, ts):
        return [self._fact(r) for r in self._q("SELECT * FROM facts WHERE observed_at>? ORDER BY id", (ts,)).fetchall()]
    def last_polled(self, key):
        r = self._q("SELECT last_checked FROM sync_checks WHERE key=?", (key,)).fetchone()
        return r["last_checked"] if r else None
    def touch_check(self, key, now):
        self._q("INSERT INTO sync_checks(key,last_checked) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET last_checked=excluded.last_checked", (key, now))

    # ---- verdicts
    @staticmethod
    def _verdict(r):
        j = json.loads
        return Verdict(r["id"], r["entity_id"], r["context"], r["action"], r["reason"], j(r["depends_on"]), j(r["expires_when"]),
                       j(r["evidence"]), j(r["uncovered"]), r["status"], r["issued_at"], r["last_verified_at"], r["fresh_until"],
                       r["supersedes_id"], j(r["call_ids"]), r["lapsed_at"], r["superseded_at"], j(r["requirements"]),
                       j(r["entitlements"]), bool(r["counter_checked"]), j(r["judge_output"]) if r["judge_output"] else None, r["visibility"])
    def put_verdict(self, *, entity_id, context, action, reason, depends_on, expires_when, evidence, uncovered, issued_at,
                    supersedes_id=None, call_ids=(), requirements=(), entitlements=(), counter_checked=False, fresh_days=FRESH_DAYS, judge_output=None,
                    visibility="private", _in_txn=False):
        if action not in VERDICT_WORDS:
            raise VerdictContractError(f"action must be one of {VERDICT_WORDS}")
        if not (reason or "").strip():
            raise VerdictContractError("a verdict needs a decisive reason")
        if not evidence:
            raise EvidenceError("a verdict needs at least one piece of evidence")
        for e in evidence:
            if not e.get("url") or not e.get("ts"):
                raise EvidenceError(f"every evidence row needs a source URL and a timestamp: {e}")
        if action == "RETIRE" and uncovered:
            raise RetireRuleError("RETIRE requires every declared requirement to be covered")
        self.ensure_entity(entity_id)
        d = dumps
        cur = self._q("""INSERT INTO verdicts(entity_id,context,action,reason,depends_on,expires_when,evidence,uncovered,status,issued_at,
                         last_verified_at,fresh_until,supersedes_id,call_ids,requirements,entitlements,counter_checked,judge_output,visibility)
                         VALUES(?,?,?,?,?,?,?,?,'CURRENT',?,?,?,?,?,?,?,?,?,?)""",
                      (entity_id, context, action, reason, d(depends_on), d(list(expires_when)), d(list(evidence)), d(list(uncovered)),
                       issued_at, issued_at, add_days(issued_at, fresh_days), supersedes_id, d(list(call_ids)), d(list(requirements)),
                       d(list(entitlements)), int(counter_checked), d(judge_output) if judge_output else None, visibility))
        self._event(cur.lastrowid, "PUBLISHED", issued_at, f"supersedes {supersedes_id}" if supersedes_id else "first issue")
        return self.get_verdict(cur.lastrowid)
    def _event(self, vid, event, at, cause=""):
        self._q("INSERT INTO verdict_events(verdict_id,event,at,cause) VALUES(?,?,?,?)", (vid, event, at, cause))
    def events(self, vid):
        return [dict(r) for r in self._q("SELECT event,at,cause FROM verdict_events WHERE verdict_id=? ORDER BY id", (vid,)).fetchall()]
    def max_fact_id(self):
        return self._q("SELECT COALESCE(MAX(id),0) m FROM facts").fetchone()["m"]
    def get_verdict(self, vid):
        r = self._q("SELECT * FROM verdicts WHERE id=?", (vid,)).fetchone()
        return self._verdict(r) if r else None
    def verdicts(self, entity_id=None, context=None, status=None, visibility=None):
        sql, p = "SELECT * FROM verdicts WHERE 1=1", []
        for col, val in (("entity_id", entity_id), ("context", context), ("status", status), ("visibility", visibility)):
            if val is not None:
                sql += f" AND {col}=?"; p.append(val)
        return [self._verdict(r) for r in self._q(sql + " ORDER BY id", p).fetchall()]
    def lapse_verdict(self, vid, now, cause=""):
        if self._q("UPDATE verdicts SET status='LAPSED', lapsed_at=? WHERE id=? AND status='CURRENT'", (now, vid)).rowcount:
            self._event(vid, "LAPSED", now, cause)
    def supersede(self, old_id, new_id, now):
        self._q("UPDATE verdicts SET status='SUPERSEDED', superseded_at=? WHERE id=?", (now, old_id))
        self._event(old_id, "SUPERSEDED", now, f"by {new_id}")
    def publish_successor(self, old_id, is_still_valid, **fields):
        """ONE transaction: re-check validity, insert the revision, supersede the predecessor (compare-and-swap).
        Returns the new verdict, or None if the predecessor is no longer LAPSED, already has a successor, or inputs moved."""
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")
            try:
                old = self._q("SELECT status FROM verdicts WHERE id=?", (old_id,)).fetchone()
                if not old or old["status"] != "LAPSED" or self.has_successor(old_id) or not is_still_valid():
                    self._c.execute("ROLLBACK"); return None
                new = self.put_verdict(supersedes_id=old_id, **fields)
                if self._q("UPDATE verdicts SET status='SUPERSEDED', superseded_at=? WHERE id=? AND status='LAPSED'", (fields["issued_at"], old_id)).rowcount != 1:
                    self._c.execute("ROLLBACK"); return None
                self._event(old_id, "SUPERSEDED", fields["issued_at"], f"by {new.id}")
                self._c.execute("COMMIT")
                return new
            except Exception:
                self._c.execute("ROLLBACK"); raise
    def has_successor(self, vid):
        return self._q("SELECT 1 FROM verdicts WHERE supersedes_id=?", (vid,)).fetchone() is not None
    def verdict_as_of(self, entity_id, context, as_of_ts, visibility=None):
        """The verdict revision AirStack had RECORDED at that moment (a reconstruction, not memory)."""
        r = self._q("SELECT * FROM verdicts WHERE entity_id=? AND context=? AND issued_at<=? AND (? IS NULL OR visibility=?) ORDER BY issued_at DESC, id DESC LIMIT 1",
                    (entity_id, context, as_of_ts, visibility, visibility)).fetchone()
        if not r:
            return None, None
        v = self._verdict(r)
        status = "LAPSED" if (v.lapsed_at and v.lapsed_at <= as_of_ts) else "CURRENT"
        return v, status

    # ---- calls log
    def log_call(self, **c):
        self._q("""INSERT INTO calls(role,model,effort,in_tok,out_tok,cached_tok,latency_ms,cost,request_json,response_json,ts,tool,kind,call_ref,search_executed)
                   VALUES(:role,:model,:effort,:in_tok,:out_tok,:cached_tok,:latency_ms,:cost,:request_json,:response_json,:ts,:tool,:kind,:call_ref,:search_executed)""", c)
    def _committed(self, job_id=None, day=None):
        if job_id is not None:
            rows = self._q("SELECT reserved, spent, state FROM budget_ledger WHERE job_id=?", (job_id,)).fetchall()
        elif day is not None:
            rows = self._q("SELECT reserved, spent, state FROM budget_ledger WHERE at LIKE ?", (day + "%",)).fetchall()
        else:
            rows = self._q("SELECT reserved, spent, state FROM budget_ledger").fetchall()
        return sum((Decimal(r["spent"]) if r["state"] == "SETTLED" else Decimal(r["reserved"]) for r in rows), Decimal(0))
    def spent_today(self, day):
        """Settled spend plus OPEN reservations: money that may already be committed counts as spent."""
        return self._committed(day=day)
    def reserve(self, *, tool, est, now, day_cap, total_cap, job_id=None, job_cap=None):
        """Atomically check headroom and reserve worst-case cost. Two workers can't both spend the same headroom.
        Committed money = settled spend + OPEN and UNCERTAIN reservations, at the job, the day and the lifetime level."""
        from .budget import BudgetExceeded
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")
            try:
                if self.paused():
                    raise BudgetExceeded("paused", self.get_setting("paused_reason") or "paid work is paused")
                if job_id is not None and job_cap is not None and self._committed(job_id=job_id) + est > job_cap:
                    raise BudgetExceeded("job_cap", "this job would exceed its cap")
                if self._committed(day=now[:10]) + est > day_cap:
                    raise BudgetExceeded("day_cap", "today would exceed its cap")
                if self._committed() + est > total_cap:
                    raise BudgetExceeded("total_cap", "lifetime Spark spend would exceed its cap")
                rid = self._c.execute("INSERT INTO budget_ledger(tool,reserved,state,at,job_id) VALUES(?,?,'OPEN',?,?)", (tool, str(est), now, job_id)).lastrowid
                self._c.execute("COMMIT")
                return rid
            except Exception:
                self._c.execute("ROLLBACK")
                raise
    def settle(self, rid, spent):
        self._q("UPDATE budget_ledger SET spent=?, state='SETTLED' WHERE id=?", (str(spent), rid))
    def mark_uncertain(self, rid):
        """The provider may have billed us: keep the full reservation counted until someone reconciles it."""
        self._q("UPDATE budget_ledger SET state='UNCERTAIN' WHERE id=?", (rid,))
    def reconcile(self, rid, spent):
        self._q("UPDATE budget_ledger SET spent=?, state='SETTLED' WHERE id=? AND state='UNCERTAIN'", (str(spent), rid))
    def ledger(self):
        return [dict(r) for r in self._q("SELECT * FROM budget_ledger ORDER BY id").fetchall()]
    # ---- durable jobs
    def open_job(self, *, tool, purpose, now, dedupe_key=None):
        import uuid
        jid = uuid.uuid4().hex
        try:
            self._q("INSERT INTO jobs(id,tool,purpose,dedupe_key,state,created_at) VALUES(?,?,?,?,'OPEN',?)", (jid, tool, purpose, dedupe_key, now))
        except sqlite3.IntegrityError as e:
            from .budget import BudgetExceeded
            raise BudgetExceeded("duplicate_job", f"an identical job is already open: {dedupe_key}") from e
        return jid
    def close_job(self, jid, now):
        self._q("UPDATE jobs SET state='CLOSED', closed_at=? WHERE id=? AND state='OPEN'", (now, jid))
    # ---- pause switch: any cost-bound breach stops all paid work until a person resumes it
    def get_setting(self, key):
        r = self._q("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None
    def set_setting(self, key, value):
        self._q("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    def paused(self):
        return self.get_setting("paid_paused") == "1"
    def pause(self, reason):
        self.set_setting("paid_paused", "1"); self.set_setting("paused_reason", reason)
    def resume(self):
        self.set_setting("paid_paused", "0")
    def spent_total(self):
        return self._committed()
    def calls(self, limit=100):
        return [dict(r) for r in self._q("SELECT * FROM calls ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

