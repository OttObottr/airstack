# Specs

The ticket files in this folder are the source of truth for what AirStack does, how each behaviour is proved, and what is not built.

| File | Area |
|---|---|
| `record.md` | The append-only record, the verdict engine, expiry, evidence chain |
| `money.md` | Spend guards, the account ledger, secrets |
| `trust.md` | Privacy, publication rules, polite fetching, web security |
| `mcp.md` | Local read-only MCP |
| `research.md` | Data collection: profiles, prices, directory, news, freshness |
| `pages.md` | Crawlable pages for products, makers, categories, comparisons |
| `app.md` | The app: landing, answer, search, market views, polish |
| `ops.md` | Audits, tests, deploy, publishing, repository |
| `roadmap.md` | Planned work, each with its reason |

A ticket is one `## AS-nnn · Title` section:

```
## AS-nnn · Title
DONE · P0 · user-facing        status (DONE, IN PROGRESS, TODO), priority, optional user-facing flag

Why, in one paragraph.

- [x] A criterion that is true and proved (or [ ] when it is not yet).

Files: paths or globs that implement it
Tests: path::test_name, another_name; other/path::test_name
Journeys: J-nn            automated walkthroughs that prove it (user-facing tickets)

### J-nn · Title            the journey itself, in the ticket that owns it
Who: ... Test: JOURNEY/test_journeys.py::test_name
```

`python tools/spec_audit.py` checks both directions and prints OK with zero gaps: every code file is cited by a ticket and carries a `spec:` marker on its first lines;
every cited file and test exists; a DONE ticket has every criterion ticked and cites a test; a user-facing DONE ticket is proved by an automated journey;
`--fix` rewrites the markers. `--table` prints a traceability view.
