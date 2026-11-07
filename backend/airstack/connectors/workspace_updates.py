# spec: AS-012 AS-070
"""Google Workspace Updates Atom feed. Rule-based (no model): a known title means a known capability fact.
Facts carry the feed's own link and its own `published` timestamp (converted to UTC)."""
import re
from datetime import datetime, timezone
from ..engine import Obs
from ..fetch import parse_xml, text   # one honest name; robots.txt obeyed (AS-274)

FEED_URL = "https://workspaceupdates.googleblog.com/feeds/posts/default?alt=atom&max-results=50"

def window_url(start, end):
    """The default feed only carries recent posts; ask Blogger for a published-date window instead (e.g. 2026-08-12 .. 2026-08-15)."""
    return f"{FEED_URL}&published-min={start}T00:00:00-07:00&published-max={end}T00:00:00-07:00"
_NS = {"a": "http://www.w3.org/2005/Atom"}
RULES = [
    (re.compile(r"take notes for me for in[- ]person meetings is now available", re.I),
     [("meet", "in_person_notes", True, None), ("meet", "in_person_notes_platforms", ["Android"], "2026-08-11T07:00:00Z"),
      ("meet", "in_person_notes_ios_earliest", "2026-08-31", None),
      ("meet", "listed_editions", ["Business Standard", "Business Plus", "Enterprise Standard", "Enterprise Plus", "Google AI Pro",
                                   "Google AI Ultra", "Frontline Plus", "Google AI Pro for Education"], None)]),
    # the post: Android from Aug 11 (PT); web no sooner than Aug 14; iOS no sooner than Aug 31
]

def _utc(ts):
    return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class WorkspaceUpdatesConnector:
    name = "workspace.updates"
    def __init__(self, fetch_text=None, url=FEED_URL, window=None):
        self._fetch, self._url = fetch_text or (lambda url: text(url, timeout=20)), (window_url(*window) if window else url)
    def fetch(self):
        root = parse_xml(self._fetch(self._url))
        out = []
        for e in root.findall("a:entry", _NS):
            title = e.findtext("a:title", "", _NS)
            link = next((l.get("href") for l in e.findall("a:link", _NS) if l.get("rel") == "alternate"), None)
            pub = e.findtext("a:published", "", _NS)
            for rx, facts in RULES:
                if rx.search(title) and link and pub:
                    out += [Obs(ent, metric, val, "workspace.updates", link, _utc(pub), eff) for ent, metric, val, eff in facts]
        return out

class StaticConnector:
    """Fixture connector: returns a fixed list of observations, or raises to simulate a failed fetch."""
    def __init__(self, name, observations=(), error=None):
        self.name, self._obs, self._error = name, list(observations), error
    def fetch(self):
        if self._error:
            raise self._error
        return list(self._obs)
