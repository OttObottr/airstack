---
name: airstack-release
description: Use to release AirStack from a reviewed commit through tests, static deployment and production verification.
---
# Release

A failed gate stops the release.

1. Rebuild public data without live/model calls and validate the complete allowlisted snapshot.
2. Run the full tests, journeys, spec audit, lint, secret scan and Lighthouse checks.
3. Commit on a branch, review the diff, merge to `main`, and require green CI. Never include local state or private operating evidence.
4. `tools/deploy.sh` publishes static assets from the clean tested commit. It never downloads executable tooling during release.
5. Verify production files, commit identity, manifest, headers, routes and the core desktop/mobile journeys. Hosted MCP is not part of the default release.

Report only what this run observed as VERIFIED; otherwise use BLOCKED or UNBUILT.
