"""Where every file lives: config/ in git, the published datasets in $AIRSTACK_DATA/site (default data/site), rendered pages in the root."""
import json
import os
from pathlib import Path
from .files import read_json

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = Path(os.environ.get("AIRSTACK_DATA") or ROOT / "data")
SITE = DATA / "site"

SITE_DATA, MARKET_DATA = SITE / "site-data.js", SITE / "market-data.js"
CHAIN_DATA = SITE / "chain-data.json"
CATALOG, UNIVERSE = SITE / "catalog.json", SITE / "universe.json"
DIRECTORY, COMMUNITY = SITE / "directory.json", SITE / "community.json"
PROFILES, PRICING, OSS, HF = SITE / "profiles.json", SITE / "pricing.json", SITE / "oss.json", SITE / "hf.json"
INSIGHTS, NEWS, EVENTS = SITE / "insights.json", SITE / "news.json", SITE / "events.json"
CATEGORY_GUIDES = SITE / "category-guides.json"
ATTENTION, MAKERS, SUGGESTIONS, MARKETS = SITE / "attention.json", SITE / "makers.json", SITE / "suggestions.json", SITE / "markets.json"
TAXONOMY_INDEX = SITE / "taxonomy-index.json"
TAXONOMY_CROSSWALK = SITE / "taxonomy-crosswalk.json"
FEED = SITE / "changes.atom"
OPEN_DATA = SITE / "open-data"
STATS_SVG, SITEMAP = SITE / "stats.svg", SITE / "sitemap.xml"
PAGE_DIRS = {name: ROOT / name for name in ("p", "o", "c", "t", "compare", "insights", "calendar", "method")}

TAXONOMY = CONFIG / "taxonomy.json"


def read_js(path):
    """The JSON object inside a generated `window.X = {...};` file."""
    text = Path(path).read_text()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def config(name):
    return read_json(CONFIG / f"{name}.json")
