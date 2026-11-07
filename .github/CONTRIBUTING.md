# Contributing

## Setup
```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r backend/requirements-dev.txt
git config core.hooksPath .githooks
tools/data_pull.sh
```
Contributions require no credentials. Maintainers run live research and tests that use private source records.

## Tests
```bash
.venv/bin/pytest -q backend/tests JOURNEY
```
Generated datasets remain outside git. Changes to builders should include focused fixture coverage; maintainers rebuild and validate the published snapshot.

## The spec rule
Every behaviour is a ticket in `SPECS/`; `tools/spec_audit.py` checks tickets against code, tests and journeys.
- A ticket names its checks, the files that implement it and the tests that prove it.
- Every code file's first line names the tickets that cite it (`# spec: AS-123`, or `// spec: AS-123` in JavaScript).
- `.venv/bin/python tools/spec_audit.py --fix` must pass. `--fix` rewrites file markers.
- A user-facing ticket is DONE only when a journey in `JOURNEY/` proves it with a real test.

Keep the rules in `CLAUDE.md`: unknown stays unknown, no dollar amounts on screen except sourced list prices, and the verdict words are BUILD, BUY, KEEP and RETIRE.
