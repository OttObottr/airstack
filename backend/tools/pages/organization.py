"""/o/<slug>/: one page per maker with at least one product listed."""
import collections
import re
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head, slug
from .data import DIRECTORY, ORGS, PAGES, app_addr
from .makers import maker_lists
from airstack.files import read_json

LINKS = PAGES["links"]

ROLE = PAGES["roles"]

PLATFORM = PAGES["platforms"]

def link_url(kind, v):
    """An address built from an id Wikidata records; only ids made of safe characters become links."""
    if kind == "blog":
        return v if re.match(r"https?://", v) else None
    if kind == "mastodon":
        m = re.fullmatch(r"@([\w.]+)@([\w.-]+)", v); return f"https://{m.group(2)}/@{m.group(1)}" if m else None
    if kind not in LINKS or not re.fullmatch(r"[\w./@-]{1,120}", v):
        return None
    return LINKS[kind][1].format(v)

def org_page(qid, row, made, all_, community, duplicate=False):
    name, site, country, founded, _, kind, staff, year, wiki = row[:9]
    url = f"{BASE}/o/{ORGS[qid]}/"; C = community.get(qid, {})
    linked = [(LINKS.get(k, (PLATFORM.get(k, k), ""))[0] if k != "mastodon" else "Mastodon", link_url(k, v)) for k, v in sorted(C.get("links", {}).items())]
    linked = [(ln, u) for ln, u in linked if u]
    prods = sorted(made, key=lambda x: x[1].lower())
    plink = lambda pid, nm: f'<a href="/p/{all_[pid]["slug"]}/">{e(nm)}</a>' if pid in all_ and all_[pid].get("page") else f'<a href="/#app={e(app_addr(pid, nm))}">{e(nm)}</a>'
    facts = [("Kind", "Business" if kind == "business" else "Organization"), ("Country", country), ("Founded", founded if founded and str(founded)[:4].isdigit() else None),
             ("Employees", f"{staff:,} (as Wikidata records it{', ' + str(year) if year else ', undated'})" if staff else None),
             ("Documented in", f"{wiki} Wikipedia and sister-site pages" if wiki else None)]
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in facts if v)
    fol = "".join(f"<li>{n:,} followers on {e(PLATFORM.get(pl, pl))} <small>as Wikidata states it{', ' + e(d) if d else ''}</small></li>" for pl, n, d in C.get("followers", []))
    people = "".join(f"<li>{e(nm)} <small>{e(ROLE.get(r, r))}</small></li>" for _, nm, r in C.get("people", []))
    desc = (f"{name}: {'a business' if kind == 'business' else 'an organization'}{' in ' + country if country else ''}{', founded ' + str(founded) if founded and str(founded)[:4].isdigit() else ''}. "
            + (f"{len(prods)} product{'s' if len(prods) != 1 else ''} listed on AirStack. " if prods else "")
            + (f"{staff:,} employees as Wikidata records it." if staff else "")).strip()
    same = [u for u in [site if site and re.match(r"https?://", site) else None, f"https://www.wikidata.org/wiki/{qid}"] + [u for _, u in linked if not u.startswith(BASE)] if u]
    ld = {"@context": "https://schema.org", "@type": "Organization", "name": name, "url": url, "sameAs": same,
          **({"foundingDate": str(founded)[:4]} if founded and str(founded)[:4].isdigit() else {}), **({"address": {"@type": "PostalAddress", "addressCountry": country}} if country else {}),
          **({"numberOfEmployees": {"@type": "QuantitativeValue", "value": staff}} if staff else {}),
          **({"founder": [{"@type": "Person", "name": nm} for _, nm, r in C.get("people", []) if r == "founder"]} if any(r == "founder" for _, _, r in C.get("people", [])) else {})}
    domain = re.sub(r"^www\.", "", re.sub(r"^https?://", "", site or "").split("/", 1)[0])
    detail = domain or (f"founded {founded}" if founded else kind)
    qualifier = f" ({detail})" if duplicate else ""
    title = f"{name}{qualifier}{' in ' + country if country else ''}: products, size and community · AirStack.bot"
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Software makers", "/o/"), (name, None)))
    return head(title, desc, url, (ld, crumb)) + f"""<body><main>{nav}
<h1>{e(name)}</h1>
<p><small>{(f'<a href="{e(site)}" rel="nofollow noopener">' + e(re.sub(r"^https?://(www\.)?", "", site).split('/')[0]) + '</a> · ') if site and re.match(r"https?://", site) else ''}<a href="https://www.wikidata.org/wiki/{e(qid)}" rel="nofollow noopener">Wikidata</a></small></p>
<a class="cta" href="/#app={e(app_addr(qid, name))}">Open {e(name)} in AirStack</a>
{f'<h2>About {e(name)}</h2><table>{rows}</table>' if rows else ''}
{f'<h2>Products by {e(name)}</h2><ul>' + "".join(f"<li>{plink(pid, nm)}</li>" for pid, nm in prods[:PAGES["limits"]["org_products"]]) + '</ul>' if prods else ''}
{f'<h2>Where to find {e(name)}</h2><ul>' + "".join(f'<li><a href="{e(u)}" rel="nofollow noopener">{e(ln)}</a></li>' for ln, u in linked) + '</ul>' if linked else ''}
{f'<h2>Audience</h2><ul>{fol}</ul>' if fol else ''}
{f'<h2>People</h2><ul>{people}</ul><p><small>As Wikidata records them; a role may have ended.</small></p>' if people else ''}
{foot('Organization records from Wikidata (CC0). ')}
</main></body></html>
"""

def org_pages(all_):
    """A page per maker with at least one listed product."""
    C = read_json(paths.COMMUNITY) if paths.COMMUNITY.exists() else {"entities": {}, "catalog": {}}
    community = C["entities"]
    made = {}
    for pid, name, *_rest in DIRECTORY["products"]:
        for m in _rest[3]:
            made.setdefault(m, []).append((pid, name))
    for cid, qids in C.get("catalog", {}).items():                            # catalog products, joined to their makers' Wikidata items
        for q in qids:
            if cid in all_ and q in DIRECTORY["orgs"] and (cid, all_[cid]["name"]) not in made.get(q, []):
                made.setdefault(q, []).append((cid, all_[cid]["name"]))
    keep = {q: r for q, r in DIRECTORY["orgs"].items() if r[5] != "person" and any(pid in all_ and all_[pid].get("page") for pid, _ in made.get(q, []))}
    names = collections.Counter(slug(r[0]) for r in keep.values())
    for q, r in keep.items():
        ORGS[q] = slug(r[0]) if names[slug(r[0])] == 1 else f"{slug(r[0])}-{q.lower()}"      # a readable address; the id only where two makers read the same
    out = paths.PAGE_DIRS["o"]; shutil.rmtree(out, ignore_errors=True); urls = []
    for q, r in sorted(keep.items(), key=lambda kv: ORGS[kv[0]]):
        d = out / ORGS[q]; d.mkdir(parents=True, exist_ok=True); d.joinpath("index.html").write_text(org_page(q, r, made.get(q, []), all_, community, names[slug(r[0])] > 1))
        urls.append(f"{BASE}/o/{ORGS[q]}/")
    return urls + maker_lists(keep, made)
