# AirStack: see the software market move

Software market intelligence where every fact is a short quote found on the product's own page, with its source and the date the
page was read. A missing fact reads "Not observed". Live at [airstack.bot](https://airstack.bot).

[![Counts as deployed](https://airstack.bot/stats.svg)](https://airstack.bot)

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r backend/requirements-dev.txt
.venv/bin/pytest -q                                   # on the synthetic datasets in backend/tests/fixtures; browser tests run real Chrome
tools/data_pull.sh                                    # the published datasets into data/site, checked against their checksums
tools/assemble.sh public && python3 -m http.server -d public    # the site from those datasets
PYTHONPATH=backend python3 -m airstack.mcp_server data/site    # the local read-only MCP
```

`web/` is the static application. `backend/airstack/` holds the quote check (`quotes.py`), the data paths and the local MCP.
`backend/tools/` renders the pages, feed and stats card from the published datasets.

More: [Architecture](docs/ARCHITECTURE.md), [MCP](docs/MCP.md), [Roadmap](docs/ROADMAP.md), [Contributing](.github/CONTRIBUTING.md),
[Security](.github/SECURITY.md), [Notice](NOTICE.md).

## License

Code is MIT. Source material and quotes remain with their publishers; see [NOTICE.md](NOTICE.md). The published datasets are
released as [open data](https://airstack.bot/open-data/).
