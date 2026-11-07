# MCP and agents

AirStack exposes reviewed data to local agents over stdio.

## AS-062 · The MCP server offers read-only tools and never spends
DONE · P0

Agents can inspect the same reviewed record from their local tools.

- [x] Tools: `get_verdict`, `get_evidence`, `changes_since`, `review_stack`, `get_entity`. Arguments are schema-validated.
- [x] Every tool is read-only, imports no model code and makes no network request.
- [x] A stack review accepts at most 25 tools; a context-free lookup is labelled as a reference scenario.
- [x] A JSON-RPC notification produces no response.

Files: backend/airstack/mcp_server.py, backend/airstack/views.py
Tests: backend/tests/test_money.py::test_every_mcp_tool_makes_zero_spark_calls, test_public_read_modules_cannot_even_import_spark, test_oversized_stack_review_is_rejected, test_notifications_get_no_response, test_the_stdio_loop_writes_nothing_for_a_notification; backend/tests/test_truth.py::test_a_context_free_lookup_is_labelled_as_a_reference_scenario

## AS-136 · Connect local agent clients
DONE · P0 · user-facing

The local server reads the reviewed files already on the operator's machine.

- [x] The Agents view provides copyable stdio commands and client JSON.
- [x] Local calls are read-only and require no hosted service.

Files: backend/airstack/mcp_server.py, docs/MCP.md, docs/ARCHITECTURE.md, web/index.html, web/src/components/record.js
Tests: backend/tests/test_money.py::test_every_mcp_tool_makes_zero_spark_calls; JOURNEY/test_journeys_pages.py::test_j42_anyone_can_run_airstack_locally_from_two_copyable_commands
Journeys: J-34

### J-34 · Run it from my agent
Who: A developer using any stdio MCP client. Test: JOURNEY/test_journeys_pages.py::test_j42_anyone_can_run_airstack_locally_from_two_copyable_commands

## AS-310 · Verify local MCP in agent clients
IN PROGRESS · P1

The stdio protocol is tested; the remaining work is a person checking client-specific setup screens.

- [x] The stdio loop passes initialize, list and call behavior in tests.
- [ ] Connect it in Claude and record the result.
- [ ] Connect it in ChatGPT when local stdio connectors are supported, or document the limitation.

Files: backend/airstack/mcp_server.py, docs/MCP.md

## AS-294 · More local MCP reads
TODO · P2 · user-facing

Add `compare`, `related`, category KPIs and trust when each can reuse the page's published evidence.

- [ ] Each new tool returns stable ids, explicit unknowns, source, quote and read date.
- [ ] Each tool remains local and read-only.

Files: backend/airstack/mcp_server.py, backend/airstack/views.py, docs/MCP.md
