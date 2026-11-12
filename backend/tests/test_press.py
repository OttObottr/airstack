"""No outlet wording reaches the site: press is a link with its outlet and date, shown only as "Covered by" on the vendor's own news."""
import json
from airstack.paths import ROOT, SITE

ALLOWED = {"id", "name", "outlet", "url", "date", "signal", "weight"}


def test_press_items_carry_no_outlet_wording():
    items = json.loads((SITE / "coverage.json").read_text())["items"]
    assert all(set(i) <= ALLOWED for i in items), sorted({k for i in items for k in i} - ALLOWED)


def test_no_page_or_feed_shows_press_as_its_own_row():
    src = (ROOT / "web" / "src" / "components" / "news.js").read_text()
    assert "kind: 'press'" not in src and "['press', 'Press']" not in src
