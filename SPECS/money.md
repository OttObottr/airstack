# Model usage and cost controls

Paid model work is opt-in, budgeted before dispatch and reconciled with the provider.

## AS-020 · Budget every model call before dispatch
DONE · P0

Each call reserves its maximum cost in a durable ledger before it is sent.

- [x] Sync, research and the nightly batch all call the model through the guarded client; each call logs role, model, tokens, latency, cost, call id and whether a web search ran. The API key is never logged.
- [x] Calls outside the job, day or lifetime cap are rejected before dispatch with a named reason; each research tool has call and input limits.
- [x] Reservations use measured input, the full output allowance and reviewed list prices. Oversized input is rejected.
- [x] Reservation is one database transaction. Open and uncertain reservations count as spent; a failed or timed-out call stays reserved at its maximum until a person reconciles it; the SDK client never retries behind our back.
- [x] A settled cost above its reservation pauses paid work for review. Duplicate jobs share one durable state, and processes using one database share one ledger.

Files: backend/airstack/budget.py, backend/airstack/config.py, backend/airstack/spark.py, backend/airstack/store.py
Tests: backend/tests/test_money.py::test_run_over_cap_is_refused_before_the_call_goes_out, test_run_cap_refuses_when_the_estimate_alone_would_cross_it, test_a_day_over_cap_is_refused_and_the_next_day_is_allowed, test_lifetime_cap_stops_spend_below_the_dashboard_limit, test_per_tool_call_cap_is_8, test_per_tool_search_cap_is_4, test_a_key_in_the_environment_never_reaches_an_mcp_answer_or_a_call_log, test_two_workers_cannot_both_spend_the_same_headroom, test_a_failed_or_timed_out_call_is_still_charged, test_a_call_that_costs_more_than_its_maximum_pauses_all_paid_work, test_a_reservation_is_the_worst_case_not_a_guess, test_in_flight_reservations_count_against_the_job_cap, test_an_uncertain_charge_stays_reserved_at_its_maximum, test_duplicate_job_delivery_is_refused, test_two_processes_on_one_database_file_share_one_ledger

## AS-022 · Model output is validated, and malformed output is never saved
IN PROGRESS · P0

A model can return broken or invented structure. Nothing it says is stored until it passes the schema.

- [x] Every response is checked against its role's flat JSON schema; a malformed response is rejected and no verdict is written.
- [x] Paid model web search is unavailable because the provider does not expose a hard per-call query ceiling.
- [ ] An opt-in smoke run returns schema-valid classify, extract and judge outputs within their reservations.

Files: backend/airstack/spark.py, backend/airstack/schemas.py
Tests: backend/tests/test_truth.py::test_validator_rejects_malformed_shapes, test_a_malformed_spark_response_is_rejected_and_nothing_is_saved; backend/tests/test_money.py::test_live_smoke_returns_schema_valid_outputs_within_reservations

## AS-026 · A preflight shows the settings without showing a secret, and the key stays in .env
DONE · P0

Before any paid run the owner should see which limits are active and whether the key is present, without the key ever being printed.

- [x] `backend/tools/preflight.py` prints only present or MISSING for secrets, plus the caps, the account ceiling, what is committed and what remains. It makes no network call and states that the provider has no hard cap.
- [x] A scan of HTML, JavaScript, Python, fixtures, git history, logs and API output finds no key. `.env` is ignored and an empty `.env.example` ships; only the live client reads the key.

Files: backend/tools/preflight.py, backend/airstack/spark.py
Tests: backend/tests/test_money.py::test_preflight_prints_settings_never_secrets, test_a_key_in_the_environment_never_reaches_an_mcp_answer_or_a_call_log

## AS-027 · Live research is opt-in and account-bounded
DONE · P0

Live research requires an explicit local cap and uses one account-wide reservation ledger.

- [x] With no cap set, live work remains off even when a key is present. Invalid caps resolve to zero and caps above the reviewed ceiling are clamped.
- [x] The live client is the only path to the provider and reserves each call's maximum in one account-wide ledger kept outside the repository (`~/.airstack`), shared by every database, test and process. Configuration can lower the ceiling but never raise it.
- [x] Every call counts at its full reserved maximum; uncertain charges stay reserved and usage anomalies pause live work for review.
- [x] Checked-in price floors cannot be lowered by environment variables; overrides may only reserve more. Paid model web search is disabled before reservation or network access.
- [x] Concurrent processes reserve against the same ceiling atomically.
- [x] Only Standard-mode models are available; requests are bounded, never retried and never follow redirects carrying the bearer token. Tests use a throwaway ledger.
- [x] `tools/reconcile.py` prints the ledger beside the provider's own request and credit counts and exits non-zero unless the counts agree within a small tolerance and our settled cost is never below the provider's.

Files: backend/airstack/account_guard.py, backend/airstack/spark.py, backend/airstack/config.py, backend/tools/preflight.py, .env.example, backend/airstack/budget.py, docs/ARCHITECTURE.md, tools/reconcile.py
Tests: backend/tests/test_money.py::test_configuration_can_lower_the_ceiling_but_never_raise_it, test_price_environment_can_raise_reservations_but_never_lower_reviewed_floors, test_reservations_stop_at_the_ceiling, test_live_research_uses_the_reviewed_model_set, test_paid_web_search_has_no_live_execution_path, test_requests_are_bounded_and_never_retried, test_the_http_client_sends_one_attempt_with_the_key_only_in_the_header, test_live_research_requires_an_explicit_account_cap, test_only_the_guarded_live_client_can_reach_the_provider

## AS-055 · Reuse paid results
DONE · P0

Rebuilds reuse saved results and interrupted runs resume from their last completed input.

- [x] `build_demo_data.py` refuses to overwrite a database holding model calls unless told to start a new live run; earlier runs are kept under `data/runs/`; `run_ab.py` saves after every run and makes only the missing ones.
- [x] Research has one reviewed Standard-mode path. Paid model web search is not enabled.

Files: backend/tools/build_demo_data.py, backend/tools/run_ab.py, backend/airstack/config.py, backend/airstack/spark.py, backend/airstack/budget.py, backend/tools/build_profiles.py
Tests: backend/tests/test_data_site.py::test_a_database_holding_paid_calls_is_never_rebuilt_by_accident; backend/tests/test_money.py::test_a_second_run_is_free_and_only_missing_runs_are_made, test_standard_replay_uses_the_paid_memo_without_spend, test_live_research_uses_the_reviewed_model_set

## AS-205 · Provider billing controls
TODO · P0

Provider settings complement the application ledger. Owner-only checks live in `docs/OWNER.md`.

- [ ] Provider spend limit set with no automatic top-up; GitHub Actions budget at zero with usage stopped; Cloudflare budget alert on the account.
- [ ] Every owner-only step (keys, logins, connector checks, local cleanup) is listed with exact steps and ticked with the date it was done.

## AS-206 · Standard processing and redacted private context
DONE · P0

Live research uses Standard mode. Private stack context is redacted from logs.

- [x] The live client exposes only the reviewed Standard-mode models.
- [x] For any call made in a seat's context the log keeps only the request's shape, marked redacted; no requirement text reaches it.

Files: backend/airstack/config.py, backend/airstack/spark.py
Tests: backend/tests/test_money.py::test_live_research_uses_the_reviewed_model_set; backend/tests/test_truth.py::test_private_seat_context_is_redacted_in_the_calls_log
