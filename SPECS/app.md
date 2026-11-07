# The app

What a person sees and does on airstack.bot: the landing, the answer, search, the market views, and the polish that makes them feel finished.

## AS-100 · The landing states the value and opens onto the market
DONE · P0 · user-facing

A visitor has five seconds: this is a software-market intelligence product, not a renewal utility or a blog, then the market itself on the first screen with no full-screen gate.

- [x] A compact "Software market intelligence" scope label, "See the software market move.", the supporting line "Track your stack, compare every category, and catch the changes that matter—each claim linked to its source.", the search box as the one way in, a "Compare tools side by side" link, and one proof line (the number of researched products counted from the data, "every fact quoted from its own page", provenance and as-of date). The first screen has no tiles, category dropdown or taxonomy button; what it dropped is still reached from Markets, from `/t/` and `/c/` and from the type crumb on a product card.
- [x] The document title and share titles use the broader promise, never position AirStack as primarily a renewal tool, and make no paid-service promise.
- [x] One provenance line covers the whole site (example plans, sources, the replay date, the model run date). No dollar figures, no "seat", "sample" or "LIVE", nothing under 12 px, five type sizes in all.
- [x] Apps are ordered by data, not hand-picked; the recorded example is labelled as an example.
- [x] Title, description, canonical URL, Open Graph tags and an inline favicon identify airstack.bot when shared.

Files: web/index.html, web/src/components/hero.js, web/src/components/browse.js, web/src/components/search/index.js, web/src/styles/landing.css, tools/assemble.sh
Tests: JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action; JOURNEY/test_journeys_quality.py::test_j08_phone_width_stacks_tables_and_keeps_tap_targets
Journeys: J-01

## AS-101 · As it happened: the recorded change, step by step
DONE · P0 · user-facing

The product's value is continuously monitored advice, so the page shows the stored lifecycle, including the step where a recheck is due and no current recommendation is shown.

- [x] Four selectable steps come from stored verdict events: Before, Google ships, Re-checked, Scheduled check.
- [x] At "Google ships" both answers are struck through and read "Needs a second look"; the caption links the vendor's post with its date and time. A withheld re-judge also shows as "Needs a second look".
- [x] It replays once, labelled as a replay, and stops on the latest step. With reduced motion nothing plays and every step is selectable. The only motion is the strike when a source change makes a recheck due.

Files: web/src/components/replay.js, backend/tools/build_site_data.py
Tests: JOURNEY/test_journeys.py::test_j03_as_it_happened_old_advice_never_looks_current, test_j03b_the_replay_steps_through_recorded_events_once, test_j02b_reduced_motion_shows_every_step_without_animation
Journeys: J-02b, J-03

### J-02b · Reduced motion
Who: Someone who has reduced motion turned on. Test: JOURNEY/test_journeys.py::test_j02b_reduced_motion_shows_every_step_without_animation

### J-03 · Inspect the change, step by step
Who: A skeptical judge. Test: JOURNEY/test_journeys.py::test_j03_as_it_happened_old_advice_never_looks_current

## AS-102 · Check yours: the answer depends on what you already have
DONE · P0 · user-facing

The same change matters differently to two people because what they own differs. Defaults must be honest: a phone model picked for the user would be an invented fact about them.

- [x] A business plan that includes the notes gives Retire only when the rest of what you use the tool for is covered; until then the answer is "Notes covered" (headline "You may be able to stop paying for X") and asks what else you use it for, in the answer itself, from that app's own profile. "Nothing else" gives Retire scoped to what you said; a need your platform lacks gives Keep; an unverified one gives "Not known yet".
- [x] Business Standard on Android reads Retire; Business Starter on Android reads Keep with the reason; each answer names what would change it and lists every requirement as covered, not covered or unknown.
- [x] Where you meet defaults to Online; a device is asked for only for in-person Google notes and none is preselected. The "Your setup" line says "Assuming" until you change something; it is one line (plan, meeting, device, needs) and Change shows the chips (keyboard operable, the address carries them either way). Choosing another tool resets the scenario.
- [x] The market matrix and the answer card use the same word and the same device text; no matrix cell issues an unconditional Retire.

Files: web/src/components/answer/model.js, web/src/components/answer/answer.js, backend/tools/build_site_data.py, web/src/components/answer/needs.js, backend/tools/build_market_data.py, web/src/components/market-table.js
Tests: JOURNEY/test_journeys.py::test_j02_check_yours_answers_every_plan_without_a_request, test_j21_same_app_and_plan_different_needs_different_answers, test_j20_task_a_zoom_user_gets_a_sourced_answer_in_four_interactions; JOURNEY/test_journeys_quality.py::test_j30_in_page_links_never_undo_a_choice; JOURNEY/test_journeys_market.py::test_j15_the_market_every_cell_is_sourced_or_says_not_observed; backend/tests/test_truth.py::test_the_pages_demo_data_agrees_with_the_engine
Journeys: J-02, J-15, J-20, J-21

### J-02 · Check yours
Who: Someone paying for Fireflies. Test: JOURNEY/test_journeys.py::test_j02_check_yours_answers_every_plan_without_a_request

### J-21 · Same app, same plan, different needs
Who: Two people paying for the same note-taker on the same plan. Test: JOURNEY/test_journeys.py::test_j21_same_app_and_plan_different_needs_different_answers

## AS-103 · The record: sources, history and execution, one view at a time
DONE · P0 · user-facing

Reviewers score evidence and model use; they should reach any of it in one action, as tables.

- [x] Three keyboard-operable tabs (Sources, History, Execution) switch content.
- [x] Sources lists every fact with its source, published date, checked date and a SHA-256 fingerprint the browser recomputes and matches; replaced facts are struck.
- [x] History lists every revision with its date, whether that clock is replayed or real, the answer and why.

Files: web/src/components/record.js
Tests: JOURNEY/test_journeys_products.py::test_j06_sources_are_dated_linked_and_fingerprinted, test_j07_history_and_execution_show_the_real_work
Journeys: J-06

## AS-104 · Find any tool instantly: nothing is preselected, and every input answers within a frame or two
DONE · P0 · user-facing

Someone who pays for any tool in any category must find it at once. A slow control reads as a broken one.

- [x] `/` focuses one search box over every tracked tool, ranking by name prefix, word prefix, substring, then category; arrow keys, Enter and Escape work; the box states how many tools it searches, computed from the data.
- [x] Before a tool is chosen there is no answer on screen: the box, the categories, and a ranked list of what moved most this week with bars on one shared scale. Choosing a tool puts `#app=<id>` in the address.
- [x] A tool with a replacement model opens its questions; every other tool opens its own page with signals linked to sources, its place among peers, its own-page quotes and a plain note that replacement advice for that category is not built yet.
- [x] No screen shows "[object", "undefined", "NaN" or "null". If market data cannot load the page says so, and once visited the shell and data work offline.
- [x] Each interaction (keystroke, tool, category, plan, platform, sort) costs under 50 ms of main-thread time at 4x CPU slowdown; showing all rows paints the first at once; answers are lookups, so choosing any scenario makes no request.
- [x] Suggestions shown right after the box loses focus stay open.

Files: web/src/components/search/index.js, web/src/components/avatar.js, web/src/components/browse.js, backend/tools/build_site_data.py, web/src/components/app.js
Tests: JOURNEY/test_journeys_products.py::test_j04_search_finds_any_tracked_tool_by_name_or_category_and_opens_it, test_j29_the_search_box_counts_the_tools_it_searches, test_j26_no_tracked_tool_is_a_dead_end; JOURNEY/test_journeys_quality.py::test_j31_when_the_market_data_cannot_load_the_page_says_so, test_j28_no_screen_ever_shows_a_stringified_object_or_undefined, test_j08_phone_width_stacks_tables_and_keeps_tap_targets, test_j27_every_input_responds_within_a_frame_or_two, test_j38_suggestions_typed_right_after_a_blur_are_not_closed_by_its_late_timer; JOURNEY/test_journeys_market.py::test_j14_movers_show_real_signals_each_linked_to_its_source; JOURNEY/test_journeys.py::test_j02_check_yours_answers_every_plan_without_a_request
Journeys: J-04, J-26, J-27

### J-04 · Search any tracked tool
Who: Someone who knows what they pay for, in any category. Test: JOURNEY/test_journeys_products.py::test_j04_search_finds_any_tracked_tool_by_name_or_category_and_opens_it

### J-26 · No tracked tool is a dead end
Who: Someone who pays for a tool in any of the twelve categories. Test: JOURNEY/test_journeys_products.py::test_j26_no_tracked_tool_is_a_dead_end

### J-27 · Every input is instant
Who: Anyone with a slow phone. Test: JOURNEY/test_journeys_quality.py::test_j27_every_input_responds_within_a_frame_or_two

## AS-105 · A tool we do not track says so
DONE · P0 · user-facing

Visitors must not be able to trigger paid work, and a miss must never show another tool's answer.

- [x] An untracked name reads "We don't track “…” yet"; nothing is researched on the spot and no other tool's answer stays on screen.
- [x] "Save on this device" stores it in this browser and confirms so; it never claims a request was sent.

Files: web/src/components/cards/tool.js, web/src/components/search/index.js
Tests: JOURNEY/test_journeys.py::test_j05_an_untracked_tool_is_saved_on_this_device_only
Journeys: J-05

### J-05 · A tool we do not track
Who: Someone whose tool is not in the universe. Test: JOURNEY/test_journeys.py::test_j05_an_untracked_tool_is_saved_on_this_device_only

## AS-106 · The receipt: every model claim counts stored calls
DONE · P1 · user-facing

"Powered by a model" is branding; a receipt with real calls, tokens and time is evidence.

- [x] The judged example reads "Judged by muse-spark-1.3 · confidence · calls · tokens · seconds · date"; the re-checked one says "Re-checked by"; every other plan and device reads "Rules only · no model call".
- [x] Execution lists every stored call and the judge's own words verbatim with the facts it cited.

Files: web/src/components/answer/model.js
Tests: JOURNEY/test_journeys.py::test_j02_check_yours_answers_every_plan_without_a_request; JOURNEY/test_journeys_products.py::test_j07_history_and_execution_show_the_real_work
Journeys: J-02, J-07

### J-07 · History and execution
Who: A judge checking the model's work. Test: JOURNEY/test_journeys_products.py::test_j07_history_and_execution_show_the_real_work

## AS-066 · The page speaks four verdict words, shows no spend figure, and prints only sourced prices
DONE · P0 · user-facing

Verdicts are BUILD, BUY, KEEP or RETIRE, and prices go stale fast and invite argument.

- [x] A scan of the page, data, specs, journeys and API output finds no forbidden synonym, no dollar amount except a sourced list price, and no credit or spend figure.
- [x] The MCP block shows the real `assess` request and the matching reviewed answer from the generated record; no button or public endpoint can execute work.
- [x] In-person notes ask "Which device do you record on?"; the "In their words" row is hidden when there is no quote.

Files: web/index.html, web/src/components/prices.js, data/site/site-data.js, web/src/components/answer/model.js, web/src/components/record.js, backend/tools/build_site_data.py
Tests: backend/tests/test_truth.py::test_no_dollar_figure_anywhere_except_the_credit_readout, test_the_word_kill_never_appears_in_the_ui_the_specs_or_the_outputs, test_golden_demo_every_screen_state; JOURNEY/test_journeys_quality.py::test_j34_nothing_on_screen_shows_a_spend_figure_a_stale_api_name_or_a_wrong_noun; JOURNEY/test_journeys.py::test_j46_the_example_request_and_recorded_answer_use_the_same_words; backend/tests/test_live_site.py::test_the_mcp_example_shown_on_the_page_is_local_and_matches_the_recorded_answer
Journeys: J-01, J-29

### J-29 · The record is clean
Who: Anyone reading the page, or an agent copying its example. Test: JOURNEY/test_journeys_quality.py::test_j34_nothing_on_screen_shows_a_spend_figure_a_stale_api_name_or_a_wrong_noun

## AS-112 · Works on a phone and from the keyboard
DONE · P0 · user-facing

- [x] At 390 px nothing scrolls sideways, tables stack into labelled rows, and every chip, step, tab and button is at least 44 px tall.
- [x] The momentum tape stops for focus or hover and each link keeps at least a 24 px target inside its 32 px rail.
- [x] `/` focuses search, Escape closes its list, arrow keys move plans, devices, steps and tabs.
- [x] At 720 px and below a Movers row is two lines and tapping it reveals the rest; in Check yours a sticky strip shows the verdict word and one line and updates on every chip.

Files: web/src/styles/index.css, web/src/components/chips.js, web/src/components/movers.js
Tests: JOURNEY/test_journeys_quality.py::test_j08_phone_width_stacks_tables_and_keeps_tap_targets, test_j09_keyboard, test_j37_on_a_phone_the_verdict_changes_in_view_and_movers_rows_are_compact
Journeys: J-08, J-09, J-31

### J-08 · On a phone
Who: Someone on a 390px phone. Test: JOURNEY/test_journeys_quality.py::test_j08_phone_width_stacks_tables_and_keeps_tap_targets

### J-09 · From the keyboard
Who: A keyboard user. Test: JOURNEY/test_journeys_quality.py::test_j09_keyboard

### J-31 · On a phone
Who: Someone with a 375 px screen. Test: JOURNEY/test_journeys_quality.py::test_j37_on_a_phone_the_verdict_changes_in_view_and_movers_rows_are_compact

## AS-120 · Release quality contract
DONE · P0 · user-facing

Performance, accessibility, document quality and interaction speed are release contracts.

- [x] A real-Chrome gate measures FCP, LCP, cumulative layout shift and long-task blocking against explicit budgets; interaction journeys separately measure p95 latency at 4× CPU slowdown.
- [x] The same gate inspects Chrome's accessibility tree for named controls and required landmarks, then checks headings, metadata, canonical URL, structured data and minimum text size. Phone, keyboard, reduced-motion and offline journeys cover behavior.

Files: web/index.html, web/src/styles/index.css, web/src/main.js, web/public/fonts/Inter-latin.woff2, tools/assemble.sh, JOURNEY/test_journeys_quality.py
Tests: JOURNEY/test_journeys_quality.py::test_j12_release_quality_contract, test_j27_every_input_responds_within_a_frame_or_two, test_j08_phone_width_stacks_tables_and_keeps_tap_targets, test_j09_keyboard
Journeys: J-12

### J-12 · Browser quality contract
Who: anyone using the site. Test: JOURNEY/test_journeys_quality.py::test_j12_release_quality_contract

## AS-121 · Installable and works offline
DONE · P1 · user-facing

- [x] A web manifest with 192, 512 and maskable icons makes it installable; the service worker is network-first, so online it always fetches fresh and offline it serves the last copy.
- [x] Only an allowlist of public static files is cached, and only successful responses; everything else passes through.

Files: web/public/sw.js, web/public/manifest.webmanifest, web/public/icons/icon-192.png, web/public/icons/icon-512.png, web/public/icons/icon-maskable-512.png, web/public/icons/apple-touch-icon.png
Tests: JOURNEY/test_journeys_quality.py::test_j11_works_offline_after_the_first_visit; backend/tests/test_site.py::test_crawl_and_install_files_exist_and_point_at_airstack_bot, test_the_service_worker_caches_only_an_allowlist
Journeys: J-11

### J-11 · Offline
Who: Someone on a train. Test: JOURNEY/test_journeys_quality.py::test_j11_works_offline_after_the_first_visit

## AS-131 · The page is a snapshot of the database, in plain words, answered by the same rules
DONE · P0 · user-facing

An earlier page rendered hand-written data that disagreed with the database. Now it can only show what the database holds.

- [x] `backend/tools/build_site_data.py` writes `site-data.js` from the database and `deploy.sh` copies it; every call id on screen resolves to a stored call; times come from the database's clocks, never the visitor's.
- [x] Every plan and device is answered at build time by the engine's own `evaluate()`; for the two recorded examples it asserts the precomputed answer equals the stored verdict. Flipping a chip sends no request.
- [x] Every sentence on an answer, step or source row is human text; a test fails if any contains a dotted key, a hash, a call id, a token count, or the words seat, verdict or lapsed.

Files: backend/tools/build_site_data.py, data/site/site-data.js, tools/deploy.sh, web/src/lib/data.js, tools/assemble.sh, web/src/components/answer/answer.js, web/src/components/record.js, web/src/components/answer/model.js
Tests: backend/tests/test_truth.py::test_the_pages_demo_data_agrees_with_the_engine; backend/tests/test_site.py::test_deploy_ships_every_local_file_the_page_loads, test_card_faces_hold_plain_english_only; JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action, test_j02_check_yours_answers_every_plan_without_a_request; JOURNEY/test_journeys_products.py::test_j06_sources_are_dated_linked_and_fingerprinted, test_j07_history_and_execution_show_the_real_work
Journeys: J-01, J-02, J-07

## AS-239 · Each page shows what belongs to it
DONE · P0 · user-facing

The worked example must not leak onto other tools' pages.

- [x] A tool's page shows that tool: the meeting-notes market, the replayed example and its record appear only on the landing and on meeting-notes tools. The example is titled as one.
- [x] The first row under a tool's name names only coverage that exists (current market signals and/or own-page facts with the quote count). Unavailable capabilities do not occupy promotional badges; meaningful evidence gaps stay inside the relevant analysis and can still be inspected.

Files: web/src/components/cards/tool.js
Tests: JOURNEY/test_journeys_products.py::test_j41_a_tools_page_shows_that_tool_and_the_worked_example_stays_with_meeting_notes, test_j36_a_tool_without_a_replacement_check_states_its_coverage_first; JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action
Journeys: J-30, J-33

### J-33 · A tool's page is about that tool
Who: Anyone opening a tool that is not a meeting-notes app. Test: JOURNEY/test_journeys_products.py::test_j41_a_tools_page_shows_that_tool_and_the_worked_example_stays_with_meeting_notes

## AS-242 · An answer copies as a brief with its plan, sources and dates
DONE · P1 · user-facing

A buyer takes the answer to a note, ticket or renewal thread, and it has to travel with what it rests on.

- [x] "Copy with sources" writes plain text from the same answer object the card shows: tool, plan, answer and reason, what would change it, when it was evaluated and until when it is current, each source with link and checked date, and a link back. It adds the MCP request only when the endpoint takes exactly that scenario.
- [x] It says "Copied" only when the clipboard write worked.

Files: web/src/components/answer/answer.js, web/src/components/record.js
Tests: JOURNEY/test_journeys.py::test_j43_the_answer_copies_as_a_brief_with_its_plan_its_sources_and_its_dates
Journeys: J-35

### J-35 · Take the answer with me
Who: A buyer who has to justify the decision to someone else. Test: JOURNEY/test_journeys.py::test_j43_the_answer_copies_as_a_brief_with_its_plan_its_sources_and_its_dates

## AS-253 · The answer is a coverage map
DONE · P1 · user-facing

A verdict word in a box is a label, not an explanation.

- [x] Three columns: the tool you pay for, your needs, what you already have. A covered need draws a solid line to your plan, a need only the tool covers draws one back to the tool, an unverified need is a dashed stub.
- [x] The decision comes first, in plain words, as the headline ("You can stop paying for X.", "Keep paying for X.", "You may be able to stop paying for X.", "We can’t say yet.", "Monitoring recheck due."); the official word (Retire, Keep, Notes covered, Not known yet) is the small label above it; no count of lines. The coverage map and its line-by-line quotes sit in a closed "How we decided" disclosure.
- [x] The dates read as a sentence, never a countdown: "Verified 4 Nov 2026. Monitoring active; next recheck by 18 Nov 2026."; after that date the headline says "Monitoring recheck due" and the previous answer is clearly labelled as history with its last verification date. On a phone the map is a list; reduced motion shows the final state.

Files: web/src/components/answer/coverage-map.js, web/src/styles/index.css
Tests: JOURNEY/test_journeys.py::test_j02_check_yours_answers_every_plan_without_a_request
Journeys: J-02

## AS-256 · The page is plain ES-module components, assembled once
DONE · P1

One 120 KB file of inline script and style was hard to review. Components with explicit imports say what depends on what, and nothing needs a build tool.

- [x] `web/index.html` is the shell and `web/src/main.js` starts each component; each module imports what it uses. No package manifest or lockfile.
- [x] `tools/assemble.sh` inlines the stylesheets, copies the modules with preload links and writes the first screen's text from the data. `deploy.sh` ships what it builds, the journeys serve it, and `verify_deploy.py` compares production with it byte for byte.
- [x] Styles are plain CSS with the design tokens in `theme.css`.

Files: web/index.html, tools/assemble.sh, tools/deploy.sh, tools/verify_deploy.py, web/public/sw.js, web/src/**/*.js, web/src/**/*.css
Tests: backend/tests/test_site.py::test_deploy_ships_every_local_file_the_page_loads; JOURNEY/test_journeys.py::test_j01_first_look_is_the_claim_and_one_action

## AS-257 · The market map
DONE · P1 · user-facing

A table of 130 rows hides the shape of the market. A map shows where adoption is moving, provided every tile's number was measured.

- [x] One panel per lane with a squarified treemap, one tile per tool that has registry downloads, area by last week's downloads; areas compare within a lane only, and the page says so.
- [x] Colour is the change against the tool's own 4-week level in four steps each way, grey within 2%, clamped at 50% with a key; a tool with no usable earlier weeks is hatched, never coloured.
- [x] Every tile is a button whose label carries its numbers; opening it opens the tool.
- [x] Markets also covers every kind of software: a picker over the taxonomy draws a category's products sized by how widely each is documented, in a neutral tone, says it is not market share, and states how many listed products carry no category yet.

Files: backend/tools/build_pages.py, backend/tools/pages/*.py, web/index.html, web/src/components/market-map.js, web/src/components/type-map.js, web/src/lib/treemap.js, web/src/styles/market-map.css
Tests: JOURNEY/test_journeys_market.py::test_j53_the_market_map_draws_only_measured_tools_and_says_what_its_areas_and_colours_mean, test_j69_markets_covers_every_kind_of_software_sized_by_documentation_and_says_what_it_is_not; backend/tests/test_pages.py::test_the_type_map_data_agrees_with_the_taxonomy_pages
Journeys: J-45, J-57

### J-45 · The market at a glance
Who: Anyone wondering what is moving. Test: JOURNEY/test_journeys_market.py::test_j53_the_market_map_draws_only_measured_tools_and_says_what_its_areas_and_colours_mean

## AS-260 · Eight views with tabs and routes
DONE · P0 · user-facing

- [x] Overview, Compare, Markets, Insights, Calendar, Makers, Agents and How it works are routes (`#/markets`); one is shown at a time with its tab marked current and the page title naming it; back and forward move between views.
- [x] On a narrow screen the horizontal tab strip brings the current route into view, including a direct link to a later tab.
- [x] `#app=<id>` opens a product in Overview from any view; old section anchors land on the view that holds them; closing a profile or the chain returns to the view's own address.

Files: web/src/lib/router.js, web/index.html, web/src/main.js, web/src/styles/landing.css, web/src/styles/base.css
Tests: JOURNEY/test_journeys_quality.py::test_j54_the_app_views_each_have_a_tab_route_and_working_back_and_forward
Journeys: J-46

### J-46 · An app, not one long page
Who: Everyone. Test: JOURNEY/test_journeys_quality.py::test_j54_the_app_views_each_have_a_tab_route_and_working_back_and_forward

## AS-268 · How it works is a methodology page
DONE · P1 · user-facing

- [x] A hero line, then a four-step pipeline (read the vendor's page, code finds the quote, the model judges against the plan, continuous monitoring schedules the next recheck) with real evidence from the worked record.
- [x] Then the replay, the record, and a muted fine-print block of clocks and caveats. No spend figure.

Files: web/src/components/method.js, web/src/styles/method.css, web/index.html
Tests: JOURNEY/test_journeys_pages.py::test_j59_how_it_works_is_a_methodology_page_built_from_the_examples_own_records
Journeys: J-50

### J-50 · How it works, as a methodology
Who: A judge or a buyer deciding whether to trust an answer. Test: JOURNEY/test_journeys_pages.py::test_j59_how_it_works_is_a_methodology_page_built_from_the_examples_own_records

## AS-283 · Your stack, local-first
IN PROGRESS · P1 · user-facing

Tracking a stack is the reason to come back, and the list of what a company pays for is the most sensitive thing it has, so it stays with its owner.

- [x] Overview makes Your software stack a primary workflow with an honest empty state and add action. Add a tool from its open record; the device-local workspace shows renewal-answer availability, own-page research, quoted prices and public momentum, and unlocks My stack filters for vendor updates and the calendar. It does not call same-category alternatives recommendations without requirements-fit evidence.
- [x] A compact intelligence panel counts only the tracked tools with loaded own-page research and renewal answers, shows a public-registry trend only when the generated market data has a comparison against that tool's own four-week level, and prioritizes the next review by an evidence gap. It labels that priority as evidence coverage, not product fit, and makes no request.
- [ ] A `#stack=` link carries tools and plans so a colleague sees the same review; no server sees it.
- [ ] Save to a code: the stack is encrypted in the browser with a passphrase-derived key and only the opaque blob is stored.
- [ ] An `.ics` export of renewal dates you enter and scheduled recheck dates for answers about your tools.
- [x] `review_stack` over MCP takes up to 25 names, ids or domains and returns, per tool, the match, category, whether researched, facts total (null when none, never 0), list prices present and up to three same-category alternatives; no model call, never a verdict, the list never logged.

Files: web/index.html, web/src/components/stack.js, web/src/lib/stack.js, web/src/styles/stack.css, docs/MCP.md
Tests: JOURNEY/test_journeys.py::test_j60_a_stack_is_kept_on_this_device_carried_in_a_link_and_filters_what_changed; backend/tests/test_money.py::test_oversized_stack_review_is_rejected, test_every_mcp_tool_makes_zero_spark_calls
Journeys: J-51

### J-51 · My stack, kept on my device
Who: Someone who pays for a handful of tools. Test: JOURNEY/test_journeys.py::test_j60_a_stack_is_kept_on_this_device_carried_in_a_link_and_filters_what_changed

## AS-316 · Terms and privacy on one short page
DONE · P1 · user-facing

The legal page should be brief, readable and accurate to the product.

- [x] Under 90 words: provided as is, not advice, may be wrong or out of date, marks and data belong to their owners, no account needed, standard host logs, the stack stays in the browser. One link for sources and licences and a removal route; linked from every view's footer and every product page.

Files: web/public/legal/index.html, web/public/legal/notices.txt, web/index.html, tools/assemble.sh, backend/tools/build_pages.py, backend/tools/pages/*.py
Tests: JOURNEY/test_journeys_pages.py::test_j61_terms_and_privacy_are_one_short_page_linked_from_every_view
Journeys: J-52

### J-52 · Terms and privacy, short
Who: Anyone. Test: JOURNEY/test_journeys_pages.py::test_j61_terms_and_privacy_are_one_short_page_linked_from_every_view

## AS-326 · Moving this week: registry and attention signals, honestly read
DONE · P1 · user-facing

What is moving, from keyless public sources, so the page opens on a market rather than one app.

- [x] Tools in five lanes, each registry id verified to exist; 7-day downloads against the week before from npm and PyPI, Hacker News stories (attention, not users), GitHub stars and last release.
- [x] Every number keeps its API URL and fetch time; every raw response is saved and an offline rebuild is byte-identical. A missing signal is null with its reason, never zero.
- [x] Trending means above the tool's own 4-week level (median of up to four earlier full weeks), with at least 5,000 downloads a week; rows up on the week but below their own level say so and rank below solid movers.
- [x] The table filters by lane, sorts by change, stories or stars, and links every number to its source.
- [x] A measured zero remains `0`; an unavailable source, a missing prior week, an insufficient four-week baseline and a catalog-only product each have distinct plain-language labels. No dash stands in for missing data. The scope and fetch line is body-readable, and the map draws an unavailable baseline with an intentional pattern and label so it cannot look like a broken tile.

Files: backend/airstack/connectors/registries.py, backend/tools/build_movers.py, config/universe.json, data/movers.json, backend/tools/build_market_data.py, web/src/components/movers.js, web/src/components/browse.js
Tests: backend/tests/test_data_chain.py::test_week_delta_prior_zero_gives_null_delta_not_infinity, test_zero_days_count_as_a_reporting_gap_when_the_source_writes_0_for_missing, test_a_tool_without_a_registry_gets_null_and_a_reason_never_zero, test_every_number_in_a_built_movers_json_has_a_url_and_fetched_at, test_offline_rebuild_from_committed_raw_reproduces_movers_json_exactly, test_a_rebound_from_a_trough_week_is_flagged_by_the_tools_own_recent_level; JOURNEY/test_journeys_market.py::test_j14_movers_show_real_signals_each_linked_to_its_source, test_j39_trending_lists_only_tools_above_their_own_recent_level_and_above_the_volume_floor, test_j40_the_first_screen_never_shows_a_rebound_as_the_top_mover_even_before_the_full_data_loads, test_j82_missing_market_signals_are_named_not_drawn_as_holes
Journeys: J-14, J-32

### J-14 · What's moving this week
Who: Anyone deciding what to look at. Test: JOURNEY/test_journeys_market.py::test_j14_movers_show_real_signals_each_linked_to_its_source

### J-32 · What is actually moving?
Who: Someone scanning the opening list for what is gaining. Test: JOURNEY/test_journeys_market.py::test_j39_trending_lists_only_tools_above_their_own_recent_level_and_above_the_volume_floor

## AS-306 · A live comparison with and without the MCP tool
DONE · P1 · user-facing

The on-camera comparison must be real, not scripted.

- [x] The same model and question, three runs without tools and three with `get_verdict`, every answer shown verbatim and recorded with response ids, tokens and time in `data/ab-runs.json`. Resumable and append-only; every call goes through the account ledger first.
- [x] A second, neutral set (the question never names the feature) is kept and shown, newest first, with what its question did and did not say.
- [x] Execution shows the literal request and the answer any agent gets, with a raw-JSON toggle; no Orbit section ships because no real Orbit data exists.

Files: backend/tools/run_ab.py, backend/airstack/spark.py, backend/tools/build_site_data.py, web/src/components/record.js, data/ab-runs.json, data/ab-runs-2.json
Tests: backend/tests/test_money.py::test_three_runs_each_side_saved_verbatim_and_the_with_side_really_reads_airstack, test_a_second_run_is_free_and_only_missing_runs_are_made; JOURNEY/test_journeys_products.py::test_j07_history_and_execution_show_the_real_work
Journeys: J-07

## AS-270 · Marks: monograms now, licensed logos later
IN PROGRESS · P2 · user-facing

Rows of identical grey read as a database; marks make a market legible, but fetching logos at scale means hotlinking or redistributing trademarks.

- [x] Initials on a tint from a hash of the product's website, drawn by CSS and decorative, in search, lists, the alternatives table and the product header; the search monogram carries a status badge (renewal verdict, researched, organization).
- [ ] A directory product's card shows list prices whenever `pricing.json` has its id; `pricing.json` carries prices for directory products so the journey runs rather than skips.
- [ ] A build step resolves Wikidata's logo to its Commons file, records licence, source and date, and self-hosts it (no hotlinking); marks appear unaltered on product pages only; NOTICE.md gives the takedown path.

Files: web/src/components/avatar.js, web/src/styles/workspace.css, web/src/components/cards/directory.js, backend/tools/build_marks.py, data/site/marks.json
Tests: JOURNEY/test_journeys_products.py::test_j62_every_product_and_organization_carries_a_monogram_drawn_from_its_initials, test_j58_a_directory_product_shows_its_list_prices_when_its_pricing_page_was_read; backend/tests/test_data_graph.py::

## AS-346 · Compare and share
DONE · P1 · user-facing

A decision has to travel to a colleague exactly as it was made.

- [x] Compare 2 to 5 products (see AS-366); a saved comparison shows its active monitoring window and next recheck, counted from the oldest fact shown.
- [x] The address carries the whole assessment (app, plan, device, needs) and back and forward restore it.
- [x] Inside "How we decided" (closed by default), hovering a coverage line shows its quote and source; opening a hollow need lists what would close it; a Current / Proposed switch shows coverage before and after a change.

Files: web/src/components/answer/answer.js, web/src/components/answer/coverage-map.js, web/src/components/answer/needs.js, web/src/components/answer/model.js, web/src/components/app.js, web/src/components/chain.js, web/src/components/search/index.js, web/index.html, web/src/styles/coverage-map.css, web/src/styles/workspace.css
Tests: JOURNEY/test_journeys.py::test_j63_a_shared_answer_reopens_the_same_scenario_and_the_page_has_a_skip_link; JOURNEY/test_journeys.py::test_j76_an_answer_shows_each_lines_quote_lists_what_would_close_it_and_shows_coverage_before_and_after_a_change; JOURNEY/test_journeys.py::test_j77_back_and_forward_restore_each_step_of_an_assessment; JOURNEY/test_journeys.py::test_j78_compare_puts_two_to_five_products_side_by_side_each_cell_in_the_pages_words
Journeys: J-64, J-65, J-66

### J-64 · Coverage, line by line, before and after
Who: Someone deciding whether to cancel, who wants to see the words behind each line and what a change of plan would do. Test: JOURNEY/test_journeys.py::test_j76_an_answer_shows_each_lines_quote_lists_what_would_close_it_and_shows_coverage_before_and_after_a_change

### J-65 · Back and forward
Who: Someone who changed plan and needs and wants to step back through it. Test: JOURNEY/test_journeys.py::test_j77_back_and_forward_restore_each_step_of_an_assessment

### J-66 · Compare products
Who: Someone choosing between 2 to 5 products who needs a colleague to see the same table. Test: JOURNEY/test_journeys.py::test_j78_compare_puts_two_to_five_products_side_by_side_each_cell_in_the_pages_words

## AS-366 · Compare: what each product's own pages say, side by side
IN PROGRESS · P0 · user-facing

Someone comparing software sees every claim quoted from the vendor's own page, dated and sourced, for any two to five of the researched products.

- [x] "Compare tools side by side" under the first screen's search opens the Compare view (`#compare=`); a product's card and an answer start one with that product; the command palette lists it. Products are added with a search that uses the same index and ranking as the first screen's, by keyboard alone.
- [x] A table with one column per product and a row for each field any of them states (what it does, plans, free plan, integrations, compliance, platforms, open source, and the rest of the profile fields) plus a list price. Every cell shows the value, the page it is on (host, linked) and the day the quote was found there; the verbatim quote opens under "Quote" (tap, click or keyboard). A field a product's pages do not state shows "Not observed", never blank or guessed.
- [x] A list price appears only where it was read from a pricing page, with that page, its date and its quote. Rows where two or more products state different values are marked "differs" (Not observed against a value is not a difference); "Only what differs" hides the rest.
- [x] The address carries the selection (`#compare=a,b,c`), back and forward restore it, and a pasted link opens it. Five is the most. On a 390 px phone the page does not scroll sideways: the table scrolls in its box with the field names pinned.
- [x] Compare is a primary tab in the top navigation; on a narrow screen the current tab is scrolled into view. Copy link reports success or failure. The local MCP `compare` tool returns the same cells but is not driven from this view.

Files: web/src/components/compare.js, web/src/components/chain.js, web/src/components/prices.js, web/src/components/app.js, web/src/lib/profiles.js, web/src/lib/router.js, web/index.html, web/src/styles/workspace.css
Tests: JOURNEY/test_journeys.py::test_j78_compare_puts_two_to_five_products_side_by_side_each_cell_in_the_pages_words; JOURNEY/test_journeys.py::test_j79_compare_is_one_click_from_the_first_screen_works_by_keyboard_and_on_a_phone
Journeys: J-67

### J-67 · Compare from the first screen
Who: Someone who landed on the site and wants two or three products side by side with the vendors' own words. Test: JOURNEY/test_journeys.py::test_j79_compare_is_one_click_from_the_first_screen_works_by_keyboard_and_on_a_phone

## AS-298 · The Calendar: recorded activity and published dates
IN PROGRESS · P1 · user-facing

A calendar is the one chart where the future is a first-class place, which makes continuous monitoring and scheduled rechecks tangible.

- [x] `build_events.py` writes `events.json`: observed vendor announcements and releases, scheduled end-of-life/support dates published by endoflife.date (MIT), and AirStack's own evidence-review dates. Every event is a day with a source URL; the UI distinguishes the publisher's record from an AirStack review date. No model call.
- [x] The factual calendar contains no release prediction, inferred cadence window, invented deadline or source-less event. Forecasts, if later added, live in a separately labelled forecast product and never share this calendar's marks, counts or agenda.
- [x] Hacker News and general blog posts remain optional context and are off by default. The default view answers what shipped, what changed, what support date was published and what AirStack will review.
- [x] Activity shades a year of days by deduplicated material events, and a day not observed looks different from a quiet one. Horizon shows the next 90 days by lane, each event drawn by what is known.
- [x] The agenda lists each product once: its next dated item leads and later dates fold under it.
- [ ] A time cursor in the address is shared with the market map; My Stack dims everything else and lists only events that affect your tools by rule.
- [ ] A stated date that passes becomes "occurrence unconfirmed" until evidence shows it happened; a delay updates the same event and keeps its history.

Files: web/src/components/calendar.js, web/src/styles/calendar.css, web/index.html, web/src/lib/router.js, backend/tools/build_events.py, data/site/events.json
Tests: JOURNEY/test_journeys_market.py::test_j64_the_calendar_draws_only_recorded_or_published_dates_with_their_sources; backend/tests/test_data_site.py::test_every_calendar_event_is_factual_dated_and_sourced; backend/tests/test_repo.py::test_the_published_file_is_what_its_builder_writes_from_the_saved_data

## AS-343 · Finishing touches and motion that never costs speed
IN PROGRESS · P2 · user-facing

The last ten percent of a product reads as care.

- [x] A faint film grain and soft top light give the dark surface depth; micro-interactions use only transform and opacity, end at rest, are off under reduced motion, and never imply liveness the data lacks. Pasting the link shows a 1200 by 630 share card under 150 KB.
- [x] A 404 page in the site's style, a skip link, and a document title naming the product or view.
- [ ] Count-up numbers and the verdict reveal play once and not at all under reduced motion.

Files: web/public/404.html, wrangler.jsonc, web/index.html, web/src/components/app.js, web/src/lib/router.js, web/src/styles/index.css, web/src/lib/dom.js
Tests: JOURNEY/test_journeys.py::test_j63_a_shared_answer_reopens_the_same_scenario_and_the_page_has_a_skip_link; JOURNEY/test_journeys_quality.py::test_j32_motion_plays_when_allowed_ends_at_rest_and_switches_off_when_asked; backend/tests/test_site.py::test_share_card_exists_and_is_the_size_its_tags_promise
Journeys: J-28

### J-28 · The finish
Who: Anyone, on any device, including someone who has asked their device for less motion. Test: JOURNEY/test_journeys_quality.py::test_j32_motion_plays_when_allowed_ends_at_rest_and_switches_off_when_asked

## AS-344 · The companies map
TODO · P2 · user-facing

Who is eating whom, at a glance, from measured inputs only.

- [ ] Organizations as tiles sized by the sum of their products' measured weekly adoption and coloured by AI role; organizations without a measure are counted beside the map, not drawn.

## AS-345 · Market Pulse: developing stories and detectors, each typed and sourced
TODO · P1 · user-facing

Daily content worth opening, without letting talk read as adoption.

- [ ] A story groups one event and its updates; each update has a type (discussed, tested, reported using, reported switching), a source and a date; reposts count once.
- [ ] Each detector is a rule over stored series (a breakout is 2 sigma above a tool's own 26-week level above a volume floor; a crossing is a newcomer overtaking an incumbent in a lane; a regime change is a sign flip held four weeks; attention without adoption is a discussion spike with flat downloads) and emits an event with its inputs; adoption, attention and endorsement are never blended into one score.

## AS-341 · Terminal controls
IN PROGRESS · P1 · user-facing

Keyboard-first, with liveness that is true.

- [x] `/` or Ctrl/Cmd-K opens a palette (a modal `<dialog>`, loaded the first time it opens) that jumps to any view, product or command. Products are the search's own index and ranking; a view or command whose name starts as typed comes first. Arrow keys and Enter, Escape closes and returns focus, Tab stays inside, no animation. The search box is still reached by clicking it or by the command "Search products".
- [ ] A status bar lists each source with its last successful run, read from the data files. Built: the bar is the foot of the palette, not a bar on the page (the page's first screen is unchanged); it lists the pages read for answers, the day the download figures were built, the Wikidata directory, vendor news, the calendar, open models and open-source candidates, each with the date its own file records, or Not observed. Not built: a source with no recorded date in its file (the page re-check tiers in freshness.json record ages, not a run date) is not listed.
- [x] The tape can show only the tools you track (palette command; it says so on the tape, and says nothing changed when none of them has a download figure). It is not remembered after a reload.
- [x] `j` and `k` move through the trending list and the Markets, Makers, news, calendar and stack lists when focus is not in a box.

Files: web/src/components/keys.js, web/src/components/palette.js, web/src/components/hero.js, web/src/styles/terminal.css
Tests: JOURNEY/test_journeys_terminal.py::test_j71_the_palette_jumps_to_a_view_a_product_or_a_command_from_the_keyboard_alone, test_j72_the_palette_fits_a_phone_and_respects_reduced_motion, test_j73_the_status_bar_dates_come_from_the_data_files_and_the_tape_can_show_only_your_tools, test_j74_j_and_k_move_through_a_list_unless_you_are_typing
Journeys: J-59, J-60, J-61

### J-59 · Jump anywhere from the keyboard
Who: Anyone who prefers the keyboard. Test: JOURNEY/test_journeys_terminal.py::test_j71_the_palette_jumps_to_a_view_a_product_or_a_command_from_the_keyboard_alone

### J-60 · The palette's sources are dated by their own files
Who: Anyone checking how fresh the data is. Test: JOURNEY/test_journeys_terminal.py::test_j73_the_status_bar_dates_come_from_the_data_files_and_the_tape_can_show_only_your_tools

### J-61 · Move through a list with j and k
Who: Anyone reading a long list. Test: JOURNEY/test_journeys_terminal.py::test_j74_j_and_k_move_through_a_list_unless_you_are_typing

## AS-347 · Search that forgives
IN PROGRESS · P1 · user-facing

People search by job and misspell names.

- [x] Edit-distance tolerance on names and aliases (1 edit up to six letters, 2 for longer, a swap counts once): offered only when fewer than three results match as typed, ranked below real matches and by distance. Typeahead stays under budget.
- [ ] Category synonyms; groups for categories and capabilities; Enter opens a full results view.
- [ ] A reviewed set of 100 queries with expected top results runs in CI. (A generated set of 120 misspellings of real tools runs now; a person's review of real queries is still owed.)

Files: web/src/components/search/index.js
Tests: JOURNEY/test_journeys_products.py::test_j70_a_misspelled_name_still_finds_the_tool
Journeys: J-58

### J-58 · A misspelled name still finds the tool
Who: Anyone typing a name from memory. Test: JOURNEY/test_journeys_products.py::test_j70_a_misspelled_name_still_finds_the_tool

## AS-335 · Independent Lighthouse cross-check and typeahead under 10 ms
IN PROGRESS · P1

The target is 100 everywhere and instant typeahead; the current gate is 95 for performance and 50 ms under throttling.

- [ ] The mobile performance gate is 100 (median of three) and passes.
- [x] Typing a name with all 21,000 records loaded: p95 4.5 ms unthrottled and 25 ms at 4x CPU slowdown (measured), asserted at 50 ms at 4x by the timing journey, which loads the directory first. A misspelling measures p95 11 ms and 48 ms; its budget in CI is 100 ms at 4x until it is under 10 and 50 with margin on a loaded machine.

Files: web/src/components/search/index.js, JOURNEY/test_journeys_quality.py
Tests: JOURNEY/test_journeys_quality.py::test_j27_every_input_responds_within_a_frame_or_two

## AS-354 · Accessibility and design checks beyond Lighthouse
TODO · P1

Lighthouse is a floor.

- [ ] A recorded screen-reader walk-through of the eight views; every view usable at 200% zoom and 320 px; focus order and names checked (WCAG 2.2 AA).
- [ ] CI fails if the built CSS has more than five font sizes, spacing outside the scale, or the accent on more than 2% of a view's pixels, naming the selector.

## AS-350 · The latest brief holds to a fact contract and hides itself when stale
IN PROGRESS · P1 · user-facing

A short human summary of what moved makes the data readable at a glance; a model may write it but may not add anything.

- [x] `backend/tools/build_brief.py` assembles the day's facts, each with an id, and asks the model once (memoised). Publication requires every number in every sentence to be in the facts that sentence cites, with subject, unit and direction; an unknown citation, dollar amount or banned wording blocks it and the previous brief stays.
- [x] The landing labels it as the latest evidence brief and shows its exact date, who wrote it and what code checked, each item linking its tools. It never implies that an older generated brief is from today.
- [ ] The brief is hidden after 36 hours without a new one, with the reason shown.

Files: backend/tools/build_brief.py, data/brief.json, backend/airstack/schemas.py, backend/airstack/spark.py, backend/airstack/config.py, web/src/components/brief.js
Tests: backend/tests/test_data_site.py::test_each_number_must_carry_its_facts_unit_direction_and_subject, test_a_sentence_that_breaks_the_contract_is_withheld_and_the_rest_is_published, test_the_stored_brief_holds_to_the_contract_and_a_recheck_costs_nothing_and_changes_nothing, test_a_number_from_nowhere_or_from_a_fact_it_did_not_cite_blocks_publication, test_money_and_banned_wording_block_publication; JOURNEY/test_journeys_pages.py::test_j45_the_daily_brief_says_who_wrote_it_and_every_number_in_it_is_in_a_figure_it_cites
Journeys: J-37

### J-37 · Latest evidence in one glance
Who: Anyone landing on the page. Test: JOURNEY/test_journeys_pages.py::test_j45_the_daily_brief_says_who_wrote_it_and_every_number_in_it_is_in_a_figure_it_cites

## AS-351 · One number, one source
IN PROGRESS · P0

Counts differed between the README, the notes and the page, and some docs described features as shipped that were only announced.

- [x] `data/numbers.json` is generated by `tools/update_counts.py`; the README, `llms.txt`, `stats.svg` and `site-data.js` are checked against it, and a test fails when any surface differs or a counted sentence is reworded. The daily run updates it locally for review and never commits or releases it.
- [x] Documents state announced features as announced, with dates, and say what is public.
- [ ] The daily brief on the page states today's counts (needs one live model call, with the owner's approval).
- [ ] CLAUDE.md says the model is called only when evidence changes, never when someone opens a page.

Files: tools/update_counts.py, config/numbers.json, tools/daily.sh, docs/OWNER.md
Tests: backend/tests/test_site.py::test_numbers_json_is_what_the_data_gives_today, test_every_counted_sentence_in_the_readme_and_llms_txt_states_the_number_in_numbers_json, test_the_stats_card_states_the_same_numbers, test_no_surface_states_a_count_of_a_thousand_or_more_that_numbers_json_does_not_hold, test_a_changed_count_or_a_reworded_sentence_is_caught, test_the_daily_run_updates_counts_but_leaves_release_to_a_person, test_the_docs_say_what_the_record_says_announced_not_shipped_and_what_is_public
