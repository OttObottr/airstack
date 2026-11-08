"""The method: a fact exists only if check() finds its quote, every listed name and every number on the text of its own page."""
import json
import re
import unicodedata
from decimal import Decimal
from html.parser import HTMLParser
from .paths import config
from .schemas import CATALOG_METRICS, PROFILE_METRICS

SKIP = {"script", "style", "template", "noscript", "svg"}
BLOCK = {"address", "article", "aside", "blockquote", "body", "br", "dd", "details", "dialog", "div", "dl", "dt", "fieldset", "figcaption", "figure",
         "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "html", "li", "main", "nav", "ol", "p", "pre", "section", "summary",
         "table", "tbody", "tfoot", "thead", "title", "tr", "ul"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Page(HTMLParser):
    """Visible text with line breaks at block elements, and the JSON-LD blocks."""
    def __init__(self):
        super().__init__()
        self.out, self.skip, self.ld, self.capture = [], [], [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.skip and tag not in SKIP and "hidden" not in a and (a.get("aria-hidden") or "").strip().lower() != "true":
            self.out.append("\n" if tag in BLOCK else " " if tag in ("td", "th") else "")
        elif tag not in VOID:
            self.capture = not self.skip and tag == "script" and (a.get("type") or "").strip().lower() == "application/ld+json"
            self.ld += [""] * self.capture
            self.skip.append(tag)

    def handle_endtag(self, tag):
        if not self.skip:
            self.out.append("\n" if tag in BLOCK else "")
        elif tag in self.skip:
            del self.skip[len(self.skip) - 1 - self.skip[::-1].index(tag):]
        else:
            self.skip = []                                           # an unmatched end tag closes an element around the hidden one
        self.capture = self.capture and bool(self.skip)

    def handle_data(self, data):
        if not self.skip:
            self.out.append("".join(" " if c.isspace() else c for c in data))
        elif self.capture:
            self.ld[-1] += data


def _parse(raw):
    p = _Page()
    p.feed(raw or "")
    p.close()
    return p


def page_text(raw):
    """Readable text of an HTML page: visible text only, line breaks at block elements."""
    lines = "".join(_parse(raw).out).split("\n")
    return "\n".join(ln for ln in (" ".join(x.split()) for x in lines) if ln)


def offers(raw):
    """[{name, amount, currency}] from the page's schema.org Offer and PriceSpecification JSON-LD."""
    out = []
    def walk(x, name=None):
        if isinstance(x, list):
            for y in x:
                walk(y, name)
        elif isinstance(x, dict):
            name = x.get("name") if isinstance(x.get("name"), str) else name
            price, cur = x.get("price", x.get("lowPrice")), x.get("priceCurrency")
            if str(x.get("@type")).endswith(("Offer", "PriceSpecification")) and isinstance(price, (int, float, str)) and isinstance(cur, str):
                try:
                    out.append({"name": name, "amount": Decimal(str(price).replace(",", "")), "currency": cur.upper()})
                except ArithmeticError:
                    pass
            for v in x.values():
                walk(v, name)
    for block in _parse(raw).ld:
        try:
            walk(json.loads(block))
        except ValueError:
            pass
    return out


class _Fold(dict):
    """Per character: format characters dropped, every dash to '-', every quote mark to ' or \", and each Chinese or Japanese character
    standing alone (those scripts write words without spaces)."""
    def __missing__(self, o):
        c = chr(o)
        cat, name = unicodedata.category(c), unicodedata.name(c, "")
        r = (o if o < 128 else None if cat == "Cf" else "-" if cat == "Pd" or c == "\u2212"
             else ('"' if "DOUBLE" in name else "'") if cat in ("Pi", "Pf") or ("QUOTATION MARK" in name or "APOSTROPHE" in name or "PRIME" in name)
             else f" {c} " if name.startswith(("CJK UNIFIED", "CJK COMPATIBILITY IDEOGRAPH", "HIRAGANA", "KATAKANA")) else o)
        self[o] = r
        return r

FOLD = _Fold()
TOKEN = re.compile(r"\d+(?:[.,']\d+)*|[^\W\d_]+[+#]*|[^\w\s]")   # a number, a word (c++, c#), or one mark


def _fold(s):
    return unicodedata.normalize("NFKC", (s or "").replace("\u2122", " \u2122")).translate(FOLD)        # "Android™" is "Android TM"


def norm(s):
    """Canonical text for matching: NFKC, case-folded, dashes and quotes unified, as words, numbers and marks separated by one space."""
    return " ".join(TOKEN.findall(_fold(s).casefold()))


def found(needle, text):
    """Normalised `needle` as a whole run of tokens in normalised `text`: "pro" is not in "products"."""
    return bool(needle) and f" {needle} " in f" {text} "


CURRENCY = config("currency")
SYMBOLS, PREFIXED, CODES = CURRENCY["symbols"], CURRENCY["prefixed"], set(CURRENCY["codes"])          # a code counts in capitals and apart: not "Try 30", "PHP8"


def readings(tok, mark=None):
    """The values a number token can mean. Separators are read from digit-group structure; one separator before exactly three
    digits ("1,200") is either grouping or a decimal mark, so it has two readings unless `mark` (the decimal mark) says which."""
    seps = [c for c in tok if not c.isdigit()]
    groups = re.split(r"[.,']", tok)
    grouped = lambda gs: 1 <= len(gs[0]) <= 3 and gs[0] != "0" and all(len(g) == 3 for g in gs[1:])
    if not seps:
        return [Decimal(tok)]
    if len(set(seps)) == 1 and (len(seps) > 1 or seps[0] == "'"):
        return [Decimal("".join(groups))] if grouped(groups) else []
    if len(set(seps)) == 1:
        dec = Decimal(f"{groups[0]}.{groups[1]}")
        if len(groups[1]) != 3 or not grouped(groups):
            return [dec]
        whole = Decimal("".join(groups))
        return [whole] if mark and mark != seps[0] else [dec] if mark == seps[0] else [whole, dec]
    dec = seps[-1]
    if seps.count(dec) == 1 and dec != "'" and grouped(groups[:-1]):
        return [Decimal(f"{''.join(groups[:-1])}.{groups[-1]}")]
    return []


def numbers(q, whole=False):
    """Every value any number token in normalised text can mean; `whole`: only readings written without decimals."""
    return {r for t in q.split() if t[0].isdigit() for r in readings(t) if not whole or r.as_tuple().exponent >= 0}


def has_money(s):
    """A currency symbol, or an ISO 4217 code standing apart, next to a number, in any free text."""
    t = list(TOKEN.finditer(_fold(s)))
    money = lambda j, i: 0 <= j < len(t) and ((len(y := t[j].group()) == 1 and unicodedata.category(y) == "Sc") or (y in CODES and not _glued(t[i], t[j])))
    return any(m.group()[0].isdigit() and (money(i - 1, i) or money(i + 1, i)) for i, m in enumerate(t))


def _glued(a, b):
    return a.end() == b.start() or b.end() == a.start()


def prices(text, lang=None, mark=None):
    """Each price in `text`: {amount: Decimal or None, currency: ISO 4217, raw, ambiguous}. The symbol or code may stand before or after
    the number. `lang` (the page language) or `mark` (its decimal mark) settles "1,200"; without either it is ambiguous."""
    mark = mark or (lang and ("," if lang.split("-")[0].lower() in CURRENCY["decimal_comma_languages"] else "."))
    s = _fold(text)
    ms = list(TOKEN.finditer(s))
    def at(j, i):                                                    # (currency, first token) of a symbol or code at j, beside number i
        y = ms[j].group() if 0 <= j < len(ms) else ""
        if y in CODES and not _glued(ms[i], ms[j]):
            return y, j
        if len(y) == 1 and unicodedata.category(y) == "Sc":
            pre = ms[j - 1].group().casefold() + y if j and ms[j - 1].end() == ms[j].start() else ""
            return (PREFIXED[pre], j - 1) if pre in PREFIXED else (SYMBOLS.get(y), j)
        return None, j
    for i, m in enumerate(ms):
        if m.group()[0].isdigit():
            (cur, a), b = at(i - 1, i), i
            if not cur:
                (cur, b), a = at(i + 1, i), i
            if cur:
                r = readings(m.group(), mark)
                yield {"amount": r[0] if len(r) == 1 else None, "currency": cur, "raw": s[ms[a].start():ms[b].end()], "ambiguous": len(r) != 1}


def parse_price(text, lang=None, mark=None):
    """The first price in `text` (see prices), or None."""
    return next(prices(text, lang, mark), None)


QUOTE_WORDS = 25
LISTS = ("x.devices", "x.integrations", "x.compliance", "x.plan_names", "x.deployment", "x.platforms", "x.sdk_languages", "x.models_supported")
COUNTS = ("x.languages_count", "x.store_users", "x.integrations_count", "x.founded_year")
COMPLIANCE = config("compliance")
STANDARDS = [norm(s) for s in COMPLIANCE["standards"]]
CODE = re.compile(r"[{}]|=>|;\s*$|\bawait\b|\bimport\b|\bconst\b|\w\.\w+\(")
INTEGRATION = re.compile(r"integrat|connect|plug-?in|add-?on|extension|works? with|compatible with|sync|import|export|marketplace|app directory")
THIRD_PARTY = r"(?:payment|third[- ]party|sub-?)\s?processors?|data cent(?:er|re)s?|(?:cloud|hosting) providers?|\bhosted (?:on|by|with)\b|our (?:vendors?|partners?|infrastructure)"
OURS = re.compile(r"\bwe use\b|\bwe rely on\b|\bpowered by\b|" + THIRD_PARTY)


def held(q):
    """The normalised quote says the product holds what it names: an assertion form, and no negation, plan or third party."""
    C, words = COMPLIANCE, set(q.split())
    return bool(words & set(C["assert"]) or any(found(p, q) for p in C["assert_phrases"])) \
        and not words & set(C["not_held"]) and not any(found(p, q) for p in C["not_held_phrases"])


def check(f, text, kind=None):
    """(ok, why, value). `text` is the normalised page text; `kind` the page's kind (home, pricing, integrations ...).
    A certification counts only when the quote says the product holds it; an integration only from an integrations page or
    a quote that presents it as one, never from a product the vendor itself uses."""
    if f["metric"] not in CATALOG_METRICS and f["metric"] not in PROFILE_METRICS:
        return False, "metric not in the vocabulary", None
    q = norm(f["quote"])
    if len(f["quote"].split()) > QUOTE_WORDS:
        return False, f"quote longer than {QUOTE_WORDS} words", None
    if len(q) < 3 or not found(q, text):
        return False, "quote not found on the page", None
    try:
        v = json.loads(f["value_json"])
    except ValueError:
        v = f["value_json"].strip()
    m, words, low = f["metric"], set(q.split()), _fold(f["quote"]).casefold()
    if m == "x.integrations" and (OURS.search(low) or (kind != "integrations" and not INTEGRATION.search(low))):
        return False, "the quote does not present it as an integration", None
    if m in LISTS and isinstance(v, str):  # "A, B and C" is split; each piece is still checked
        v = [x for x in re.split(r"\s*(?:,|;|\band\b|&)\s*", v) if x.strip()]
    if m in ("x.free_plan", "x.open_source") and isinstance(v, str) and v.lower() in ("true", "false"):
        v = v.lower() == "true"
    if m in COUNTS and isinstance(v, str) and v.replace(",", "").isdigit():
        v = int(v.replace(",", ""))
    if m == "x.integrations" and isinstance(v, int) and not isinstance(v, bool):        # "100+ apps": a count, not names
        return (True, "ok", ("x.integrations_count", v)) if v in numbers(q, True) else (False, "the number is not in its quote", None)
    if m in LISTS:
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False, "expected a list of names", None
        kept = sorted({x.strip() for x in v if x.strip() and found(norm(x), q)})
        if m == "x.compliance":
            kept = [x for x in kept if any(found(s, norm(x)) for s in STANDARDS)] if held(q) else []
            return (True, "ok", kept) if kept else (False, "the quote does not say the product holds it", None)
        return (True, "ok", kept) if kept else (False, "no listed name appears in the quote", None)
    if m in COUNTS:
        if isinstance(v, bool) or not isinstance(v, int):
            return False, "expected an integer", None
        if m == "x.store_users" and not any(w.startswith("user") for w in words):  # a ratings count is not a user count
            return False, "the quote does not say users", None
        return (True, "ok", v) if v in numbers(q, True) else (False, "the number is not in its quote", None)
    if m in ("x.free_plan", "x.open_source"):
        if not isinstance(v, bool):
            return False, "expected true or false", None
        if m == "x.free_plan" and v is True:  # a free plan, not a trial or one-time credits
            p = parse_price(f["quote"])
            if not ("free" in words or (p and p["amount"] == 0 and words & {"mo", "month", "forever"})):
                return False, "the quote never says free or $0 a month (no credit card required is not a free plan)", None
            if (words & {"trial", "credits"} or found("credit", q) and not found("credit card", q)) and not words & {"month", "monthly", "forever", "always", "plan", "tier"}:
                return False, "free credits or a trial, not a free plan", None
        return True, "ok", v
    if m == "x.what_it_does" and CODE.search(f["quote"]):
        return False, "not a description (code)", None
    if m in ("x.what_it_does", "x.license", "x.pricing_basis", "x.customers_claimed"):
        return True, "ok", f["quote"].strip()  # the value is the page's own words
    if m == "x.store_rating":
        r = v.get("rating") if isinstance(v, dict) else v
        if isinstance(r, str):
            r = next((float(readings(t)[0]) for t in norm(r).split() if t[0].isdigit() and readings(t)), None)
        if isinstance(r, bool) or not isinstance(r, (int, float)) or not 0 <= r <= 5:
            return False, "expected a rating out of 5", None
        if Decimal(str(r)) not in numbers(q):
            return False, "the rating is not in its quote", None
        count = str(v.get("count", "")).strip() if isinstance(v, dict) else ""
        return True, "ok", {"rating": float(r), "count": count}
    return False, "unhandled metric", None
