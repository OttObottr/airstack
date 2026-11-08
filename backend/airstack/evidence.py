"""Links that let a reader check one fact: a text fragment that highlights the quote on its page, and a prefilled problem report.
web/src/lib/format.js builds the same links in the browser; backend/tests/test_data.py holds both to the same output."""
from urllib.parse import quote as _quote

ISSUES = "https://github.com/OttObottr/airstack/issues/new"
WORDS = 4          # a long quote is matched by its first and last words: textStart,textEnd
SHORT = 8          # up to this many words on one line, the whole quote is the textStart


def term(s):
    """One text directive term: UTF-8 percent-encoded, every byte but A-Z a-z 0-9 _ . ~ (so '-', ',' and '&' never act as syntax)."""
    return _quote(s, safe="").replace("-", "%2D")


def text_fragment(url, quote):
    """`url#:~:text=start[,end]` (WICG Scroll to Text Fragment). Whitespace runs collapse; lines are matched across."""
    lines = [" ".join(line.split()) for line in str(quote).splitlines() if line.strip()]
    if not lines:
        return url
    first, last = lines[0].split(), lines[-1].split()
    if len(lines) == 1 and len(first) <= SHORT:
        directive = term(lines[0])
    else:
        directive = term(" ".join(first[:WORDS])) + "," + term(" ".join(last[-WORDS:]))
    return url + ("" if "#" in url else "#") + ":~:text=" + directive


def report_url(product, field, url, quote):
    """A new GitHub issue, prefilled with the product, the fact, its page and its quote."""
    body = f"Product: {product}\nFact: {field}\nPage: {url}\nQuote: “{quote}”\n\nWhat is wrong:\n"
    return f"{ISSUES}?title={term(f'Problem with a fact: {product}, {field}')}&body={term(body)}"


def shown(policy, metric):
    """Whether chain-data.json's published policy lets a fact of this metric appear: its low and medium tiers."""
    return metric in {*policy["tiers"]["low"], *policy["tiers"]["medium"]}
