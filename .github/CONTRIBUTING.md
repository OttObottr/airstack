# Contributing

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r backend/requirements-dev.txt
git config core.hooksPath .githooks
.venv/bin/ruff check backend tools
.venv/bin/pytest -q
```

The tests run on the synthetic datasets in `backend/tests/fixtures/site` and need no credentials or download. Set `AIRSTACK_DATA` to
a data directory (for example after `tools/data_pull.sh`) to run them on the published data. Browser tests run real Chrome.
A change to a renderer comes with a fixture case. Fixtures use invented products and `example.com` addresses.

## Rules
- Unknown stays unknown: never a zero, a pass or a recommendation. "Not observed" is a value.
- A fact exists only if its quote is on its own page, shown with its source and the date the page was read.
- No dollar amounts on screen except sourced list prices.
- Report what you observed running as verified; anything else as reviewed only, blocked or unbuilt.
- Never commit a secret, a key or a database.
