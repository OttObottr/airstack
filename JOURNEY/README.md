# Journeys

Each journey is something a real person does on airstack.bot, automated in a real browser (Chrome via Playwright) by `JOURNEY/test_journeys*.py` (shared fixtures in `conftest.py`, helpers in `journey_kit.py`). A journey passes only if every "you should see" line is true.

The steps of each journey live inside the ticket they prove, as a `### J-nn` section in `SPECS/*.md` (find one with `grep -n "### J-02" SPECS/*.md`). Every user-facing DONE ticket cites at least one journey, and the spec audit fails if a journey cites a test that does not exist.

Run them: `.venv/bin/pytest -q JOURNEY`
