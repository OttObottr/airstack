# Record and verdict engine

How AirStack stores what it knew and when, decides renew-or-replace answers by rules, and schedules evidence rechecks.

## AS-010 · Facts, verdicts and lifecycle events are append-only
DONE · P0

The audit trail is the product. If a fact, a verdict or its history could be edited, AirStack could quietly rewrite what it knew and when.

- [x] Updating or deleting a fact is refused by the application and by the database itself (raw SQL included).
- [x] A fact stores its source URL, the source's own timestamp when one exists, when AirStack observed it, and a hash of its value; the page recomputes the same hash in the browser.
- [x] A saved verdict's action, reason, evidence, conditions and requirements cannot change; only lifecycle fields (status, last verified, deadline, lapsed and superseded times) move; verdicts are never deleted.
- [x] Publishing, lapsing and superseding each append an event with its time and cause; events cannot be edited or deleted.

Files: backend/airstack/store.py
Tests: backend/tests/test_truth.py::test_facts_are_append_only, test_hash_matches_the_hash_the_page_shows, test_verdict_content_is_immutable_and_never_deleted, test_every_lifecycle_change_is_an_append_only_event

## AS-012 · Every verdict cites dated, linked evidence on four separate clocks
DONE · P0

A verdict nobody can check is an opinion. Each one points at sources a stranger can open, and keeps apart the different times that matter.

- [x] A verdict without evidence, or with evidence missing a URL or a timestamp, is refused; every evidence row in every output has both.
- [x] Publication time, effective time, observation time and evaluation time are stored separately; an unknown publication time is shown as the fetch time and labelled so, never invented.

Files: backend/airstack/store.py, backend/airstack/evaluate.py, backend/airstack/views.py, backend/airstack/engine.py, backend/airstack/connectors/workspace_updates.py
Tests: backend/tests/test_truth.py::test_a_verdict_without_a_source_url_and_timestamp_is_refused, test_four_clocks_are_kept_apart, test_every_evidence_row_in_every_api_output_has_a_url_and_a_timestamp

## AS-013 · Replays and live answers are labelled, and a live answer shows a real re-read date
DONE · P0

AirStack can say what it recorded on a given day, and must never show a replay clock as if it were today.

- [x] Asking for a verdict "as of" a date returns the revision current then, labelled as a historical replay reconstructed from recorded revisions; a normal request is never labelled as a replay.
- [x] `tools/verify_references.py --record` re-reads every real evidence page, confirms the quoted phrase is still on it, and only then stamps the real time; nothing is stamped if any reference is broken.
- [x] A live answer's source date is its last real re-read; the publication date travels separately; a test fails if any check date on a live answer is more than 30 days before the build.

Files: backend/airstack/store.py, backend/airstack/views.py, backend/tools/verify_references.py, backend/tools/build_site_data.py, backend/tools/build_market_data.py
Tests: backend/tests/test_truth.py::test_historical_replay_is_labeled_and_returns_the_verdict_as_of_the_date; backend/tests/test_site.py::test_no_live_answer_shows_the_replay_clock_as_its_check_date

## AS-030 · One evaluate() decides, and RETIRE needs every requirement covered
DONE · P0

Telling someone to cancel a tool is the costliest mistake the product can make, so the rules are strict and shared by every surface.

- [x] One function computes public, seat and stack decisions and returns the uncovered requirements by name.
- [x] Each requirement is pass (evidence says yes), fail (evidence says no) or unknown (no fact yet); a missing fact is unknown, never fail.
- [x] RETIRE needs every requirement to pass; any uncovered requirement gives KEEP with the list filled in; saving a RETIRE with an uncovered requirement is refused.
- [x] If any requirement is unknown and none fails, nothing is published and the decision stays lapsed, with no model call.
- [x] A requirement may name an entitlement that the seat must hold; a fact effective after the evaluation time counts as unknown; a KEEP resting on the alternative failing is labelled a provisional hold.
- [x] Worked example: an English, in-person, Android seat on a qualifying plan becomes RETIRE after Google's change; the same seat on iOS stays KEEP, because on that day the feature had only started on Android.

Files: backend/airstack/evaluate.py, backend/airstack/views.py, backend/airstack/store.py, backend/airstack/engine.py, backend/airstack/schemas.py, backend/tools/build_demo_data.py
Tests: backend/tests/test_truth.py::test_retire_only_when_every_seat_requirement_is_covered, test_seat_a_retires_fireflies_and_seat_b_keeps_it_after_the_event, test_an_ios_seat_is_not_told_to_retire_on_the_announcement_day, test_each_requirement_is_pass_fail_or_unknown_and_only_all_pass_retires, test_insufficient_evidence_publishes_no_new_verdict, test_retire_needs_the_seat_to_hold_the_entitlement, test_a_capability_effective_in_the_future_is_not_yet_coverage, test_the_public_review_schema_accepts_an_entitlement_requirement, test_an_added_uncovered_job_changes_the_outcome, test_keep_is_labelled_a_provisional_hold; backend/tests/test_money.py::test_every_mcp_tool_makes_zero_spark_calls

## AS-032 · The judge explains; the evidence decides
DONE · P0

Models write well and can still be wrong. The action comes from requirement coverage; the model writes the reason and cites sources.

- [x] A judge that proposes a different action than the evidence supports leaves the verdict lapsed; it may cite only evidence ids that exist, including at least one piece of the new evidence.
- [x] The judge receives each fact's typed value, source URL and dates plus requirement statuses; a search result counts only if its URL is among the provider's citations.
- [x] A judge below 0.7 confidence publishes nothing; code still decides the action and cannot be overridden on a missing entitlement or stale input.

Files: backend/airstack/engine.py, backend/airstack/evaluate.py, backend/airstack/spark.py
Tests: backend/tests/test_truth.py::test_judge_cannot_overrule_the_evidence, test_the_judge_sees_values_requirements_and_entitlements, test_a_search_result_the_provider_never_returned_is_not_evidence, test_a_low_confidence_judge_blocks_publication

## AS-232 · The judge cites only allowed source classes
IN PROGRESS · P1

Commentary and user-written pages must not be what a stored verdict rests on, even though they are removed from public surfaces.

- [x] `publication.source_class()` names the class of every source: vendor, platform maker, store, registry, or regulator or court. Unknown is never citable, user content is never citable, and a shared host is never a vendor.
- [x] A judge that cites any other class is held: the verdict stays lapsed, the stored outcome names each reference and host, and the public projection says "a third-party review".
- [ ] The same check applies on first research (`research.py`).
- [ ] The fourth verdict is re-issued over facts already stored, with the old row kept as superseded (needs the owner's explicit approval to spend).

Files: backend/airstack/publication.py, backend/airstack/engine.py
Tests: backend/tests/test_truth.py::test_a_judge_that_cites_a_source_outside_the_citable_classes_is_held_and_says_why, test_a_due_recheck_never_reissues_a_verdict_that_rests_on_an_uncitable_source; backend/tests/test_data_market.py::test_only_the_vendor_the_platform_maker_a_store_a_registry_or_a_regulator_or_court_is_citable, test_the_vendor_is_its_own_homepage_site_never_the_platform_it_is_hosted_on, test_a_held_outcome_reaches_the_page_without_the_commentary_host_it_names, test_the_stored_verdict_that_rests_on_a_review_is_exactly_what_the_gate_now_holds

## AS-040 · Verdicts lapse before anyone re-thinks them, and expired advice never reads as current
DONE · P0

The product's promise is advice that knows when it is out of date. Old advice stops being current before a new answer exists.

- [x] When a relevant fact arrives, every affected verdict is lapsed before the first model call; a verdict is never current while it is being re-judged.
- [x] Each verdict stores structured recheck conditions; a value that moves without flipping a condition leaves it current, and a new fact matching a capability condition lapses a verdict that never depended on it.
- [x] An unchanged poll makes no model call and never moves the last-verified date or the deadline; a failed re-check keeps the verdict lapsed with its old date.
- [x] A current verdict read after its deadline is reported overdue even if no worker has run; replays and the page's MCP preview use the replay clock, never today's.

Files: backend/airstack/engine.py, backend/airstack/evaluate.py, backend/airstack/views.py, backend/airstack/mcp_server.py
Tests: backend/tests/test_truth.py::test_changed_dependency_lapses_the_verdict_BEFORE_any_reevaluation, test_dependency_hash_moves_but_the_condition_does_not_flip_so_it_stays_current, test_unrelated_fact_leaves_verdicts_current_and_costs_nothing, test_a_brand_new_capability_fact_lapses_a_verdict_that_never_depended_on_it, test_unchanged_sync_makes_zero_spark_calls_and_confirms_last_verified, test_due_recheck_runs_when_unchanged_inputs_go_stale_and_reissues_on_clean_result, test_daily_unchanged_polls_cannot_postpone_the_recheck_forever, test_failed_recheck_leaves_verdict_lapsed_and_never_bumps_last_verified, test_failed_connector_never_confirms_a_verdict, test_weak_evidence_stays_lapsed, test_an_expired_verdict_is_never_read_as_current, test_a_failed_due_recheck_leaves_the_verdict_lapsed, test_golden_demo_every_screen_state

## AS-044 · A grounded re-issue supersedes the old verdict in one atomic step
DONE · P0

The new answer must link to the one it replaces, rest on a search that really happened, and never be published from stale inputs or twice.

- [x] One transaction re-checks the inputs, inserts the successor and supersedes the predecessor, or does nothing; a predecessor has at most one successor, even against a raw insert; two workers publish at most once.
- [x] The successor records the call ids that produced it; if the search did not actually run, nothing is published.
- [x] A fact that arrived during re-judging refuses publication and leaves the decision lapsed for the next pass.
- [x] Classify and search questions are asked once per tool per run and shared by every seat; if the rules change an action the change is material by definition and no classify call is made.

Files: backend/airstack/engine.py, backend/airstack/store.py, backend/airstack/evaluate.py, backend/airstack/views.py
Tests: backend/tests/test_truth.py::test_successful_recheck_creates_a_new_verdict_and_supersedes_the_old, test_an_ungrounded_search_cannot_publish_a_verdict, test_an_answer_built_on_older_inputs_is_never_published_as_current, test_stale_inputs_at_the_publication_boundary_publish_nothing, test_the_same_predecessor_can_have_only_one_successor, test_two_workers_on_separate_connections_publish_at_most_once, test_a_rules_hold_never_carries_the_old_reason_and_never_claims_a_judge, test_due_recheck_runs_when_unchanged_inputs_go_stale_and_reissues_on_clean_result, test_changed_dependency_lapses_the_verdict_BEFORE_any_reevaluation, test_golden_demo_every_screen_state

## AS-070 · The workspace-updates connector supplies the headline fact with its own timestamp
DONE · P0

The worked example's key fact must come from the vendor's own feed with the vendor's own time.

- [x] The connector parses Google's Workspace Updates feed; the in-person notes post becomes a fact scoped to Android, with the post's link and its published time converted to UTC.
- [x] It is tested against the real entry recorded from the feed.

Files: backend/airstack/connectors/__init__.py, backend/airstack/connectors/workspace_updates.py
Tests: backend/tests/test_truth.py::test_golden_demo_every_screen_state, test_the_connector_can_ask_the_feed_for_a_date_window

## AS-080 · The golden demo test
DONE · P0

If this passes, the recorded walkthrough cannot surprise anyone.

- [x] The script replays on fixtures and asserts each state: current, lapsed, re-judged, split, MCP.
- [x] The page's data agrees with what the engine produces, and while a verdict is lapsed MCP reports it as lapsed.

Files: backend/tests/conftest.py
Tests: backend/tests/test_truth.py::test_golden_demo_every_screen_state, test_the_pages_demo_data_agrees_with_the_engine, test_while_lapsed_mcp_never_serves_the_old_verdict_as_current

## AS-134 · What the site publishes keeps uncertainty, is evaluated at a time, and expires
DONE · P0 · user-facing

An external review reproduced six defects: unknown rendered as Keep, expired advice staying current, dropped date corrections and corroborating sources, a builder with no clock, and an unscoped product. The journeys had exercised only the happy path.

- [x] An unresolved evaluation publishes "Not known yet"; a negative claim comes only from a failed requirement, never a missing one.
- [x] Every published answer carries its evaluation time and deadline; past the deadline the page shows "Needs a recheck" and keeps the last answer as history; the client clock can only remove validity.
- [x] An unchanged value with a corrected effective time is appended and counts as a change; the same value from another source is kept as corroboration and triggers no work.
- [x] The site builder refuses to evaluate without an explicit time; a future-effective fact cannot justify a current answer; answers are keyed by product.
- [x] A KEEP states it is provisional; model confidence appears only in the record. Hostile journeys run against an expired clock, an unresolved answer and an unseen product.

Files: backend/airstack/engine.py, backend/tools/build_site_data.py, backend/tools/build_market_data.py, web/src/components/answer/model.js, web/src/components/answer/coverage-map.js
Tests: backend/tests/test_truth.py::test_C03_a_date_only_correction_survives_and_counts_as_a_change, test_X02_an_independent_source_for_the_same_value_is_kept_without_triggering_work; backend/tests/test_data_site.py::test_C01_an_unresolved_evaluation_is_never_published_as_keep, test_C04_a_future_effective_fact_cannot_justify_a_current_answer, test_C02_every_published_answer_carries_its_evaluation_time_and_deadline, test_a_keep_says_it_is_provisional; JOURNEY/test_journeys.py::test_j17_an_expired_answer_is_never_shown_as_current, test_j18_an_unresolved_answer_never_renders_as_keep, test_j19_an_unseen_product_works_through_the_same_path
Journeys: J-17, J-18, J-19

### J-17 · Come back after the recheck date
Who: Someone who bookmarked the page. Test: JOURNEY/test_journeys.py::test_j17_an_expired_answer_is_never_shown_as_current

### J-18 · An answer the evidence can't settle
Who: Anyone. Test: JOURNEY/test_journeys.py::test_j18_an_unresolved_answer_never_renders_as_keep

### J-19 · A product the page has never seen
Who: A reviewer adding data. Test: JOURNEY/test_journeys.py::test_j19_an_unseen_product_works_through_the_same_path

## AS-140 · Every claim can be re-checked against the live page, and the chain of custody is visible
DONE · P0 · user-facing

Belief comes from a visible chain from source page to screen, a later re-check, and admitting what the chain lacks. The re-check needs no model.

- [x] For each page backing an admitted fact, a conditional GET (304 means unchanged), otherwise a fetch and a search for every admitted quote. Outcomes: unchanged, changed with quotes present, changed with quotes missing, fetch failed; a failed fetch is never a pass.
- [x] Each run appends a row per page; stored page text is never replaced; `--check` exits non-zero if a quote went missing.
- [x] The evidence inspector lists, per fact: the page's own words, the source and its class, retrieval time, HTTP status and hash, extraction time, when code found the words, the latest re-check, and other pages stating the same thing.
- [x] Unknown is never independent: only an explicitly listed third-party host counts, and the summary says "none yet" when there is none. A fact never re-checked says so; a fact on one page says "Only this page".
- [x] A quote counts as a user count only if it says users. The chain data loads on demand, is linkable, closes with Escape and returns focus.

Files: backend/tools/reverify_corpus.py, backend/airstack/corpus.py, backend/tools/build_chain_data.py, data/site/chain-data.json, web/src/components/chain.js, web/public/sw.js, tools/deploy.sh
Tests: backend/tests/test_data_market.py::test_a_304_means_unchanged_and_nothing_is_overwritten, test_a_changed_page_that_still_says_it_is_recorded_as_such, test_a_changed_page_that_no_longer_says_it_is_flagged_and_check_mode_fails, test_a_failed_fetch_is_a_failure_never_a_pass, test_an_identical_200_is_unchanged_without_a_304, test_rechecks_are_append_only_history_one_row_per_run, test_a_ratings_count_is_not_accepted_as_a_user_count; backend/tests/test_data_chain.py::test_every_link_of_the_chain_comes_from_stored_records_and_unknown_is_never_independent, test_only_a_listed_third_party_counts_as_independent, test_a_price_never_reaches_the_chain; JOURNEY/test_journeys_products.py::test_j25_the_evidence_chain_shows_every_link_and_admits_what_is_missing
Journeys: J-25

### J-25 · Follow a fact's chain of evidence
Who: A skeptic who wants to know why a number is believable. Test: JOURNEY/test_journeys_products.py::test_j25_the_evidence_chain_shows_every_link_and_admits_what_is_missing

## AS-348 · The evidence chain as a short receipt
IN PROGRESS · P1 · user-facing

Reviewers found the chain long, a vendor's own site classed as "other", and no feed of changes across the corpus.

- [x] A product's own homepage domain is classed as vendor.
- [ ] Each fact's chain folds into a five-step receipt (page, quote, read, re-checked, second record) with details on demand.
- [ ] Captures are immutable by hash; `changes_since` covers the whole corpus, not only the demo.

Files: backend/tools/build_chain_data.py, data/site/chain-data.json
Tests: JOURNEY/test_journeys_products.py::test_j25_the_evidence_chain_shows_every_link_and_admits_what_is_missing

## AS-D01 · Every fact on screen has evidence a stranger can follow, and references are re-checked live
IN PROGRESS · P0 · user-facing

Nothing shown should be wrong, and anyone can check it. A link that no longer resolves or no longer says what is claimed is a wrong fact.

- [x] Every real evidence row has a source URL, the exact phrase it rests on, and a source link on the page.
- [x] A checker re-fetches every source row and confirms the phrase is on the page; Google's iOS help page and the edition table are checked by phrase so a moved feature fails.
- [ ] Claims have more than one independent source where one exists (today most rows have one primary source).

Files: data/site/site-data.js, web/src/components/profile.js, web/src/components/chain.js, web/public/llms.txt, backend/tools/verify_references.py
Tests: backend/tests/test_references.py::test_every_real_evidence_row_declares_a_url_and_the_phrase_it_rests_on, test_every_reference_resolves_and_contains_its_phrase_live, test_phrase_matching_ignores_markup_case_whitespace_and_curly_quotes
Journeys: J-06

### J-06 · Open the sources
Who: A skeptical judge. Test: JOURNEY/test_journeys_products.py::test_j06_sources_are_dated_linked_and_fingerprinted

## AS-D03 · Examples are labelled quietly, and no claim about a real product is invented
DONE · P0 · user-facing

Example inputs are fine; a faked result is never fine. Hand-written sample evidence about real products was removed rather than patched.

- [x] One provenance line covers the whole site; no badges and no words such as "sample" or "LIVE"; the footer says "Built with Muse Spark" only when the database holds real model calls.
- [x] Only the recorded example ships; each of its evidence rows comes from the database and is sourced. Hand-written sample files live in `archive/` and are never deployed.

Files: data/site/site-data.js, web/index.html, web/src/components/hero.js
Tests: backend/tests/test_references.py::test_every_real_evidence_row_declares_a_url_and_the_phrase_it_rests_on; JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action; backend/tests/test_site.py::test_card_faces_hold_plain_english_only
Journeys: J-01

### J-01 · Open the page
Who: Anyone with the link. Test: JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action
