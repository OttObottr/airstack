# Data and research

How facts are collected: pages read politely, a model extracts, and code admits a fact only if its quote is on the page.

## AS-327 · Market research: the model extracts, code verifies every quote, every input is paid for once
DONE · P0

Breadth has to be real. A fact exists only if code finds its words on the page it came from.

- [x] Pages are fetched once and re-fetched conditionally; a script shell or error page is never sent to a model. An oversized page is skipped and named; only a real budget stop ends a batch.
- [x] The catalog role has a closed metric vocabulary and requires a verbatim quote for every fact. Code admits a fact only if its quote is on the page, list items each appear, and a number appears in its quote.
- [x] The guarded client consults a memo keyed by role, model, prompt version, schema and input before reserving anything; a hit replays the stored output at no cost. A replay re-checks without re-counting.
- [x] The batch has its own cap below the account ceiling and stops before sending when it would pass it. The recorded run verified 207 of 229 claims (90.4%).

Files: backend/airstack/corpus.py, backend/airstack/spark.py, backend/airstack/schemas.py, backend/tools/build_market.py, backend/tools/build_profiles.py
Tests: backend/tests/test_data_market.py::test_only_facts_whose_words_are_on_the_page_are_admitted, test_a_second_run_costs_nothing_and_admits_nothing_new, test_a_shell_or_missing_page_is_never_sent_to_the_model, test_a_refetch_is_conditional_and_a_304_reuses_the_stored_text, test_the_batch_stops_at_its_cap_before_sending, test_values_are_checked_against_the_page_not_trusted, test_shapes_are_coerced_by_code_only_when_the_quote_still_holds, test_a_page_that_ships_its_text_as_one_long_line_still_fits_the_envelope
Journeys: J-15

### J-15 · The market, cell by cell
Who: A skeptical analyst. Test: JOURNEY/test_journeys_market.py::test_j15_the_market_every_cell_is_sourced_or_says_not_observed

## AS-328 · The market, comparable cell by cell, and what you already have
DONE · P0 · user-facing

Every cell is a verified fact with its page and date, or says "Not observed".

- [x] One vocabulary per column so vendors compare like for like; every cell links the page it was verified on; a missing fact reads "Not observed", never blank or zero.
- [x] No price reaches the screen from this table; the generator refuses a displayed quote with a currency amount.
- [x] Check yours covers Google, Zoom and Microsoft plans, online or in person; a plan with no verified fact reads "Not known yet". Platform answers are rules over verified quotes and cite the extraction they rest on.

Files: backend/tools/build_market_data.py, data/site/market-data.js, web/src/components/market-table.js, web/src/lib/market.js
Tests: backend/tests/test_data_market.py::test_every_shown_value_has_its_pages_and_no_price_reaches_the_screen, test_platform_answers_rest_on_verified_quotes_or_say_unknown, test_the_corpus_counts_each_claim_once_and_its_pass_rate_is_published; JOURNEY/test_journeys_market.py::test_j15_the_market_every_cell_is_sourced_or_says_not_observed; JOURNEY/test_journeys.py::test_j16_check_yours_covers_zoom_and_teams_from_verified_quotes, test_j20_task_a_zoom_user_gets_a_sourced_answer_in_four_interactions
Journeys: J-15, J-16, J-20

### J-16 · Check yours on Zoom or Teams
Who: Someone on Zoom or Microsoft. Test: JOURNEY/test_journeys.py::test_j16_check_yours_covers_zoom_and_teams_from_verified_quotes

### J-20 · Can I drop it? In a few taps
Who: A Zoom user paying for a note-taker. Test: JOURNEY/test_journeys.py::test_j20_task_a_zoom_user_gets_a_sourced_answer_in_four_interactions

## AS-137 · Product profiles for every tool in the universe
IN PROGRESS · P0 · user-facing

Each tracked tool gets a profile of facts read from its own pages, every one with its quote verified on the page.

- [x] A generic profile vocabulary (what it does, open source, licence, deployment, platforms, SDK languages, models, integrations, compliance, plans, pricing basis) passes the same gate as the market corpus.
- [x] Calls run in a small thread pool over one lock; each still reserves its maximum in the account ledger, and the memo means no input is paid for twice.
- [x] The first run read 36 homepages: 177 claims produced, 162 verified on the page (91.5%); rejections are counted by reason.
- [x] Moving this week shows "Profile · N facts" for any tool with one, opening the facts with links and a list of what was not observed; `#tool=id` deep-links to it.
- [ ] Pricing, docs, integrations and security pages for the expanded universe, read in tranches with the pass rate checked before each.
- [ ] Weighted market membership with the claims behind it ("Why this product appears here").

Files: backend/tools/build_profiles.py, backend/airstack/corpus.py, backend/airstack/schemas.py, backend/tools/build_market_data.py, web/src/components/profile.js, web/src/lib/profiles.js
Tests: backend/tests/test_data_market.py::test_only_facts_whose_words_are_on_the_page_are_admitted, test_a_second_run_costs_nothing_and_admits_nothing_new, test_every_shown_value_has_its_pages_and_no_price_reaches_the_screen; JOURNEY/test_journeys_products.py::test_j24_a_tool_profile_opens_with_only_verified_facts_and_a_deep_link
Journeys: J-24

### J-24 · Open a tool's profile
Who: Someone scanning Moving this week. Test: JOURNEY/test_journeys_products.py::test_j24_a_tool_profile_opens_with_only_verified_facts_and_a_deep_link

## AS-224 · Track the paid SaaS tools people actually renew
TODO · P0

The tracked tools are what a package registry can count, not what a renewal line item names. The first thing anyone types is a famous paid product.

- [ ] About 40 paid products have profiles from their own pricing, plans and security pages, through the existing pipeline.
- [ ] Signals for them without a registry: store users, app-store counts, marketplace installs, attention.
- [ ] Eight named popular products each return a profile of at least six facts.

## AS-237 · Everyday business software is tracked and found by name, alias or category
DONE · P0 · user-facing

The universe was seeded from package registries, so only developer tools existed. A buyer renews email, chat, CRM and design software.

- [x] `data/catalog.json` lists mainstream paid products in business categories, each homepage, pricing, docs, integrations and security URL fetched by `tools/check_catalog.py` (status, final URL, title, date); entries whose homepage was not reached are not listed.
- [x] The page finds them by name, alias or typo and gives each a page with its vendor, its category (labelled as AirStack's classification) and the links reached.
- [x] One list of categories feeds the checker, the page and the endpoint.

Files: config/catalog.json, tools/check_catalog.py, backend/airstack/catalog.py, backend/tools/build_site_data.py, backend/tools/build_market_data.py, web/src/components/search/index.js, web/src/components/cards/catalog.js
Tests: backend/tests/test_data_site.py::test_every_entry_has_the_fields; JOURNEY/test_journeys_products.py::test_j44_everyday_business_software_is_found_by_name_alias_or_category_and_its_page_says_only_what_is_known
Journeys: J-36

### J-36 · The software I actually pay for
Who: A buyer whose renewals are Gmail, Slack, Salesforce and Figma, not developer packages. Test: JOURNEY/test_journeys_products.py::test_j44_everyday_business_software_is_found_by_name_alias_or_category_and_its_page_says_only_what_is_known

## AS-236 · Track the package that is the product
TODO · P2

A tool that migrated or split its packages is measured on the legacy one, so downloads mislead.

- [ ] Each tool declares its primary package per registry, with the reason; siblings are listed, not silently summed.
- [ ] Where a tool has counts in more than one registry, both are shown and a larger sibling is named.

Files: backend/airstack/connectors/registries.py, backend/tools/build_movers.py
Tests: backend/tests/test_data_chain.py::

## AS-248 · Every software product and company Wikidata records is searchable and browsable, labelled as Wikidata's record
DONE · P0 · user-facing

A team asks about whatever it pays for. AirStack researches a few hundred products in depth; the rest of the market must still be findable, honestly labelled and linked to a record a stranger can open.

- [x] `backend/tools/build_directory.py --fetch` queries Wikidata (CC0) for items typed under software with an official website and at least one Wikipedia or sister-site page, the companies that make them, and the type tree. Every raw response is saved with its query and time; the build repeats offline byte for byte.
- [x] Fan-out adds online services and every listed maker's websites, round by round. Shops, forums, archives, reserved domains and sites documented in under three languages are not products; end dates retire discontinued products; a maker of two or more products opens as the organization.
- [x] Listings already covered by the catalog or registry are left to them; every type's lineage reaches "software" and each product is counted once.
- [x] The page loads `directory.json` on first search or link; a listing shows Wikidata's description, maker, type path, website and record link with its read date, and says it has not been researched. MCP returns listings marked as from Wikidata, ranked below tracked tools unless the name is exact.
- [x] `build_profiles.py --directory N` researches the best-known listings' homepages through the same quote gate.

- [x] A content policy keeps out piracy, adult content, illegal markets and malware: `config/excluded.json` names the rules, the directory builder drops matching listings and organizations and records their ids, and no builder publishes research for those ids. Legitimate neighbours (BitTorrent clients, security tools) stay, and a vandalised label is listed under its real name.

Files: backend/tools/build_directory.py, config/excluded.json, backend/airstack/policy.py, data/site/directory.json, web/src/components/search/directory.js, web/src/components/cards/directory.js, web/src/components/browse.js, backend/tools/build_site_data.py, backend/tools/build_profiles.py, tools/deploy.sh, web/public/sw.js, backend/airstack/wikidata.py
Tests: backend/tests/test_data_site.py::test_the_published_directory_is_rebuilt_byte_for_byte_from_the_saved_wikidata_responses, test_the_taxonomy_hangs_from_software_and_its_counts_add_up; JOURNEY/test_journeys_products.py::test_j47_every_software_product_and_company_wikidata_records_is_searchable_and_says_it_is_listed_not_researched; backend/tests/test_pages.py::test_no_listing_matches_the_policy, test_legitimate_neighbours_of_excluded_categories_stay_listed, test_a_label_carrying_vandalism_is_listed_under_its_real_name, test_nothing_excluded_reaches_published_research, test_no_published_file_names_a_blocked_site
Journeys: J-38

### J-38 · Find anything, and know how much is known
Who: Anyone looking for a product AirStack hasn't researched. Test: JOURNEY/test_journeys_products.py::test_j47_every_software_product_and_company_wikidata_records_is_searchable_and_says_it_is_listed_not_researched

## AS-264 · Communities and people from Wikidata
IN PROGRESS · P1 · user-facing

Communities, channels and leaders around each organization and product, without scraping anyone.

- [x] `build_community.py --fetch` saves every Wikidata response and rebuilds offline byte for byte: links and handles as Wikidata records them, dated follower counts, founders and leaders with a Wikidata item. Every id is validated by pattern.
- [x] Nothing is scraped from the platforms; a missing link means Wikidata has none. Product and organization pages show known public channels, linked, with roles as Wikidata records them. Dated follower counts remain Wikidata statements, never presented as live.
- [x] Product pages separate a known channel from measured attention and both from adoption: retained Hacker News stories are counted only inside their stated feed window; a link to a social channel never implies conversation there. Sources without evidence are omitted from the product UI rather than rendered as zero or as dead placeholders; internal coverage state remains explicit in the connector manifest.

Files: backend/tools/build_community.py, data/site/community.json
Tests: backend/tests/test_data_site.py::test_the_published_file_is_rebuilt_byte_for_byte_from_the_saved_wikidata_responses, test_no_field_holds_an_email_address, test_a_person_is_named_by_their_own_wikidata_item_and_role_only; JOURNEY/test_journeys_products.py::test_j80_a_product_separates_known_channels_measured_attention_and_omits_unmeasured_sources

## AS-250 · List prices as written on each product's own pricing page, each linked with its quote
DONE · P0 · user-facing

What a product costs is the first thing a buyer compares. The only dollar figures on the site are sourced list prices.

- [x] `build_pricing.py` has the model read each stored pricing page and return each plan's price as written, with its period, unit and a quote. Code keeps a price only when the quote is on the page, contains the price, states a currency, and names the plan.
- [x] `--discover` finds each researched product's pricing page from a link on its own homepage, else a conventional path whose text names a currency; the URL and how it was found are recorded.
- [x] A product page shows "Plans and list prices" with each price linked to its page; MCP `get_profile` returns the list prices.

Files: backend/tools/build_pricing.py, backend/airstack/schemas.py, backend/airstack/spark.py, web/src/components/prices.js, web/src/lib/profiles.js, data/pricing-pages.json, data/site/pricing.json
Tests: backend/tests/test_data_site.py::test_a_price_is_kept_only_when_its_quote_is_on_the_page_and_contains_it, test_an_invented_price_a_quote_from_nowhere_or_a_missing_currency_is_refused; JOURNEY/test_journeys_products.py::test_j49_list_prices_are_shown_as_written_each_linked_to_its_page_with_its_quote
Journeys: J-40

### J-40 · What it costs, as the vendor writes it
Who: Anyone comparing what they pay for. Test: JOURNEY/test_journeys_products.py::test_j49_list_prices_are_shown_as_written_each_linked_to_its_page_with_its_quote

## AS-251 · Open-source alternatives, vetted by automated checks and labelled as leads
DONE · P0 · user-facing

A buyer weighing a paid tool should see open-source projects that do the same job, with signals that go beyond star counts.

- [x] `build_oss.py --fetch` queries GitHub for each category's topics (500 or more stars, not archived, not a fork, not a curated list) and saves every response; the build repeats offline.
- [x] `--vet` saves each candidate's OpenSSF Scorecard result. A project passes with a score of 5 or more, no dangerous CI workflow, no committed binaries and no known open vulnerabilities; passing projects rank first.
- [x] A product page lists up to eight projects with stars, licence, last push, score, a ten-check reputation graph and plain-words findings; a repository not scanned says "unknown". Nothing is called malicious or safe from a heuristic; the section says the checks are automated, not an audit.
- [x] Each repository also shows the saved GitHub fork count, combined open-issue-and-pull-request count and whether Discussions is enabled, explicitly distinguishing activity from capability and both from use, sentiment or trust. Social-platform discussion is not inferred from those fields and no composite popularity score is invented.
- [x] A bounded build-only pass runs one exact GitHub-repository URL query per unique candidate against the public Hacker News search index, saves the response, and rebuilds offline. A successful zero, missing snapshot and failed refresh remain different internal states; only actual repository-linked stories appear in the UI, with points, comments, date and discussion link.

Files: backend/tools/build_oss.py, backend/tools/pages/category.py, web/src/components/cards/catalog.js, web/src/lib/profiles.js, data/site/oss.json, web/src/styles/motion.css
Tests: JOURNEY/test_journeys_products.py::test_j50_a_product_shows_open_source_alternatives_from_github_each_linked_with_its_repository_attention_and_licence; backend/tests/test_data_site.py::test_vetted_projects_come_first_and_every_flag_is_a_finding_not_an_accusation; backend/tests/test_repo.py::test_the_published_file_is_what_its_builder_writes_from_the_saved_data
Journeys: J-41

### J-41 · The open-source way to do the same job
Who: Anyone weighing a paid tool. Test: JOURNEY/test_journeys_products.py::test_j50_a_product_shows_open_source_alternatives_from_github_each_linked_with_its_repository_attention_and_licence

## AS-259 · Open models you can run, per job, from the Hugging Face Hub's own counts
DONE · P1 · user-facing

For AI categories the real alternative to a subscription is often an open model, and its adoption is public.

- [x] `build_hf.py --fetch` saves every Hub response; the build repeats offline. Fifteen models per job for eight jobs by 30-day downloads, with likes, licence (only from a licence tag, else not stated) and whether gated.
- [x] AI product pages list the top models for their jobs, labelled as a lead, not an endorsement.

Files: backend/tools/build_hf.py, data/site/hf.json, web/src/components/cards/guide.js, tools/assemble.sh
Tests: backend/tests/test_data_graph.py::test_the_committed_hf_json_is_rebuilt_byte_for_byte_from_the_saved_responses, test_a_licence_is_null_or_a_license_tag_the_api_returned; JOURNEY/test_journeys_products.py::test_j55_a_product_says_why_teams_use_its_category_and_which_open_models_do_the_job
Journeys: J-47

### J-47 · Why you'd want it, and who uses it
Who: Someone deciding whether a kind of tool is for them. Test: JOURNEY/test_journeys_products.py::test_j55_a_product_says_why_teams_use_its_category_and_which_open_models_do_the_job

## AS-255 · A publication-grade market brief from stored facts
DONE · P1 · user-facing

Buyers ask which products are AI-first and which are incumbents adding AI, what is normal in a category, and what everything connects to. Insights turns the stored facts into a short analytical argument rather than an undifferentiated dashboard of widgets.

- [x] `build_insights.py` places a researched product by how widely it is documented and where AI appears in what its own pages say; a product missing either input is counted as unplaced. No model call.
- [x] AI evidence is read from every own-page fact (the one-line description is strongest, then models named, AI providers integrated, AI in plan names); each point records which. The map states its two populations (the categories AirStack follows, and all listed software) so a total never misleads; a toggle chooses one. A guard test fails if fewer than 75% of products cataloged as AI show AI evidence, to catch a broken classifier.
- [x] Per category: free plan, SOC 2 or ISO 27001, open source, AI in the one-liner and a quoted list price, each as a count over the researched products with its denominator, grouped by the department it serves; a median price appears only with five or more products publishing a per-user monthly plan price.
- [x] Hubs: the products most often named in other products' integration lists. A failed load of this view is logged, not silent.
- [x] The page opens with a measured thesis and three direct takeaways, then moves through three questions: where vendors put AI, what categories consistently disclose, and which products form the market's connective tissue. The design is an original editorial report, not an imitation of another publication and not a card grid.
- [x] Every visual states its population, denominator, scale and missing-input count in the reading flow. Restrained color carries meaning; annotations explain the strongest visible result; no composite or invented score is shown. Tables remain available for exact values, but the first read is a curated argument with body-readable source notes.

Files: backend/tools/build_insights.py, config/departments.json, data/site/insights.json, web/index.html, web/src/components/insights.js, web/src/styles/insights.css
Tests: backend/tests/test_data_site.py::test_every_researched_product_is_placed_on_measured_inputs_or_counted_as_unplaced, test_category_shares_have_their_denominator_and_the_median_price_is_a_quoted_list_price, test_the_ai_classifier_finds_ai_where_products_are_sold_as_ai; backend/tests/test_repo.py::test_the_published_file_is_what_its_builder_writes_from_the_saved_data; JOURNEY/test_journeys_market.py::test_j56_insights_place_only_measured_products_and_say_what_each_axis_is, test_j81_insights_reads_as_a_sourced_argument_not_a_widget_grid
Journeys: J-48

### J-48 · The market, measured
Who: Anyone sizing up a category. Test: JOURNEY/test_journeys_market.py::test_j56_insights_place_only_measured_products_and_say_what_each_axis_is

## AS-258 · Why teams use each category and who uses it
DONE · P1 · user-facing

A list of products does not say why anyone would want one.

- [x] `data/category-guides.json` holds, for every category, what it is for, what it gets you, the jobs, who uses it, what a basic version usually includes and what to watch for. It is labelled as AirStack's guide, carries no numbers, dollar figures or hype words (a test holds that line), and appears on each product page.

Files: config/category-guides.json, web/src/components/cards/guide.js, web/src/styles/guide.css, tools/assemble.sh
Tests: backend/tests/test_data_site.py::test_every_category_and_lane_on_the_site_has_a_guide_and_nothing_else, test_no_numbers_prices_hype_or_verdict_words; JOURNEY/test_journeys_products.py::test_j55_a_product_says_why_teams_use_its_category_and_which_open_models_do_the_job
Journeys: J-47

## AS-263 · A freshness scheduler, and a daily refresh that stays inside its budget
DONE · P1

The corpus grows by thousands of pages; re-reading all of it on a fixed timer wastes money, and never re-reading it lets answers go stale.

- [x] `refresh.py` plans every page that backs a fact or price by tier (pricing 7 days, catalog 14, directory 30); the interval halves after a change and doubles after quiet checks. Stage 1 is free: a conditional GET and a search for each stored quote. Only pages that lost a quote are re-extracted, which needs `--live` and the owner's cap.
- [x] `freshness.json` publishes per tier the page count, median and 95th-percentile age and share inside its interval; no spend figure.
- [x] `tools/daily.sh` (launchd) runs only the free refresh from the already-reviewed local checkout, rebuilds and verifies locally. It never pulls code, authorizes paid work, commits, pushes or deploys. Pages that lost a quote are left in a review file; re-extraction and release are separate, explicit owner actions.
- [x] `tools/update_counts.py` rewrites the README's and `llms.txt`'s counts from the generated files.

Files: backend/tools/refresh.py, backend/tools/reverify_corpus.py, data/site/freshness.json, tools/daily.sh, tools/bot.airstack.daily.plist, tools/update_counts.py, backend/tools/build_profiles.py
Tests: backend/tests/test_data_market.py::test_a_page_that_changed_is_checked_sooner_and_a_quiet_page_later_within_bounds, test_every_page_behind_a_fact_or_a_price_is_planned_and_the_public_file_has_no_money; backend/tests/test_repo.py::test_the_scheduled_refresh_cannot_spend_pull_push_or_deploy

## AS-265 · What changed, in each vendor's own words
DONE · P1 · user-facing

A market page is worth reading daily only if it says what changed. Vendors' feeds, releases and the stories linking to them are free and dated.

- [x] `build_news.py --fetch` finds each catalog product's feed (linked from its homepage or at a common path), GitHub releases for tracked repositories, and Hacker News stories linking to the product's own site; every response is saved and `news.json` rebuilds offline. No model call.
- [x] An item counts only if it links to the vendor's own domain (on a shared host, only the product's own path); build tags and pre-releases are skipped. Feeds are untrusted: a DTD or entity declaration is refused and bodies are capped at 2 MB.
- [x] Overview lists changes newest day first, one row per product per day: changelog, then Hacker News stories with 5 or more points, then releases; other updates fold under it with dates and kinds. Blog posts are one toggle away; nothing dated after the read is shown.
- [x] A bare tag or version number never leads “What changed.” GitHub release notes are saved with the raw response and a deterministic, publisher-written semantic line leads the item; the tag is supporting detail. A release with no meaningful note is omitted rather than presented as insight or rewritten by AirStack.

Files: backend/tools/build_news.py, data/site/news.json, web/src/components/news.js, web/src/styles/news.css, web/index.html
Tests: backend/tests/test_data_site.py::test_every_item_links_to_its_products_own_site_or_its_repository_and_no_build_tags, test_a_bare_release_version_never_pretends_to_explain_what_changed, test_an_untrusted_feed_cannot_declare_entities_or_a_doctype; backend/tests/test_repo.py::test_the_published_file_is_what_its_builder_writes_from_the_saved_data; JOURNEY/test_journeys_market.py::test_j57_what_changed_lists_each_vendors_own_announcements_by_day_with_blogs_behind_a_toggle
Journeys: J-49

### J-49 · What changed this week
Who: Anyone who wants the day's software news worth reading. Test: JOURNEY/test_journeys_market.py::test_j57_what_changed_lists_each_vendors_own_announcements_by_day_with_blogs_behind_a_toggle

## AS-238 · Claims are compared with the vendor's own registry records, as a second record and not independent proof
DONE · P1

A licence or language claim can be checked against what the vendor published on PyPI, npm and GitHub. Those records come from the same vendor, so agreement is a second record, never independent confirmation.

- [x] `backend/tools/corroborate.py` reads registry metadata (cached, replayable offline) and compares licence, open source, SDK languages and platforms value for value.
- [x] The chain carries a registry record per claim and counts matches and disputes separately; nothing lands in the independent count.

Files: backend/tools/corroborate.py, backend/tools/build_chain_data.py
Tests: backend/tests/test_data_chain.py::test_registry_records_merge_into_the_chain_never_into_agree_independent_and_are_counted_apart, test_an_agreeing_and_a_disagreeing_license_are_both_recorded_with_both_values, test_the_chain_builds_unchanged_when_corroboration_json_is_absent

## AS-334 · More than one source per fact: independent second records
TODO · P0

Today a fact's second record is the vendor's own registry entry, so independent corroboration is zero.

- [ ] Second records from keyless sources the vendor does not write: app stores, VS Code Marketplace, Docker Hub, Wikipedia pageviews, GDELT, RDAP.
- [ ] A fact shows "corroborated" only when an independent source states the same value; same-vendor records stay "second record".
- [ ] The corroboration rate is published (AS-336).

Files: backend/tools/corroborate.py
Tests: backend/tests/test_data_chain.py::
