# spec: AS-027
"""Account-wide authorization and reservations for maintainer-initiated model work."""
import os, sqlite3, threading
from decimal import Decimal
from pathlib import Path
from .budget import BudgetExceeded

DEFAULT_LEDGER = Path.home() / ".airstack" / "meta-account-ledger.sqlite"
STOP_FILE = Path.home() / ".airstack" / "STOP"

class AccountCapReached(BudgetExceeded):
    """The account ledger did not authorize a call."""

def _positive_env(name):
    try:
        value = Decimal(os.environ.get(name, ""))
    except Exception:
        return Decimal(0)
    return value if value.is_finite() and value > 0 else Decimal(0)

def private_ceiling():
    """Return the off-repository account ceiling, or zero when unset."""
    return _positive_env("AIRSTACK_HARD_CEILING_USD")

def account_cap():
    """The authorized spend for this run, bounded by the separate private ceiling. Either missing setting means zero."""
    return min(private_ceiling(), _positive_env("AIRSTACK_ACCOUNT_CAP_USD"))

class AccountGuard:
    def __init__(self, path=None, stop_file=None):
        self.path = Path(path or os.environ.get("AIRSTACK_ACCOUNT_LEDGER") or DEFAULT_LEDGER)
        self.stop_file = Path(stop_file or os.environ.get("AIRSTACK_STOP_FILE") or STOP_FILE)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None, timeout=30)
        self._lock = threading.RLock()
        self._c.executescript("""
            CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
              role TEXT NOT NULL, reserved TEXT NOT NULL, spent TEXT, state TEXT NOT NULL, ref TEXT);
            CREATE TABLE IF NOT EXISTS stops(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), reason TEXT);
            CREATE TABLE IF NOT EXISTS clears(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), reason TEXT NOT NULL,
              through INTEGER NOT NULL);""")

    def committed(self):
        """Return reserved or reported cost, whichever is higher, for every call."""
        rows = self._c.execute("SELECT reserved, spent FROM ledger").fetchall()
        return sum((max(Decimal(r), Decimal(s or 0)) for r, s in rows), Decimal(0))

    def stopped(self):
        """The STOP file, or any recorded stop the owner has not cleared."""
        return self.stop_file.exists() or self._c.execute(
            "SELECT 1 FROM stops WHERE id > (SELECT COALESCE(MAX(through), 0) FROM clears)").fetchone() is not None

    def clear(self, reason):
        """Resume processing with an auditable reason."""
        if not str(reason or "").strip():
            raise ValueError("a clear needs the owner's reason")
        self._c.execute("INSERT INTO clears(reason, through) SELECT ?, COALESCE(MAX(id), 0) FROM stops", (reason,))

    def stop(self, reason):
        self._c.execute("INSERT INTO stops(reason) VALUES(?)", (reason,))

    def reserve(self, role, maximum):
        maximum = Decimal(maximum)
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")                  # atomic across processes sharing this file
            try:
                cap = account_cap()                              # one immutable authorization value for this transaction
                if self.stopped():
                    raise AccountCapReached("stopped", "live calls are stopped (STOP file or a recorded overrun)")
                if cap <= 0:                                     # off means off, whatever a price or an estimate says
                    raise AccountCapReached("account_cap", "live research is off (cap $0): set AIRSTACK_ACCOUNT_CAP_USD for this run")
                if not maximum.is_finite() or maximum <= 0:
                    raise AccountCapReached("bad_estimate", f"invalid reservation: {maximum}")
                if self.committed() + maximum > cap:
                    raise AccountCapReached("account_cap", "would pass this run's private account authorization")
                rid = self._c.execute("INSERT INTO ledger(role,reserved,state) VALUES(?,?,'OPEN')", (role, str(maximum))).lastrowid
                self._c.execute("COMMIT")
                return rid
            except Exception:
                self._c.execute("ROLLBACK")
                raise

    def settle(self, rid, spent, ref=""):
        """Record reported cost and stop new work when it exceeds the reservation."""
        with self._lock:
            self._c.execute("BEGIN IMMEDIATE")
            try:
                self._c.execute("UPDATE ledger SET spent=?, state='SETTLED', ref=? WHERE id=?", (str(spent), ref, rid))
                reserved = self._c.execute("SELECT reserved FROM ledger WHERE id=?", (rid,)).fetchone()
                if reserved and Decimal(str(spent)) > Decimal(reserved[0]):
                    self.stop(f"call {rid} ({ref}) reported {spent} > its reserved maximum {reserved[0]}")
                self._c.execute("COMMIT")
            except Exception:
                self._c.execute("ROLLBACK")
                raise

    def uncertain(self, rid):
        self._c.execute("UPDATE ledger SET state='UNCERTAIN' WHERE id=?", (rid,))

    def rows(self):
        return self._c.execute("SELECT id, at, role, reserved, spent, state, ref FROM ledger ORDER BY id").fetchall()

if __name__ == "__main__":                # python -m airstack.account_guard --clear "why" : the owner resumes after reading the stops
    import argparse
    a = argparse.ArgumentParser(); a.add_argument("--clear", metavar="REASON"); args = a.parse_args()
    g = AccountGuard()
    for row in g._c.execute("SELECT id, at, reason FROM stops WHERE id > (SELECT COALESCE(MAX(through), 0) FROM clears)"):
        print("stop", *row)
    if args.clear:
        g.clear(args.clear); print("cleared:", args.clear)
    print("stopped" if g.stopped() else "not stopped")
