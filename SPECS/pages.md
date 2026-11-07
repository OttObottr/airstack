# Static pages

Crawlable pages generated from the same data files the app reads: products, makers, categories, comparisons and the taxonomy.

## AS-252 · A static page per product with structured data and a sitemap
DONE · P1 · user-facing

Search and answer engines cannot read hash routes, and often do not run scripts. A page per product makes the research findable and citable.

- [x] `build_pages.py` writes `/p/<slug>/` for every tracked, cataloged or researched product, and `sitemap.xml` with every page. The landing's claim and meta description are plain HTML; `robots.txt`, `sitemap.xml` and `llms.txt` point at airstack.bot, and `llms.txt` cites only references the checker verifies.
- [x] Structured data is SoftwareApplication; offers come only from sourced list prices, each with its pricing page URL. A price is shown only when read on the product's own site (a shared host's pricing page is nobody else's price); a starting price is a plan with a stated unit and period, never an add-on or credit.
- [x] A directory listing gets no alternatives list. Wording says what AirStack has not found, never that a vendor lacks something.
- [x] Each catalog product in the app links its shareable page.
- [x] Addresses are readable: a product page is `/p/<name>/` and a maker page `/o/<name>/` (an id suffix only where two names read the same); the app writes `#app=<name>` where the name is unique among listings, still opens old `#app=Q…` links, and rewrites them to the readable form.

Files: backend/tools/build_pages.py, backend/tools/pages/*.py, data/site/sitemap.xml, web/src/components/cards/catalog.js, tools/deploy.sh, web/index.html, web/public/robots.txt, web/public/llms.txt
Tests: backend/tests/test_pages.py::test_every_page_has_a_title_a_description_a_canonical_url_and_parseable_structured_data, test_an_offer_or_a_price_on_a_page_is_always_a_sourced_list_price, test_pages_never_show_another_sites_prices_invented_alternatives_or_claims_the_table_does_not_hold; JOURNEY/test_journeys_pages.py::test_j51_a_products_static_page_is_readable_without_javascript_and_links_back_to_the_app; backend/tests/test_site.py::test_structured_data_says_only_what_the_page_says, test_llms_txt_only_cites_references_the_checker_verifies
Journeys: J-01, J-42

### J-42 · A page you can share and a search engine can read
Who: Anyone sharing a product, and every crawler. Test: JOURNEY/test_journeys_pages.py::test_j51_a_products_static_page_is_readable_without_javascript_and_links_back_to_the_app

## AS-317 · A page per software maker, and a shareable makers leaderboard
DONE · P1 · user-facing

Makers are search and answer-engine entry points, and the leaderboard should be explorable and shareable.

- [x] `build_pages.py` writes `/o/<slug>/` for every organization with at least one listed product: kind, country, founded, employees as Wikidata records them, products linked, official channels, dated follower counts, and founders and leaders by name and role only. Organization structured data, canonical address, Open Graph tags and a sitemap entry; product pages link their makers.
- [x] `/o/` ranks businesses by headcount only when the figure is dated 2015 or later, one per website, never a public body or an item that is itself a product; implausible headcounts are flagged in the data with the reason and never shown as a number. `/o/in/<country>/` needs three makers.
- [x] The Makers view in the app searches by name, country and kind, sorts by headcount, product count or name, and holds the view in the address so a link restores it; it reads `o/makers.json`, written by the same function as the hub.

Files: .gitignore, backend/tools/build_pages.py, backend/tools/pages/*.py, data/site/sitemap.xml, tools/assemble.sh, web/src/components/makers.js, web/src/styles/makers.css, backend/tools/build_directory.py, data/site/directory.json
Tests: backend/tests/test_pages.py::test_every_organization_page_is_citable_and_links_only_what_exists, test_a_product_page_links_its_maker_to_a_page_that_exists, test_every_maker_page_lists_a_product_and_the_leaderboard_ranks_only_what_wikidata_dates, test_the_makers_view_data_ranks_exactly_what_the_hub_ranks; JOURNEY/test_journeys_pages.py::test_j65_a_makers_page_is_readable_without_javascript_and_links_its_products; JOURNEY/test_journeys_market.py::test_j68_the_makers_view_is_searchable_filterable_and_every_state_is_a_link; backend/tests/test_data_site.py::test_a_headcount_out_of_line_with_the_organizations_documentation_or_kind_is_flagged_and_never_carried_as_a_number, test_the_published_directory_is_rebuilt_byte_for_byte_from_the_saved_wikidata_responses
Journeys: J-53, J-56

### J-53 · A page for every software maker
Who: Anyone sizing up a vendor, and every crawler and answer engine. Test: JOURNEY/test_journeys_pages.py::test_j65_a_makers_page_is_readable_without_javascript_and_links_its_products

### J-56 · Explore the software makers
Who: Anyone sizing up a vendor, a journalist, an analyst. Test: JOURNEY/test_journeys_market.py::test_j68_the_makers_view_is_searchable_filterable_and_every_state_is_a_link

## AS-318 · A page per category
DONE · P1 · user-facing

Category pages are where buyers start and what answer engines cite.

- [x] `build_pages.py` writes `/c/<category>/` for every category with product pages: AirStack's guide, the numbers as counts, the median per-user monthly list price with its product and source, and every product with what it says it does and its cheapest paid plan as quoted (or "Not observed").
- [x] Vetted open-source candidates and the most downloaded open models appear where they exist; CollectionPage structured data lists the products; product breadcrumbs link to the category.

Files: backend/tools/build_pages.py, backend/tools/pages/*.py, tools/assemble.sh, .gitignore, data/site/sitemap.xml
Tests: backend/tests/test_pages.py::test_every_category_page_lists_its_products_and_shows_only_sourced_prices; JOURNEY/test_journeys_pages.py::test_j66_a_category_page_is_readable_without_javascript_with_its_products_and_sourced_prices
Journeys: J-54

### J-54 · A page for every category
Who: Anyone comparing a kind of software, and every crawler and answer engine. Test: JOURNEY/test_journeys_pages.py::test_j66_a_category_page_is_readable_without_javascript_with_its_products_and_sourced_prices

## AS-319 · Comparison pages built from each product's own pages
DONE · P1 · user-facing

Buyers search one product against another; a side-by-side of each product's own quotes answers that without an invented verdict.

- [x] `/compare/<a>-vs-<b>/` exists for every same-category pair of researched products whose own pages state at least four of the same facts, each with its source and "Not observed" where a page did not say. Thinner pairs get no page.
- [x] "Where they differ" lists plain statements limited to free plan, open source and security claims; nothing is scored, ranked or recommended. Product pages link their comparisons.

Files: backend/tools/build_pages.py, backend/tools/pages/*.py, tools/assemble.sh, .gitignore, data/site/sitemap.xml
Tests: backend/tests/test_pages.py::test_a_comparison_page_exists_only_where_both_products_state_enough_of_the_same_facts, test_the_generated_pages_stay_under_the_hosts_file_limit; JOURNEY/test_journeys_pages.py::test_j67_a_comparison_page_puts_two_products_own_pages_side_by_side
Journeys: J-55

### J-55 · Two products side by side
Who: A buyer choosing between two products, and every crawler and answer engine. Test: JOURNEY/test_journeys_pages.py::test_j67_a_comparison_page_puts_two_products_own_pages_side_by_side

## AS-285 · A faceted taxonomy
TODO · P2 · user-facing

A single tree starts arguments; independent facets let a buyer reach the same product by job, department or industry without duplicates.

- [x] `/t/` lists the areas and states how many listed products carry no category yet (it does not guess); `/t/<category>/` gives a definition, what it includes, examples, subcategories and its products, with CollectionPage data and a sitemap entry.
- [ ] Facets (department, job, capability, industry, delivery, commercial model, lifecycle) each have definitions and examples; outside classifications are kept as crosswalks (equivalent, broader, narrower, overlapping).
- [ ] An ambiguity set (support and success, CRM and CDP, observability and analytics) is scored in CI.

Files: .gitignore, backend/tools/build_pages.py, backend/tools/pages/*.py, backend/tools/build_taxonomy.py, config/taxonomy-crosswalk.json, config/taxonomy.json, data/site/taxonomy-index.json, tools/assemble.sh
Tests: backend/tests/test_data_market.py::; backend/tests/test_pages.py::test_the_software_taxonomy_pages_place_each_product_once_and_say_how_much_is_not_placed
Journeys: J-57

### J-57 · The market for every kind of software
Who: Anyone exploring a category beyond developer tools. Test: JOURNEY/test_journeys_market.py::test_j69_markets_covers_every_kind_of_software_sized_by_documentation_and_says_what_it_is_not

## AS-286 · Firmographics that are records
TODO · P2 · user-facing

Headcount alone is thin; the records that exist publicly can be shown with their sources, and claims labelled as claims.

- [ ] An organization page shows founded and headquarters (Wikidata), legal entity and parent (GLEIF), filings (SEC EDGAR) and domain age (RDAP), each linked and dated; disagreements are shown, not resolved silently.
- [ ] Funding appears only from the company's own release or Wikidata, labelled as claimed.

Files: backend/tools/build_firmographics.py, data/site/firmographics.json
Tests: backend/tests/test_data_graph.py::

## AS-254 · An embeddable stats card
DONE · P2 · user-facing

AirStack's numbers should travel: a README, post or slide can embed one image that shows what the deployed site shows.

- [x] `build_stats.py` writes `stats.svg` from the files the site reads: products, organizations, products read from their own pages, quoted list prices and the movers tape with its 7-day window.
- [x] It is dated by its data, light and dark, animated with CSS only and still under reduced motion, and served with no-cache.

Files: backend/tools/build_stats.py, data/site/stats.svg, tools/deploy.sh, web/public/_headers
Tests: backend/tests/test_data_site.py::test_the_committed_card_is_the_one_the_data_builds_and_its_numbers_are_the_sites; JOURNEY/test_journeys_market.py::test_j52_the_stats_card_renders_the_sites_counts_and_its_dated_tape
Journeys: J-43

### J-43 · AirStack's numbers, embedded anywhere
Who: Anyone reading the README, a post or a slide. Test: JOURNEY/test_journeys_market.py::test_j52_the_stats_card_renders_the_sites_counts_and_its_dated_tape

## AS-363 · A maker's full product tree, shown for large makers
TODO · P2

A large maker (for example Meta) owns many products and sub-products; a flat list hides how they relate.

- [ ] A maker page shows its listed products as a tree by parent product, from Wikidata's own parent relations, each node linked to its page.
- [ ] A product with no recorded parent appears at the top level; relations that Wikidata does not record are not guessed.
