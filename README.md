# AirStack: see the software market move

AirStack turns the software market into sourced intelligence—organized around the tools your team actually uses. Add your stack to see relevant comparisons, changes and renewal questions without sending it to a server. Live at [airstack.bot](https://airstack.bot).

[![Counts as deployed](https://airstack.bot/stats.svg)](https://airstack.bot)

**Current snapshot:** discovery across 13,385 products; renewal verdicts cover one category, AI meeting notes. Every answer carries its evidence, check date and the condition that would require another look. A missing fact reads "Not observed".

| Layer | How much | What it claims |
|---|---|---|
| **Researched** | 7,242 products with facts from their own pages, 30,857 facts | Each fact is a quote found on the product's own page: code looks for the quote before a fact is kept. |
| **Catalog** | 576 mainstream paid products in 24 categories | Links to each product's own pages, checked live. |
| **List prices** | 2,667 prices for 689 products | Each plan's list price as written, with its quote and read date. |
| **Registry signals** | 130 developer and AI tools in 12 lanes | Downloads, stories, stars and releases from public APIs, each with its API URL and fetch time. |
| **Directory** | 12,679 software products, 7,979 organizations (4,792 businesses, ranked by headcount), 784 types | Wikidata's record, labelled "listed, not researched". |
| **Evidence chain** | 30,906 claims across 7,330 products; 232 match the vendor's own registry record, 2 are disputed by one | Per fact: the page, the quote, when it was read, and whether another record agrees. |

Each count measures one thing:
- **7,242 products researched**: product profiles with at least one fact. The evidence chain covers 7,330, adding apps researched as a market.
- **30,857 facts**: one per field per product in those profiles.
- **30,906 claims in the evidence chain**: what is served with its page, quote and read date, after the publication hold withholds some.
- **31,704 quotes found by code**: checks that passed, out of 32,750. One fact can be checked on several pages.
- **31,593 fact rows in the database**: everything stored, including what is withheld from public view.

## How it works

Maintainer-only research turns public pages into quoted facts. Deterministic builders produce the site, comparisons and machine-readable datasets from the reviewed record. Visitor actions call no model, crawler or paid service.

Your Stack stays in browser storage. It narrows reports to the products and categories that matter to you, highlights recorded changes, and keeps every recommendation tied to visible evidence. It is not a hidden score or an automated purchasing decision.

## Run and test

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r backend/requirements-dev.txt
tools/data_pull.sh                            # the published datasets are not in the repository: download them from the site, checked against checksums
.venv/bin/pytest -q backend/tests JOURNEY    # model calls are faked; journeys run real Chrome; tests that need private data skip, saying so
```

Agents can run the read-only MCP locally from reviewed data. See [docs/MCP.md](docs/MCP.md).

Layout: `web/` is the static application; `backend/airstack/` is the engine and local MCP; `backend/tools/` holds deterministic builders; `SPECS/` defines behavior; `JOURNEY/` tests it in Chrome. Published datasets live outside git in `data/site/`. More: [ARCHITECTURE](docs/ARCHITECTURE.md), [OWNER](docs/OWNER.md), [CONTRIBUTING](.github/CONTRIBUTING.md), [SECURITY](.github/SECURITY.md), [NOTICE](NOTICE.md).

Counts above are generated: `tools/update_counts.py` writes `config/numbers.json` and rewrites these sentences; tests fail if they differ.

## Known gaps

- Verdicts exist only for meeting notes. Other categories show facts and signals.
- Of 12,679 directory listings, 6,650 have facts whose quotes are on the page. The rest are listed, not researched. Sites that block automated readers stay unresearched.
- A quote proves the words are on the page, not what they mean. List fields can carry page furniture such as button text. Read the quote beside each value.
- Agreement from the vendor's own registry is a second record, not independent confirmation.
- Advice that reaches its recheck date is clearly marked as needing another look; old evidence remains inspectable.
- MCP runs locally over stdio.

## Data and license

Code is MIT. Original compilation metadata is CC BY 4.0 where applicable; third-party material keeps its original rights. See `NOTICE.md`.

Data is not stored in this repository: airstack.bot serves the published datasets and `tools/data_pull.sh` fetches them, checked against checksums; the paid databases and saved responses stay private, backed up with `tools/backup.sh`. See `docs/OWNER.md`.
