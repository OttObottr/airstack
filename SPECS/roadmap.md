# Planned work

Tickets that describe work not yet built. Each stays TODO or IN PROGRESS with its reason; nothing here is marked done to make a table look complete.

## AS-287 · Capability models beyond meeting notes
TODO · P1 · user-facing

Renewal verdicts and the coverage map need a sourced model of each category's requirements and which platform plans bundle them.

- [ ] Each new category has 4 to 8 requirements and a record of which platform plans include each (with quote, plan and date), drafted by the model and approved by a person before any verdict cites it.
- [ ] First candidates: password managers, forms, scheduling, e-signature, whiteboards, screen recording, status pages, transcription.
- [ ] An absorption matrix shows, per platform and category, the share of requirements bundled; unknown cells are hollow.

## AS-288 · Trust for what you would install
TODO · P1 · user-facing

Repository checks are practices, not a malware verdict. The installable artifact is what matters.

- [ ] Each open-source candidate's packages are resolved through deps.dev and checked in OSV (including malicious-package records) by version; only an OSV record or advisory may say "reported", with its link.
- [ ] Provenance (npm and PyPI attestations) is shown as verified, not checked or absent; a new release invalidates the previous check.
- [ ] MCP `trust(repo or package)` returns the checks with dates; nothing in the review runs the project's code.

Files: backend/tools/build_trust.py
Tests: backend/tests/test_data_graph.py::

## AS-289 · The market map over time, and a list-price index
TODO · P2 · user-facing

A live market should be seen moving, which needs stored history rather than inference.

- [ ] A control switches colour between change against the 4-week level, against last week and against 26 weeks ago; play steps through the weeks with tiles in place. Weeks with no stored observation are hatched, never interpolated.
- [ ] A list-price index per category over time, each point a quoted list price from an archived snapshot of the vendor's own pricing page, linked; gaps stay gaps.

Files: backend/airstack/connectors/registries.py, backend/tools/build_movers.py
Tests: backend/tests/test_data_chain.py::

## AS-291 · The open index: one identity per product, its integrations and stacks seen together
TODO · P1 · user-facing

"Everything" means identities with links and measured numbers for the many, verified facts for the important, and verdicts where a model exists.

- [ ] Products resolve by domain first, then repository, then name and maker with a confidence class; listings never inflate the product count; every card shows its state: identified, measured, researched or judged.
- [ ] A product page lists what it says it integrates with, linked where AirStack has the other product and labelled as the vendor's claim; MCP `related(tool)` returns edges of five kinds (covered by, integrates with, alternative, open-source candidate, seen together), each with source and date.
- [ ] Pairs and triples are counted from public dependency manifests and labelled "seen together in N repositories, month"; comparison articles and integration listings never count.

Files: backend/tools/build_graph.py, data/site/graph.json
Tests: backend/tests/test_data_graph.py::

## AS-292 · An Atom feed of changes, per-product badges and a monthly open-data release
TODO · P2 · user-facing

Agents and other sites should be able to follow and cite what changed.

- [ ] `/changes.atom` lists verified changes with sources; a badge per product shows its fact count and check date and links to its evidence chain.
- [ ] A monthly release publishes facts, taxonomy and capability models under CC BY with a changelog.

Files: backend/tools/build_feed.py, data/site/badges.json, data/site/changes.atom, data/site/open-data
Tests: backend/tests/test_data_graph.py::

## AS-295 · Social and podcast signals through official channels only
IN PROGRESS · P1 · user-facing

Community signals improve the daily content, but scraping them is not allowed and their APIs cost money or need review.

- [x] The zero-cost layer uses stored Wikidata channel records, Hacker News stories and GitHub repository activity, each with source and read window. Channel presence, discussion, repository attention, adoption and endorsement are different fields and are never blended into a score.
- [x] Reddit, X and Threads conversation connectors remain off internally until official access, storage rights and a hard cost ceiling are reviewed. The product does not render empty source rows; it shows only discussion evidence it actually has. Nothing is scraped, browser-automated or bought from an unofficial reseller.
- [x] Muse or a web-search provider may later discover a discussion URL, but a model/search result is a lead rather than a canonical mention count. Exa and Muse connectors are default-off and may not run inside a page request or an unattended public endpoint.
- [x] `config/social-connectors.json` records each platform's state, permitted published fields, cost boundary and retention decision. Public and visitor-triggered fetches and automatic recharge are forbidden; every metered source is off until an owner-approved private ceiling and terms review exist, and no connector falls back to scraping.
- [ ] Podcast episode titles from public search and newsletters' own feeds, matched to listed products by name and domain, are shown as "discussed" with source and date and never counted as use or adoption.

Files: config/social-connectors.json, backend/tools/build_community.py, backend/tools/build_news.py, backend/tools/build_oss.py, backend/tools/pages/category.py, data/site/community.json, data/site/news.json, data/site/oss.json, web/src/components/cards/catalog.js
Tests: JOURNEY/test_journeys_products.py::test_j80_a_product_separates_known_channels_measured_attention_and_omits_unmeasured_sources; backend/tests/test_data_site.py::test_social_sources_keep_channel_attention_and_adoption_as_different_claims; backend/tests/test_repo.py::test_social_connectors_are_static_only_and_every_metered_source_is_off

## AS-300 · Remaining connectors, switch history and learned lanes
TODO · P2

The watchlist needs raw facts from every free source, and categories should come from who actually switches to what.

- [ ] The remaining connectors (GitHub changelog, OpenRouter, Vercel AI Gateway, Hugging Face, GitHub releases, npm, PyPI, Docker Hub, crates.io, Homebrew, deps.dev) each produce dated, linked facts, each with a recorded-fixture test.
- [ ] A one-year backfill stores dated A-to-B dependency switches from public repositories with commit links, within the rate limits.
- [ ] Lanes are clusters learned from switch pairs ("learned from N switch events since a date"), each citing its events; each lane's KPIs are the metrics that best predicted real switches, re-ranked monthly.
- [ ] Erosion pages show "N of M capabilities covered" with each capability and its evidence; a real Orbit shows repositories and commit links, never names, and counts only independent production switches.

## AS-311 · Native apps: Mac first, iPhone companion
TODO · P3 · user-facing

After launch. The native surface is the alert, not a dashboard. Today the site already installs as a web app on both.

- [ ] One shared Swift client with platform-specific screens; the server keeps monitoring, research and model calls; opening a screen never triggers a model call and the app holds no key or admin token.
- [ ] Offline results say "last synchronized at", never "current"; an older push never overwrites a newer verdict.
- [ ] Private seats can be evaluated on-device; lock-screen alerts use generic wording by default; a stack import creates candidates the user confirms.

## AS-312 · Accounts, organizations and private MCP access
TODO · P2 · user-facing

Accounts add memory, not access: a visitor never hits a wall, and sign-in is offered only at "Track this stack".

- [ ] If accounts are ever added, design them as a separate product boundary with minimal scopes, export and deletion; the current static application and local MCP remain account-free.
- [ ] Organization workspaces with four roles (owner, admin, editor, viewer); the last owner cannot be removed; invitations expire, are revocable and single-use; an email domain never grants a role by itself; organization admins never see personal workspaces.
- [ ] An agent reads a selected workspace with an AirStack-issued, read-only, revocable grant following the MCP authorization specification; private stacks never enter public search, exports, other workspaces' caches or statistics.

## AS-320 · Displacement ledger and market intelligence
IN PROGRESS · P2 · user-facing

The same engine as an analyst surface. Every number carries a unit, population, window, source and as-of date.

- [x] A page cache with conditional GETs and a model memo mean nothing is re-fetched or re-extracted (AS-327); a first tranche of 6 pages was read by eye, then the rest, with a stop below a 90% verification pass rate (the run passed at 90.4%).
- [ ] Feeds across vendors, classify before extract, dated absorption rows confirmed by `verify_references`.
- [ ] A markets table, a capability map with the date each vendor gained each capability (blank where unsourced), displacement records that separate could-replace from observed switching, and a private overlay that re-answers the market for your plans.

## AS-323 · Tell me the day it changes
TODO · P2 · user-facing

The alert is the product: a watch on the condition in "This changes if".

- [ ] An email or push the day a watched condition trips, with the source; no email field ships until the alert actually sends.
- [ ] If the owner chooses a paid tier, the owner decides price and provider and nothing is charged before then; no dollar figure appears on the public page except sourced list prices.

## AS-324 · Workflow tests and consented outcomes
TODO · P2 · user-facing

Original measurement rather than summarised claims.

- [ ] Versioned inputs, acceptance rules and configurations run against competing products; output artifacts kept; repeated trials; objective checks first, blinded review for subjective quality; untested requirements shown as untested.
- [ ] Opt-in decision and outcome records (recommended, evaluated, rejected, adopted, retained, reversed) kept privately, with aggregates only above minimum sample sizes and decisions not to switch kept as well as successes.

## AS-336 · Published benchmarks, quality numbers and head-to-head journeys
TODO · P1 · user-facing

The numbers a sceptical reader would ask for should already be published, and claims of being better need numbers anyone can rerun.

- [ ] 20 seat-specific questions with locked answer keys, 5 runs with and without AirStack's tools, scored by code; detection lag, recall and precision of watch conditions on replayed events; cost per real change from the ledger. Each benchmark is a script, its inputs and its result file.
- [ ] A quality page: precision per field on a golden set, corroboration rate, disputes with both values, median and 95th-percentile freshness per tier, the corrections log and the takedown path.
- [ ] Measures only AirStack can publish: time to absorption, expiry rate of standing answers, which requirement most often keeps the incumbent, verification pass rate.
- [ ] A written protocol compares named products on named axes with real, dated ground truth; captures are saved with timestamps and no bot check is bypassed.

Journeys: J-10

### J-10 · Head-to-head against review sites and a cold agent
Who:  Test: none (protocol only, not automated)

Same questions, same day, same scoring for every product. Each question has a ground truth from a real, dated event:

Axes, each scored by a script from saved captures: right answer for the seat; shows a date; shows a source a stranger can open; says what would change the answer; same answer on three runs.
Rules: save every capture with a timestamp; never bypass a CAPTCHA or bot check; if a site can't be read, record that instead of guessing.

## AS-356 · The pitch and what comes after
IN PROGRESS · P2

The write-up needs one pitch line everyone repeats and a plain account of how the product stays honest as a business.

- [x] One pitch line used in the README and the film: “AirStack turns the software market into sourced intelligence—organized around the tools your team actually uses.”
- [ ] A short section on the possible paid tier, the privacy model, no vendor money and no affiliate links.

## AS-359 · Deferred, with the reason
TODO · P3

Asked for and deliberately not built now; the reason belongs in the specs.

- [ ] Each deferred item (GPU effects, shadcn, CDN visual effects, vendor-paid alerts) is listed with why (no external dependencies, no vendor money) and what would change it.
