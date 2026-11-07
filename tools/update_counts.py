# spec: AS-263 AS-351
"""One number, one source: refresh headline counts and the local MCP contract from their canonical generated/config sources.
A sentence or contract marker that is missing or reworded stops the run, so public prose cannot drift unnoticed. No model call."""
import json, re, sqlite3
from airstack import paths
from airstack.publication import public_prices
from airstack.mcp_server import DESCRIPTIONS as MCP_DESCRIPTIONS

R = paths.ROOT
js = lambda path: (lambda t: json.loads(t[t.index("{"):t.rindex("}") + 1]))(path.read_text())
DOCS = {"README.md": R / "README.md", "llms.txt": R / "web" / "public" / "llms.txt", "stats.svg": paths.STATS_SVG}   # the files whose sentences carry counts

RULES = {   # each sentence that states a count, with {name} where the number from numbers.json goes; each must appear exactly once
    "README.md": [
        "across {products} products; renewal verdicts",
        "| {researched_products} products with facts from their own pages, {facts} facts |",
        "| {catalog_products} mainstream paid products in {catalog_categories} categories",
        "| {list_prices} prices for {priced_products} products |",
        "| {registry_tools} developer and AI tools in {registry_lanes} lanes |",
        "| **Directory** | {directory_products} software products, {organizations} organizations ({businesses} businesses, ranked by headcount), {types} types |",
        "| {chain_claims} claims across {chain_products} products; {registry_matches} match the vendor's own registry record, {registry_disputes} are disputed by one |",
        "- **{researched_products} products researched**: product profiles with at least one fact. The evidence chain covers {chain_products},",
        "- **{facts} facts**:", "- **{chain_claims} claims in the evidence chain**:",
        "- **{quotes_passed} quotes found by code**: checks that passed, out of {quotes_checked}.",
        "- **{fact_rows} fact rows in the database**:",
        "Of {directory_products} directory listings, {directory_researched} have facts whose quotes are on the page."],
    "llms.txt": [
        "Search: {products} software products and {organizations} organizations that make them",
        "{registry_tools} registry-tracked tools, {catalog_products} checked catalog products",
        "{researched_products} products carry facts", "Every software type ({types}, from Wikidata)",
        "Moving this week: {registry_tools} developer and AI tools in {registry_lanes} lanes"]}

def counts():
    mk, S = js(paths.MARKET_DATA), js(paths.SITE_DATA); ch = json.loads(paths.CHAIN_DATA.read_text()); D = json.loads(paths.DIRECTORY.read_text())
    P = {k: v for k, v in mk["profiles"].items() if v.get("facts")}; cat = json.loads(paths.CATALOG.read_text()); pr = public_prices(json.loads(paths.PRICING.read_text()))
    rows = sqlite3.connect(f"file:{paths.MARKET_DB}?mode=ro", uri=True).execute("SELECT count(*) FROM facts").fetchone()[0]
    return dict(products=len(S["index"]) + S["dir"]["products"], directory_products=S["dir"]["products"], directory_researched=len(P.keys() & {p[0] for p in D["products"]}),
                organizations=S["dir"]["orgs"], businesses=sum(1 for o in D["orgs"].values() if o[5] == "business"), types=len(D["types"]),
                registry_tools=S["moversTop"]["total"], registry_lanes=len(S["lanes"]), catalog_products=len(cat), catalog_categories=len({e["category"] for e in cat}),
                researched_products=len(P), facts=sum(x["facts"] for x in P.values()), fact_rows=rows,
                chain_claims=sum(len(e["facts"]) for e in ch["entities"].values()), chain_products=len(ch["entities"]),
                registry_matches=ch["summary"]["registry_second_record"], registry_disputes=ch["summary"]["registry_disputed"],
                quotes_passed=mk["fleet"]["passed"], quotes_checked=mk["fleet"]["checked"],
                list_prices=sum(len(v["plans"]) for v in pr.values()), priced_products=sum(1 for v in pr.values() if v["plans"]))

def fill(text, rules, n):
    """text with every counted sentence carrying n's numbers; stops if a sentence is not there exactly once."""
    for t in rules:
        rx = re.compile("".join(re.escape(p) if i % 2 == 0 else r"[\d,]+" for i, p in enumerate(re.split(r"\{(\w+)\}", t))))
        if len(rx.findall(text)) != 1:
            raise SystemExit(f"update_counts: {t!r} is not in the text exactly once: restore the sentence or change its rule")
        text = rx.sub(lambda m: t.format(**{k: f"{v:,}" for k, v in n.items()}), text)
    return text

def fill_mcp_tools(text):
    """Replace the one local tool list from the stdio server's canonical contract."""
    marker, tail = "Local MCP tools: ", ". Start with"
    if text.count(marker) != 1 or text.count(tail) != 1:
        raise SystemExit("update_counts: the llms.txt MCP tool-list sentence changed")
    before, rest = text.split(marker)
    _, after = rest.split(tail)
    tools = ", ".join(sorted(MCP_DESCRIPTIONS))
    return before + marker + tools + tail + after

def main():
    n = counts()
    paths.NUMBERS.write_text(json.dumps(n, indent=1) + "\n")
    for f, rules in RULES.items():
        text = fill(DOCS[f].read_text(), rules, n)
        DOCS[f].write_text(fill_mcp_tools(text) if f == "llms.txt" else text)
    print(n)

if __name__ == "__main__":
    main()
