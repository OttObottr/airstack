---
name: airstack-specs
description: Use to add or change a ticket, journey, or document: the specs are the source of truth and are audited against the code both ways. Use whenever behaviour changes.
---
# Specs

- The ticket files in `SPECS/*.md` are the source of truth; edit them directly using the format in `SPECS/README.md`.
- A ticket states why, the criteria (`[x]` only when proved), the `Files:` that implement it and the `Tests:` that prove it. Every code file starts with `spec: AS-...` naming the tickets that cite it; `.venv/bin/python tools/spec_audit.py --fix` rewrites the markers, and `--table` prints a traceability view.
- A DONE ticket cannot have an unticked criterion and must cite a test that passes: move open work to a TODO or IN PROGRESS ticket instead of loosening the audit.
- A user-facing DONE ticket is proved by a journey: a `### J-nn` section inside the ticket, citing a real test in `JOURNEY/test_journeys.py`.
- Generated site datasets compute their own markers from the tickets that list them; regenerate after changing tickets.
- State plainly what is not built. Planned items stay TODO with their reason; never mark them done to make a table look complete. Write specs as a public engineering record: plain prose, no slang, no quoted instructions, no internal shorthand, no competitor names, no dollar figures except sourced list prices.
