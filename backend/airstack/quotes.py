"""The method: a fact exists only if check() finds its quote, every listed name and every number on the text of its own page."""
import html
import json
import re
from .schemas import CATALOG_METRICS, PROFILE_METRICS

def page_text(raw):
    """Readable text of an HTML page, line breaks kept at block boundaries."""
    s = re.sub(r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr|/section|/article)[^>]*>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return "\n".join(ln for ln in (re.sub(r"[ \t ]+", " ", ln).strip() for ln in s.splitlines()) if ln)

def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()

CODE = re.compile(r"[{}]|=>|;\s*$|\bawait\b|\bimport\b|\bconst\b|\w\.\w+\(")

QUOTE_WORDS = 25
LISTS = ("x.devices", "x.integrations", "x.compliance", "x.plan_names", "x.deployment", "x.platforms", "x.sdk_languages", "x.models_supported")
THIRD_PARTY = r"(?:payment|third[- ]party|sub-?)\s?processors?|data cent(?:er|re)s?|(?:cloud|hosting) providers?|\bhosted (?:on|by|with)\b|our (?:vendors?|partners?|infrastructure)"
NOT_HELD = re.compile(r"in progress|in the process|on track|underway|working (?:towards?|on)|\baims?\b|\baiming\b|\bplan(?:s|ned)? to\b|\bplanned\b|pursu|roadmap|coming soon|\bexpect"
                      r"|\bpending\b|-?\bready\b|readiness|requirements of|help(?:s|ing)? (?:\w+ )?(?:to )?(?:meet|comply|achieve)|" + THIRD_PARTY)
INTEGRATION = re.compile(r"integrat|connect|plug-?in|add-?on|extension|works? with|compatible with|sync|import|export|marketplace|app directory")
OURS = re.compile(r"\bwe use\b|\bwe rely on\b|\bpowered by\b|" + THIRD_PARTY)


def check(f, text, kind=None):
    """(ok, why, value). `text` is the normalised page text; `kind` the page's kind (home, pricing, integrations ...).
    A certification counts only when the quote says the product holds it; an integration only from an integrations page or
    a quote that presents it as one, never from a product the vendor itself uses."""
    if f["metric"] not in CATALOG_METRICS and f["metric"] not in PROFILE_METRICS:
        return False, "metric not in the vocabulary", None
    q = norm(f["quote"])
    if len(q.split()) > QUOTE_WORDS:
        return False, f"quote longer than {QUOTE_WORDS} words", None
    if len(q) < 3 or q not in text:
        return False, "quote not found on the page", None
    try:
        v = json.loads(f["value_json"])
    except ValueError:
        v = f["value_json"].strip()
    m = f["metric"]
    if m == "x.compliance" and NOT_HELD.search(q):
        return False, "the quote does not say the product holds it", None
    if m == "x.integrations" and (OURS.search(q) or (kind != "integrations" and not INTEGRATION.search(q))):
        return False, "the quote does not present it as an integration", None
    if m in LISTS and isinstance(v, str):  # "A, B and C" is split; each piece is still checked
        v = [x for x in re.split(r"\s*(?:,|;|\band\b|&)\s*", v) if x.strip()]
    if m in ("x.free_plan", "x.open_source") and isinstance(v, str) and v.lower() in ("true", "false"):
        v = v.lower() == "true"
    if m in ("x.languages_count", "x.store_users", "x.integrations_count", "x.founded_year") and isinstance(v, str) and v.replace(",", "").isdigit():
        v = int(v.replace(",", ""))
    if m == "x.integrations" and isinstance(v, int) and not isinstance(v, bool):        # "100+ apps": a count, not names
        return (True, "ok", ("x.integrations_count", v)) if str(v) in re.sub(r"\D", "", q) else (False, "the number is not in its quote", None)
    if m in LISTS:
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False, "expected a list of names", None
        kept = sorted({x.strip() for x in v if x.strip() and norm(x) in text})
        return (True, "ok", kept) if kept else (False, "no listed name appears on the page", None)
    if m in ("x.languages_count", "x.store_users", "x.integrations_count", "x.founded_year"):
        if isinstance(v, bool) or not isinstance(v, int):
            return False, "expected an integer", None
        digits = re.sub(r"\D", "", q)
        if m == "x.store_users" and "user" not in q:  # a ratings count is not a user count
            return False, "the quote does not say users", None
        return (True, "ok", v) if str(v) in digits or f"{v:,}" in q else (False, "the number is not in its quote", None)
    if m in ("x.free_plan", "x.open_source"):
        if not isinstance(v, bool):
            return False, "expected true or false", None
        if m == "x.free_plan" and v is True:  # a free plan, not a trial or one-time credits
            zero_a_month = re.search(r"\$\s?0\b", q) and re.search(r"/\s?mo|month|forever", q)
            if not (re.search(r"\bfree\b", q) or zero_a_month):
                return False, "the quote never says free or $0 a month (no credit card required is not a free plan)", None
            if re.search(r"trial|credits\b|credit\b(?!\s+card)", q) and not re.search(r"month|monthly|forever|always|\bplan\b|\btier\b", q):
                return False, "free credits or a trial, not a free plan", None
        return True, "ok", v
    if m == "x.what_it_does" and CODE.search(f["quote"]):
        return False, "not a description (code)", None
    if m in ("x.what_it_does", "x.license", "x.pricing_basis", "x.customers_claimed"):
        return True, "ok", f["quote"].strip()  # the value is the page's own words
    if m == "x.store_rating":
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
