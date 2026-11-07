# Trust, privacy and security

The publication, privacy and data-handling rules behind AirStack.

## AS-072 · Public surfaces read only explicit public records
DONE · P0

An anonymous request must never read a private stack, and a context-free call must never enumerate stored seats.

- [x] Every verdict has a visibility, private by default; public pages, the changes feed, stack review and MCP read only public verdicts.
- [x] Search during a reassessment carries no seat context; only the judge sees requirements, and that log entry is redacted.
- [x] The demo database holds only explicit public example seats.

Files: backend/airstack/store.py, backend/airstack/views.py, backend/airstack/mcp_server.py
Tests: backend/tests/test_truth.py::test_context_free_mcp_calls_never_enumerate_private_seats, test_reassessment_search_carries_no_seat_context

## AS-223 · A third-party review never reaches a public reason, citation or source list
DONE · P0

Anything that reaches a reason or citation can be read as AirStack's own claim. A blog's allegations must never be one.

- [x] A publication hold cleans every public projection (page data and MCP data) and leaves stored records untouched: commentary hosts are dropped as sources, evidence rows and search results, citations to them are dropped, and allegation sentences are removed from prose in AirStack's own voice.
- [x] The hold is idempotent, does not change its input, and leaves legitimate facts untouched; a release test fails if any generated public file carries withheld content.

Files: backend/airstack/publication.py, backend/tools/build_site_data.py
Tests: backend/tests/test_data_market.py::test_commentary_sources_and_the_citations_that_point_at_them_are_dropped, test_an_allegation_sentence_is_removed_from_prose_only_and_the_rest_of_the_reason_stays, test_no_generated_public_file_carries_withheld_content; JOURNEY/test_journeys_quality.py::test_j35_no_verdict_reason_repeats_a_third_party_review_or_a_banned_word

## AS-233 · A claim the rules reject today is never shown, however it was admitted
DONE · P0 · user-facing

A quote being on a page is not the same as the quote supporting the claim. Rules grow over time, and old claims must be re-judged by the current rules.

- [x] A free plan is admitted only when the quote says free or zero a month; trials, credit-card wording and one-time credits are not a free plan. A description is not code; a ratings count is not a user count; a footnote, a download button for the reader's own system, navigation text, a certification in progress and a launch date are not values.
- [x] `failing_now()` replays today's rules over stored page text (free, no model); profiles, the chain and the headline counts skip what it rejects, and publish how many each rule hid. Stored rows stay as the record.
- [x] The page says a quote was found on its page, never "verified"; a text match is not independent confirmation, and counts say how many claims are withheld.
- [x] Golden tests use the real quotes that fooled the pipeline.

Files: backend/airstack/corpus.py, backend/tools/build_market_data.py, backend/tools/build_chain_data.py, web/src/components/chain.js, web/src/components/profile.js
Tests: backend/tests/test_data_market.py::test_a_trial_one_time_credits_or_pay_as_you_go_is_not_a_free_plan, test_a_free_plan_is_admitted_when_the_quote_says_free_or_zero_a_month, test_claims_admitted_under_older_rules_are_found_by_replay_and_never_counted, test_no_public_file_shows_a_claim_that_todays_rules_reject, test_a_download_button_for_the_readers_system_is_not_the_products_platform_list, test_models_are_models_not_vendors_footnotes_or_the_product_itself, test_a_trial_or_credits_never_reads_as_a_free_plan_and_a_contrary_page_leaves_it_unknown, test_a_certification_in_progress_is_not_held; JOURNEY/test_journeys_products.py::test_j36_a_tool_without_a_replacement_check_states_its_coverage_first, test_j48_a_profile_shows_what_its_quotes_mean_not_the_page_furniture_they_came_from
Journeys: J-30, J-39

### J-30 · What can you tell me about this tool?
Who: Someone searching for a developer tool that has no replacement check yet. Test: JOURNEY/test_journeys_products.py::test_j36_a_tool_without_a_replacement_check_states_its_coverage_first

### J-39 · A fact means what its quote says
Who: Anyone reading a researched product. Test: JOURNEY/test_journeys_products.py::test_j48_a_profile_shows_what_its_quotes_mean_not_the_page_furniture_they_came_from

## AS-274 · Read the web politely, and publish only what its terms allow
DONE · P0

A compliance review found fetchers presenting as a browser, no robots.txt checks, store pages read against their terms, and quotes longer than a short excerpt.

- [x] Every page read goes through `backend/airstack/fetch.py`: one honest user agent with a contact URL, robots.txt per host (an unreadable one closes the host), Retry-After honoured, bodies capped.
- [x] Hosts whose terms bar automated reading are never fetched; a daily sweep records pages that disallow robots and withholds their facts and prices from public files.
- [x] A quote is at most 25 words, enforced on admission and on publication. NOTICE.md states each source's licence.

Files: backend/airstack/fetch.py, backend/airstack/corpus.py, backend/airstack/files.py, backend/tools/build_pricing.py, backend/tools/build_market.py, data/robots-disallowed.json, NOTICE.md, tools/daily.sh, backend/airstack/paths.py
Tests: backend/tests/test_data_chain.py::test_robots_txt_is_obeyed_and_a_disallowed_page_is_never_requested, test_a_missing_robots_txt_allows_and_an_unreadable_one_closes_the_host, test_no_fetcher_pretends_to_be_a_browser

## AS-280 · Web and data boundaries
IN PROGRESS · P0

External text is treated as data. The browser application has no runtime package dependencies.

- [x] Every SQL value is a bound parameter and every table or column name passes `ident()`; a lint rule for formatted SQL runs in CI and in the tests.
- [x] No package manifest or lockfile; nothing loads from another origin; `script-src` is exactly 'self' with no inline script.
- [ ] Scraped text reaches the page escaped, and links built from scraped URLs are only http or https (the static check `test_every_scraped_url_goes_through_the_scheme_check` fails on the current tree after the page was split into modules and must be updated); a journey feeds script payloads and `javascript:` URLs into every field and sees nothing run and no CSP violation.
- [x] Every response carries HTTPS-only, no framing, no plugins or device APIs and a CSP confined to the site; journeys run against the real `_headers`.

Files: pyproject.toml, backend/airstack/store.py, .github/workflows/ci.yml, tools/assemble.sh, web/public/_headers, wrangler.jsonc, web/src/lib/format.js
Tests: backend/tests/test_lint.py::test_no_sql_is_built_from_strings, test_the_page_has_no_package_dependencies, test_no_inline_script_runs_and_every_script_comes_from_this_origin; backend/tests/test_site.py::test_deploy_ships_every_local_file_the_page_loads, test_security_headers_are_on_every_response, test_every_scraped_url_goes_through_the_scheme_check; JOURNEY/test_journeys_quality.py::test_j33_external_text_is_rendered_as_inert_content
