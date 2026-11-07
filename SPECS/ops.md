# Engineering, release and repository

Tests, release controls and repository standards.

## AS-210 · The spec audit keeps tickets and code in sync
DONE · P0

Every piece of code should be explained by a ticket, and every ticket should point at real code and real tests.

- [x] The ticket files in `SPECS/` are the source of truth. Every code file is listed by a ticket and carries a marker naming those tickets.
- [x] A DONE ticket has every criterion ticked and cites a test; every cited file and test exists; every user-facing DONE ticket cites a journey; every journey is defined once and its test exists.
- [x] `python tools/spec_audit.py --fix` rewrites markers; `--table` prints a traceability view on demand.

Files: tools/spec_audit.py
Tests: backend/tests/test_repo.py::test_spec_audit_passes

## AS-331 · Tests that can fail, run in a real browser
IN PROGRESS · P0

A test with an always-true assertion, or a journey that skips when the browser is missing, proves nothing.

- [x] Each journey has an automated test run in headless Chrome against the page served locally. `or True` and every other always-true assertion are removed and a lint fails the build if one returns.
- [x] Playwright is a required development dependency; a missing browser fails the journeys instead of skipping them.
- [ ] The QA procedure walks eight personas (finance lead, sceptical judge, IT administrator, developer, agent, phone user, adversarial user, returning user) through the six views and records what each could and could not do.

Files: backend/tests/test_lint.py, backend/requirements-dev.txt, JOURNEY/__init__.py, JOURNEY/conftest.py, JOURNEY/journey_kit.py
Tests: backend/tests/test_lint.py::test_no_assertion_is_always_true; JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action

## AS-202 · The site deploys as a Worker on airstack.bot, and a release proves production serves the exact build
IN PROGRESS · P0 · user-facing

- [x] The zone is active on Cloudflare; `tools/deploy.sh` ships exactly the public files (a test proves every file the page loads is shipped) and never serves secrets, configuration, backend code or drafts.
- [x] `deploy.sh` never regenerates anything: it requires a clean tree, writes `version.json`, and uses the reviewed Wrangler bundle by exact version and SHA-256. It downloads nothing. `tools/verify_deploy.py` fails unless production's `version.json` is HEAD and every served file is byte-identical to this checkout.
- [x] A `_headers` file revalidates every response and marks HTML `no-transform` so no analytics beacon is injected; a live test proves both, and the release procedure runs the verifier as its last step.
- [x] The release is static-only.

Files: wrangler.jsonc, tools/deploy.sh, web/public/_headers, tools/verify_deploy.py
Tests: backend/tests/test_site.py::test_deploy_ships_every_local_file_the_page_loads, test_headers_protect_the_html_and_leave_scripts_and_data_compressible; backend/tests/test_live_site.py::test_airstack_bot_serves_the_site_over_https, test_secrets_config_and_backend_code_are_never_served, test_cloudflare_does_not_inject_an_analytics_beacon, test_scripts_and_data_are_served_compressed, test_the_domain_is_on_cloudflare, test_production_serves_the_build_in_this_checkout
Journeys: J-13

### J-13 · Open airstack.bot
Who: anyone with the link. Test: backend/tests/test_live_site.py::test_airstack_bot_serves_the_site_over_https

## AS-141 · Public repository checks
DONE · P0

Standard scanners and project checks run before each public release.

- [x] The code lives on GitHub, and CI runs the spec audit, tests and real-browser quality journeys on every push; a red run fails the build. CI downloads no npm executable graph.
- [x] gitleaks runs over full history in CI and on staged changes in a git pre-commit hook; `.gitleaks.toml` allowlists only exact documented placeholder values. The hook also refuses a tracked `.env`, `.wrangler/`, `.DS_Store`, `.venv/` or `node_modules/`.
- [x] A clean, history-free snapshot is built by one small script from what git tracks at HEAD (code and configuration only: databases and saved data are never in the repository, AS-365), and gitleaks runs on the result.
- [x] A behavioural test remains: a key in the environment never reaches an API response or a call log. The Publishing section of `docs/OWNER.md` states what is public, under which licences, and how the public repository is updated.

Files: .githooks/pre-commit, .gitleaks.toml, .github/workflows/ci.yml, docs/OWNER.md, .gitignore
Tests: backend/tests/test_money.py::test_a_key_in_the_environment_never_reaches_an_mcp_answer_or_a_call_log, test_the_real_env_file_is_ignored_and_never_tracked; backend/tests/test_repo.py::test_spec_audit_passes

## AS-142 · Instructions, procedures and subagents are agent skills, tested like code
DONE · P1

Agents orchestrate the work, so the procedures must be explicit, safe and current.

- [x] CLAUDE.md holds the commands, the hard rules (money, secrets, honesty, vocabulary, evidence, less code) and an index of every skill and subagent: six skills and three read-only subagents.
- [x] A test checks that every skill and agent has valid frontmatter and a matching name, that CLAUDE.md indexes them all, that every file they name exists, and that nothing host-specific leaks in. Nothing in the layer can spend money or publish; those steps say to ask the owner first.

Tests: backend/tests/test_pages.py::test_every_skill_and_agent_has_a_matching_name_and_a_description, test_the_index_in_claude_md_lists_every_skill_and_agent, test_every_file_and_tool_they_name_exists, test_the_safety_rules_are_present_and_nothing_host_specific_leaks_in

## AS-130 · Reviewers can inspect the data, not just the code
DONE · P0

- [x] `data/airstack-demo.db` and `data/airstack-demo-export.json` hold facts, verdicts, events, watches, calls and the budget ledger. Every fact is real and sourced; seats are example inputs and the export says so; calls made by the fixture client are labelled as such, never as the model.
- [x] `tools/screenshots.py` captures every surface and state from one build, desktop and mobile, with an index naming route, viewport and state.

Files: backend/tools/build_demo_data.py, backend/airstack/views.py, backend/airstack/spark.py, tools/screenshots.py
Tests: backend/tests/test_data_site.py::test_the_demo_data_is_complete_and_never_claims_a_real_model_call

## AS-332 · A lean, legible repository
DONE · P1

The repository keeps source, configuration and generated working data in clear boundaries.

- [x] The root has at most 15 visible entries; generated site data lives in `data/site/`, outside git, which assemble and verify read.
- [x] Constants that are data (lanes, topics, thresholds, categories) live in `config/`, not in code.
- [x] Production modules have one clear responsibility; test suites are organized by domain with shared fixtures beside them.

Files: pyproject.toml, .github/CONTRIBUTING.md, .github/SECURITY.md
Tests: backend/tests/test_repo.py::test_the_repository_root_stays_small

## AS-338 · Public wording rules: the example never shames a vendor, and certain names never appear
TODO · P1 · user-facing

- [ ] The example's wording says what a plan already includes, not that a named product is bad; reviewed against the five meeting-notes apps' own pages; a journey checks the example's copy.
- [ ] Names the owner has excluded never appear in anything published; a test scans every published file and document for the SHA-256 of each excluded word, so the names themselves never appear in the repository.

## AS-297 · GitHub presentation
IN PROGRESS · P2

A repository is often the second thing a reviewer opens.

- [x] `SECURITY.md` and `CONTRIBUTING.md` in `.github/` (where GitHub looks for them), and `docs/ARCHITECTURE.md` with one diagram, linked from the README.
- [x] Every count in the README matches the data the site is built from (`test_numbers.py`), and CONTRIBUTING.md names every builder the daily run uses.
- [ ] The deployed site states the same counts (true only once this change is deployed).
- [ ] A tagged v1.0 release with notes, and a social preview image.

Files: .github/SECURITY.md, .github/CONTRIBUTING.md, docs/ARCHITECTURE.md
Tests: backend/tests/test_site.py::test_every_counted_sentence_in_the_readme_and_llms_txt_states_the_number_in_numbers_json, test_the_daily_run_updates_counts_but_leaves_release_to_a_person

## AS-355 · Remaining reviewer correctness items
IN PROGRESS · P1

Endorsed review items still open.

- [x] Superseded: databases and page text are never published (AS-365), so nothing needs scrubbing or replaying for a public copy, and the snapshot is exactly what git tracks at one commit (AS-141).
- [ ] An edited public assessment says so, with the date.
- [ ] Every selected need is named in the explanation.
- [ ] Movers sorts without rebuilding the list.

Files: backend/airstack/corpus.py

## AS-360 · The code is open source under the MIT licence, held by OttObottr
IN PROGRESS · P2

The repository is intended to be public. The licence names the holder and covers the code; data and third-party marks keep their own terms, stated in NOTICE.md.

- [x] `LICENSE` is the MIT licence with the copyright holder "OttObottr".
- [ ] NOTICE.md states which data is under which licence and that third-party marks are excluded (checked against the final public tree).
- [ ] Nothing is made public without the owner's explicit go-ahead.

Files: LICENSE, NOTICE.md

## AS-364 · Schemas change in place, and names carry no version suffix
TODO · P2

A second copy of a table or file with a version in its name leaves two sources of truth.

- [ ] Table, column, file and function names carry no `_v2` style suffix; a schema change edits the schema and migrates the data in place.
- [x] Specs contain current contracts only; retired ids and implementation archaeology are removed.

## AS-365 · All data stays out of the code repository, with a production-to-local backup
DONE · P2

Generated data, databases and raw captures are large, change daily and are not source code. The repository tracks code, curated configuration (config/) and site assets only.

- [x] The repository tracks no generated data, saved responses or database: they live in data/ (AIRSTACK_DATA relocates it), which git ignores; only the explicit `config/published-files.json` allowlist can leave data/site/. Tests fail if data is tracked or an unapproved file enters the publication snapshot.
- [x] `tools/data_pull.sh` stages the published datasets with portable checksum tools, requires the repository-pinned release manifest, refuses unsafe paths, active JavaScript/XML, oversized snapshots and checksum mismatches, and replaces the local snapshot only after every file passes. Assembly independently refuses symlinks, non-regular files, unapproved names and malformed payloads before a builder reads or copies them.
- [x] `tools/backup.sh` writes a dated archive of everything private (saved responses, intermediate files, both databases) with a checksum; a test restores a sample byte for byte, and the first real archive was restored and compared (the paid database is identical).
- [x] The daily job commits no data and has no spend, pull, push or deploy authority. It backs up weekly; paid extraction and production release are manual, separately reviewed actions.
- [x] Tests that need private data are marked and skip, with the reason, on a checkout that lacks it; nothing else is skipped.

Files: tools/data_pull.sh, tools/validate_published_data.py, tools/backup.sh, tools/daily.sh, tools/assemble.sh, backend/airstack/paths.py, backend/tests/conftest.py
Tests: backend/tests/test_repo.py::test_the_repository_tracks_code_and_configuration_only, test_a_backup_restores_every_file_byte_for_byte, test_data_pull_fetches_the_datasets_and_refuses_a_file_that_does_not_match_its_checksum, test_data_pull_refuses_paths_outside_the_snapshot_and_executable_data, test_assembly_refuses_an_ignored_dataset_symlink_before_copying_it, test_the_scheduled_refresh_cannot_spend_pull_push_or_deploy
