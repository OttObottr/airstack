"""site-data.js: the first-paint data (search index, categories, lanes, top movers, directory counts).
Usage: python backend/tools/build_site_data.py"""
import json
import re
from airstack import paths
from airstack.mcp_server import DESCRIPTIONS as MCP_DESCRIPTIONS
from airstack.files import read_json

ROOT = paths.ROOT
MCP_TOOLS = sorted(MCP_DESCRIPTIONS)

def directory_counts():
    p = paths.DIRECTORY
    if not p.exists():
        return None
    d = read_json(p)
    researched = sum(1 for v in read_json(paths.PROFILES).values() if v.get("facts")) if paths.PROFILES.exists() else 0
    return {"products": len(d["products"]), "orgs": sum(1 for o in d["orgs"].values() if o[5] != "person"), "types": len(d["types"]), "researched": researched,
            "fetched_at": d["source"]["fetched_at"]}

def lanes_named():
    nodes = {node["id"]: node["name"] for node in read_json(paths.TAXONOMY)["nodes"]}
    return {lane: nodes[node] for lane, node in read_json(paths.TAXONOMY_CROSSWALK)["lanes"].items()}

def discovery_data():
    movers = paths.read_js(paths.MARKET_DATA).get("movers")
    if movers:
        def substantial(row):
            return row["dl"]["value"] >= movers["params"]["solid_min_downloads"] and not (row["dl"].get("vsBase") is not None and row["dl"]["vsBase"] < 0)

        top = sorted([row for row in movers["rows"] if row["dl"]["delta"] is not None],
                     key=lambda row: (not substantial(row), -row["dl"]["delta"]))[:paths.config("pages")["limits"]["movers_top"]]
        def compact(row):
            return {"id": row["id"], "name": row["name"], "lane": row["lane"], "laneName": row["laneName"],
                    "dl": {key: row["dl"].get(key) for key in ("value", "delta", "vsBase", "baseWeeks", "registry", "url")},
                    "hn": {key: row["hn"][key] for key in ("value", "delta", "query")},
                    "gh": {key: row["gh"][key] for key in ("stars", "release", "released", "url")}}
        movers = {"window": movers["window"], "generated": movers["generated"], "lanes": movers["lanes"], "params": movers["params"],
                  "rows": [compact(row) for row in top], "partial": True, "total": len(movers["rows"])}
    universe = read_json(paths.UNIVERSE)
    names = lanes_named()
    lanes = [{"id": lane, "name": names.get(lane, lane), "n": sum(tool["lane"] == lane for tool in universe)}
             for lane in dict.fromkeys(tool["lane"] for tool in universe)]
    from airstack.catalog import CATEGORIES, entries as catalog_entries
    known = {tool["id"] for tool in universe} | {tool["name"].lower() for tool in universe}
    catalog = [entry for entry in catalog_entries() if entry["id"] not in known and entry["name"].lower() not in known]
    categories = [{"id": key, "name": name, "tools": sum(entry["category"] == key for entry in catalog)}
                  for key, name in CATEGORIES.items()]
    def aliases(tool):
        """Package and repository names people type for a tool, kept where they differ from its name as search compares."""
        key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        repo = (tool.get("github") or "").rsplit("/", 1)[-1]
        names = [*(tool.get("npm") or []), *(tool.get("pypi") or []), *([repo] if key(tool["name"]) in key(repo) else [])]
        seen = {key(tool["name"])}
        return [n for n in names if key(n) not in seen and not seen.add(key(n))]
    index = [[tool["id"], tool["name"], tool["lane"], aliases(tool)] for tool in universe]
    index += [[entry["id"], entry["name"], entry["category"], entry.get("aliases") or []] for entry in catalog]
    return index, categories, lanes, movers

def checked_at(directory, movers):
    """The newest check date in the published data, never the clock."""
    dates = [(directory or {}).get("fetched_at"), (movers or {}).get("generated")]
    if paths.PROFILES.exists():
        dates += [c.get("checked") for p in read_json(paths.PROFILES).values() for c in p.values() if isinstance(c, dict)]
    return max((d[:10] for d in dates if d), default=None)

def main():
    search_index, categories, lanes, movers = discovery_data()
    counts = directory_counts()
    checked = checked_at(counts, movers)
    d = counts or {}
    headline = {"products": len(search_index) + d.get("products", 0), "organizations": d.get("orgs", 0), "researched_products": d.get("researched", 0),
                "facts": read_json(paths.CHAIN_DATA)["summary"]["facts"] if paths.CHAIN_DATA.exists() else None,
                "list_prices": sum(len(v["plans"]) for v in read_json(paths.PRICING).values()) if paths.PRICING.exists() else None}
    data = {"index": search_index, "cats": categories, "dir": counts,
            "lanes": lanes, "moversTop": movers, "meta": {"checked_at": checked, "counts": headline}, "labels": paths.config("pages")["labels"],
            "tools": [{"key": key, "name": name, "cat": cat, "aliases": aliases} for key, name, cat, aliases in search_index],
            "execution": {"mcp": {"tools": MCP_TOOLS, "as_of": checked}}}
    paths.SITE_DATA.write_text("// GENERATED by backend/tools/build_site_data.py from the published datasets. Do not edit by hand.\n"
                               "window.AIRSTACK_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"site-data.js: {len(search_index)} indexed products, checked {checked}")
    return data

if __name__ == "__main__":
    main()
