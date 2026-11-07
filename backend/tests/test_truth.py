# spec: AS-010 AS-012 AS-013 AS-022 AS-030 AS-032 AS-040 AS-044 AS-062 AS-066 AS-070 AS-072 AS-080 AS-102 AS-131 AS-134 AS-206 AS-232
from conftest import *
import json, pathlib, pytest, re, shutil, sqlite3, subprocess, threading
from airstack import paths, views
from airstack.config import FRESH_DAYS
from airstack.connectors.workspace_updates import StaticConnector, WorkspaceUpdatesConnector, window_url
from airstack.engine import Obs, ingest, run_sync
from airstack.evaluate import evaluate
from airstack.mcp_server import McpServer
from airstack.schemas import ROLE_SCHEMAS, SchemaError, TOOL_ARGS, validate
from airstack.spark import _SYSTEM
from airstack.store import AppendOnlyError, EvidenceError, RetireRuleError, Store, add_days, value_hash


# --- truth ---

def setup_world(store, clock, **spark_kw):
    seed_before(store); ids = issue_seats(store); pub = issue_public(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50", **spark_kw)
    return ids, pub, spark, fake

def event_sync(store, clock, spark, obs=None):
    clock.set(T_EVENT)
    return run_sync(store, [StaticConnector("workspace.updates", obs if obs is not None else meet_event_obs())], spark, T_EVENT)

def test_facts_are_append_only(store):
    f = store.append_fact(entity_id="x", metric="m", value=1, source="s", url="https://e.com", source_ts=None, observed_at=T0)
    with pytest.raises(AppendOnlyError): store.update_fact(f.id, value="2")
    with pytest.raises(AppendOnlyError): store.delete_fact(f.id)
    with pytest.raises(sqlite3.DatabaseError): store._q("UPDATE facts SET url='x'")
    with pytest.raises(sqlite3.DatabaseError): store._q("DELETE FROM facts")

def test_verdict_content_is_immutable_and_never_deleted(store, clock):
    seed_before(store); ids = issue_seats(store)
    with pytest.raises(sqlite3.DatabaseError): store._q("UPDATE verdicts SET reason='changed' WHERE id=?", (ids["A"],))
    with pytest.raises(sqlite3.DatabaseError): store._q("DELETE FROM verdicts WHERE id=?", (ids["A"],))

def test_four_clocks_are_kept_apart(store, clock):
    from airstack.connectors.workspace_updates import WorkspaceUpdatesConnector
    import pathlib
    feed = (pathlib.Path(__file__).parent / "fixtures" / "workspace_updates_2026-08.atom").read_text()
    obs = {o.metric: o for o in WorkspaceUpdatesConnector(fetch_text=lambda u: feed).fetch()}
    assert obs["in_person_notes"].source_ts == "2026-08-13T17:50:38Z"                 # publication
    assert obs["in_person_notes_platforms"].effective_at == "2026-08-11T07:00:00Z"   # effective (Android start, PT)
    seed_before(store); issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    clock.set(T_EVENT); run_sync(store, [WorkspaceUpdatesConnector(fetch_text=lambda u: feed)], spark, T_EVENT)
    new = [v for v in store.verdicts("fireflies", "seat:A") if v.status == "CURRENT"][0]
    row = next(e for e in new.evidence if e["key"] == "meet.in_person_notes_platforms")
    assert row["ts"] == "2026-08-13T17:50:38Z" and row["observed_at"] == T_EVENT and row["effective_at"] == "2026-08-11T07:00:00Z"
    assert new.issued_at == T_EVENT                                                  # evaluation

def test_hash_matches_the_hash_the_page_shows():
    assert value_hash("meet.in_person_notes", True)[:8] == "853b960e"
    assert value_hash("meet.in_person_notes", False)[:8] == "20e5f611"

def test_seat_verdicts_before_the_event_are_both_keep(store, clock):
    seed_before(store); ids = issue_seats(store)
    assert {store.get_verdict(i).action for i in ids.values()} == {"KEEP"}

def test_changed_dependency_lapses_the_verdict_BEFORE_any_reevaluation(store, clock):
    seed_before(store); ids = issue_seats(store)
    seen = []
    rec = recordings()
    for role in ("classify", "search", "judge"):                       # whichever role goes first, record the state when it is called
        real = rec[role]
        rec[role] = (lambda real: lambda p: (seen.append({i: store.get_verdict(i).status for i in ids.values()}), real(p) if callable(real) else real)[1])(real)
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    rep = event_sync(store, clock, spark)
    assert set(rep.lapsed) >= set(ids.values())
    assert list(seen[0].values()) == ["LAPSED", "LAPSED"], "every affected verdict must already be LAPSED when Spark is first called"
    assert all(snap[i] != "CURRENT" for snap in seen for i in ids.values()), "an old verdict must never be CURRENT while it is being re-judged"

def test_a_brand_new_capability_fact_lapses_a_verdict_that_never_depended_on_it(store, clock):
    seed_before(store, earlier_state=False); pub = issue_public(store)
    assert "meet.in_person_notes" not in pub.depends_on and store.latest_fact("meet.in_person_notes") is None
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    rep = event_sync(store, clock, spark)
    assert pub.id in rep.lapsed

def test_unrelated_fact_leaves_verdicts_current_and_costs_nothing(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    rep = event_sync(store, clock, spark, [Obs("npm", "weekly_downloads_band", "1M-5M", "npm", "https://registry.npmjs.org/x")])
    assert rep.lapsed == [] and fake.call_count == 0
    assert all(store.get_verdict(i).status == "CURRENT" for i in [*ids.values(), pub.id])

def test_dependency_hash_moves_but_the_condition_does_not_flip_so_it_stays_current(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    rep = event_sync(store, clock, spark, [Obs("meet", "supported_languages", LANGS + ["Dutch"], "google.meet.help", HELP_2)])
    assert "meet.supported_languages" in rep.changed and rep.lapsed == [] and fake.call_count == 0

def test_unchanged_sync_makes_zero_spark_calls_and_confirms_last_verified(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    clock.set("2026-08-02T12:00:00Z")
    rep = run_sync(store, [StaticConnector("all", meet_before_obs())], spark, "2026-08-02T12:00:00Z")
    assert rep.changed == [] and fake.call_count == 0
    assert store.last_polled("meet.supported_languages") == "2026-08-02T12:00:00Z"   # polling coverage is recorded...
    v = store.get_verdict(ids["A"])                                                  # ...but an unchanged poll is not a re-judgement (F4)
    assert v.last_verified_at == T0 and v.fresh_until == add_days(T0, FRESH_DAYS)

def test_failed_recheck_leaves_verdict_lapsed_and_never_bumps_last_verified(store, clock):
    seed_before(store); ids = issue_seats(store)
    rec = recordings(); rec["classify"] = rec["search"] = RuntimeError("network down")
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    rep = event_sync(store, clock, spark)
    for vid in ids.values():
        v = store.get_verdict(vid)
        assert v.status == "LAPSED" and v.last_verified_at == T0 and not store.has_successor(vid)
    assert rep.still_lapsed and not rep.rejudged

def test_failed_connector_never_confirms_a_verdict(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    run_sync(store, [StaticConnector("down", error=OSError("timeout"))], spark, "2026-08-02T12:00:00Z")
    assert store.get_verdict(ids["A"]).last_verified_at == T0

def test_successful_recheck_creates_a_new_verdict_and_supersedes_the_old(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    rep = event_sync(store, clock, spark)
    assert len(rep.rejudged) >= 2
    old_a = store.get_verdict(ids["A"])
    assert old_a.status == "SUPERSEDED" and store.has_successor(old_a.id)
    new_a = [v for v in store.verdicts("fireflies", "seat:A") if v.status == "CURRENT"][0]
    assert new_a.supersedes_id == old_a.id and new_a.last_verified_at == T_EVENT and new_a.counter_checked

def test_weak_evidence_stays_lapsed(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(confidence=0.4), run_cap="50", day_cap="50")
    event_sync(store, clock, spark)
    assert store.get_verdict(ids["A"]).status == "LAPSED" and not store.has_successor(ids["A"])

def test_judge_cannot_overrule_the_evidence(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(judge_action="RETIRE"), run_cap="50", day_cap="50")
    event_sync(store, clock, spark)
    assert store.get_verdict(ids["B"]).status == "LAPSED"                 # evidence says KEEP for seat B; a RETIRE judge is refused

def test_an_ungrounded_search_cannot_publish_a_verdict(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, search_executed=False, run_cap="50", day_cap="50")
    event_sync(store, clock, spark)
    assert store.get_verdict(ids["A"]).status == "LAPSED"

def test_retire_only_when_every_seat_requirement_is_covered(store, clock):
    seed_before(store)
    for o in meet_event_obs():
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts, observed_at=T_EVENT)
    a = evaluate(store, "fireflies", SEAT_A, ENTS["A"]); b = evaluate(store, "fireflies", SEAT_B, ENTS["B"])
    assert a.action == "RETIRE" and a.uncovered == []
    assert b.action == "KEEP" and b.uncovered == [B_GAP]
    with pytest.raises(RetireRuleError):
        store.put_verdict(entity_id="fireflies", context="seat:B", action="RETIRE", reason="r", depends_on={}, expires_when=[], evidence=b.evidence, uncovered=b.uncovered, issued_at=T_EVENT)

def test_an_ios_seat_is_not_told_to_retire_on_the_announcement_day(store, clock):
    seed_before(store)
    for o in meet_event_obs():
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts, observed_at=T_EVENT)
    ios = [r if r["id"] != "platform" else {**r, "text": "Available on your platform (iOS)", "all": [{"key": "meet.in_person_notes_platforms", "op": "includes", "value": "iOS"}]} for r in SEAT_A]
    out = evaluate(store, "fireflies", ios, ["workspace:business_standard"])
    assert out.action == "KEEP" and out.uncovered == ["Available on your platform (iOS)"]

def test_each_requirement_is_pass_fail_or_unknown_and_only_all_pass_retires(store, clock):
    seed_before(store, earlier_state=False)
    ENT = ["workspace:business_standard"]
    assert {g["id"]: g["status"] for g in evaluate(store, "fireflies", SEAT_A).gates}["edition"] == "fail"   # listed edition is not ownership
    before = evaluate(store, "fireflies", SEAT_A, ENT)
    gates = {g["id"]: g["status"] for g in before.gates}
    assert gates["in_person"] == "unknown" and gates["lang_en"] == "pass" and before.action is None   # unknown is not KEEP
    for o in meet_event_obs():
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts, observed_at=T_EVENT)
    ios = [r if r["id"] != "platform" else {**r, "all": [{"key": "meet.in_person_notes_platforms", "op": "includes", "value": "iOS"}]} for r in SEAT_A]
    assert {g["id"]: g["status"] for g in evaluate(store, "fireflies", ios, ENT).gates}["platform"] == "fail"   # the evidence says no
    a = evaluate(store, "fireflies", SEAT_A, ENT)
    assert all(g["status"] == "pass" for g in a.gates) and a.action == "RETIRE"

def test_a_context_free_lookup_is_labelled_as_a_reference_scenario(store, clock):
    seed_before(store); issue_seats(store)
    assert "Reference scenario" in views.get_verdict(store, "fireflies")["scope"]
    assert "scope" not in views.get_verdict(store, "fireflies", "A")

def test_insufficient_evidence_publishes_no_new_verdict(store, clock):
    seed_before(store)
    export = {"id": "crm_export", "text": "Exports notes to the CRM", "all": [{"key": "meet.crm_export", "op": "eq", "value": True}]}
    reqs = SEAT_A + [export]                                     # a job nobody has evidence about either way
    ev = evaluate(store, "fireflies", reqs, ["workspace:business_standard"])
    v = store.put_verdict(entity_id="fireflies", context="seat:C", action=ev.action, reason="seat C", depends_on=ev.depends_on,
                          expires_when=ev.expires_when, evidence=ev.evidence, uncovered=ev.uncovered, issued_at=T0, requirements=reqs,
                          entitlements=["workspace:business_standard"])
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    event_sync(store, clock, spark)
    assert store.get_verdict(v.id).status == "LAPSED" and not store.has_successor(v.id)   # in-person is now covered, CRM export is unknown
    assert fake.call_count == 0                                  # insufficient evidence is decided in code: no Spark call is spent on it

def test_an_answer_built_on_older_inputs_is_never_published_as_current(store, clock):
    seed_before(store); ids = issue_seats(store)
    rec = recordings(); real = rec["judge"]
    def judge_while_a_new_fact_lands(p):
        store.append_fact(entity_id="meet", metric="in_person_notes_platforms", value=["Android", "iOS"], source="workspace.updates", url=POST, source_ts=None, observed_at=T_EVENT)
        return real(p)
    rec["judge"] = judge_while_a_new_fact_lands
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    clock.set(T_EVENT); run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    assert store.get_verdict(ids["B"]).status == "LAPSED" and not store.has_successor(ids["B"])

def test_every_lifecycle_change_is_an_append_only_event(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    event_sync(store, clock, spark)
    assert [e["event"] for e in store.events(ids["A"])] == ["PUBLISHED", "LAPSED", "SUPERSEDED"]
    assert "meet.in_person_notes" in store.events(ids["A"])[1]["cause"]
    with pytest.raises(sqlite3.DatabaseError): store._q("DELETE FROM verdict_events")

def test_seat_a_retires_fireflies_and_seat_b_keeps_it_after_the_event(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    event_sync(store, clock, spark)
    now = {c: [v for v in store.verdicts("fireflies", f"seat:{c}") if v.status == "CURRENT"][0] for c in "AB"}
    assert now["A"].action == "RETIRE" and now["B"].action == "KEEP" and now["B"].uncovered == [B_GAP]

def test_historical_replay_is_labeled_and_returns_the_verdict_as_of_the_date(store, clock):
    ids, pub, spark, fake = setup_world(store, clock)
    event_sync(store, clock, spark)
    before = views.get_verdict(store, "fireflies", "A", as_of="2026-08-05")
    after = views.get_verdict(store, "fireflies", "A", as_of="2026-08-14")
    assert before["replay"] and "Historical replay" in before["label"] and before["verdicts"][0]["action"] == "KEEP"
    assert after["replay"] and after["verdicts"][0]["action"] == "RETIRE"
    assert views.get_verdict(store, "fireflies", "A")["replay"] is False

def test_due_recheck_runs_when_unchanged_inputs_go_stale_and_reissues_on_clean_result(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(results=[]), run_cap="50", day_cap="50")
    late = "2026-08-17T12:00:00Z"; clock.set(late)
    run_sync(store, [StaticConnector("all", meet_before_obs())], spark, late)
    assert fake.call_count == 1                                                     # one public search serves both due seats (no seat context)
    old = store.get_verdict(ids["A"])
    assert old.status == "SUPERSEDED" and old.last_verified_at == T0                  # history is never rewritten
    assert [e["event"] for e in store.events(old.id)] == ["PUBLISHED", "LAPSED", "SUPERSEDED"]   # lapsed FIRST
    new = [v for v in store.verdicts("fireflies", "seat:A") if v.status == "CURRENT"]
    assert len(new) == 1 and new[0].supersedes_id == old.id and new[0].last_verified_at == late

def test_due_recheck_with_counter_evidence_lapses_the_verdict(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    late = "2026-08-17T12:00:00Z"
    rep = run_sync(store, [StaticConnector("all", meet_before_obs())], spark, late)
    assert ids["A"] in rep.lapsed or store.has_successor(ids["A"]) or store.get_verdict(ids["A"]).status != "CURRENT"

def test_a_verdict_without_a_source_url_and_timestamp_is_refused(store):
    with pytest.raises(EvidenceError):
        store.put_verdict(entity_id="x", context="public", action="KEEP", reason="r", depends_on={}, expires_when=[], evidence=[{"kind": "fact", "url": "", "ts": ""}], uncovered=[], issued_at=T0)

def test_a_rules_hold_never_carries_the_old_reason_and_never_claims_a_judge(store, clock):
    """Live finding (run 2): a re-verified KEEP copied its 1 Aug reason ("not yet available") into a 4 Nov verdict, when it was false."""
    seed_before(store); issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(material=False, label="minor"), run_cap="50", day_cap="50")
    event_sync(store, clock, spark)
    b = [v for v in store.verdicts("fireflies", "seat:B") if v.status == "CURRENT"][0]
    assert b.action == "KEEP" and b.reason == f"Re-verified KEEP: still not covered: {B_GAP}." and b.judge_output is None
    assert [r for r, _, _ in fake.calls].count("judge") == 1                       # only seat A (whose rules changed) was judged
    view = views.get_verdict(store, "fireflies", "B")["verdicts"][0]
    assert view["reason"] == b.reason and view["judged_by"]["kind"].startswith("re-verified") and "stored_reason" not in view

# ---- review 5b33e45: C03 / X02 (observation identity) ----
def test_C03_a_date_only_correction_survives_and_counts_as_a_change(store, clock):
    """Review C03: an unchanged value with a corrected effective time used to be dropped, leaving the wrong date in force."""
    rep1, _ = ingest(store, [Obs("meet", "in_person_notes", True, "workspace.updates", POST, "2026-08-13T17:50:38Z", "2026-09-30T00:00:00Z")], T0)
    assert store.latest_fact("meet.in_person_notes").effective_at == "2026-09-30T00:00:00Z"
    rep2, _ = ingest(store, [Obs("meet", "in_person_notes", True, "workspace.updates", POST, "2026-08-13T17:50:38Z", "2026-08-11T07:00:00Z")], T_EVENT)
    assert [f.key for f in rep2] == ["meet.in_person_notes"]                     # a change: applicability moved
    assert store.latest_fact("meet.in_person_notes").effective_at == "2026-08-11T07:00:00Z"
    assert len([f for f in store.facts_for("meet") if f.metric == "in_person_notes"]) == 2   # the old date stays in history
    rep3, _ = ingest(store, [Obs("meet", "in_person_notes", True, "workspace.updates", POST, "2026-08-13T17:50:38Z", None)], T_EVENT)
    assert rep3 == [] and store.latest_fact("meet.in_person_notes").effective_at == "2026-08-11T07:00:00Z"   # "not stated" never erases a known date

def test_X02_an_independent_source_for_the_same_value_is_kept_without_triggering_work(store, clock):
    """Review X02: a corroborating source was discarded, so source counts and disagreement could never be shown."""
    ingest(store, [Obs("meet", "supported_languages", LANGS, "google.meet.help", HELP_2)], T0)
    rep, _ = ingest(store, [Obs("meet", "supported_languages", LANGS, "press.9to5google", "https://9to5google.com/x")], T_EVENT)
    rows = [f for f in store.facts_for("meet") if f.metric == "supported_languages"]
    assert rep == [] and {f.url for f in rows} == {HELP_2, "https://9to5google.com/x"}   # kept, but not a change: no lapse, no model call
    rep, _ = ingest(store, [Obs("meet", "supported_languages", LANGS, "google.meet.help", HELP_2)], T_EVENT)
    assert rep == [] and len([f for f in store.facts_for("meet") if f.metric == "supported_languages"]) == 2   # an unchanged poll adds nothing

# ---- AS-232: a verdict rests only on citable sources ----
@pytest.mark.parametrize("url, held", [("https://javisreview.com/review/fireflies-ai-review-2026/", True),   # commentary
                                       ("https://9to5google.com/2026/08/13/meet-notes/", True),            # the press
                                       ("https://example.com/a", True),                                    # a domain tied to no one
                                       ("https://fireflies.ai/blog/meet", False),                          # the vendor's own site
                                       ("https://support.google.com/meet/answer/1", False)])               # the platform maker's docs
def test_a_judge_that_cites_a_source_outside_the_citable_classes_is_held_and_says_why(store, clock, url, held):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(results=[{"url": url, "title": "t", "snippet": "s", "published": ""}]), run_cap="50", day_cap="50")
    rep = event_sync(store, clock, spark)
    assert any(f.url == url for f in store.facts_since(T0))                          # the search result is kept as a fact either way: only the citation is held
    current = [v for v in store.verdicts("fireflies") if v.status == "CURRENT"]
    if held:
        assert not rep.rejudged and not current and {i for i, _ in rep.still_lapsed} == set(ids.values())
        assert all(why.startswith("held: ") and url.split("/")[2] in why for _, why in rep.still_lapsed)
    else:
        assert len(rep.rejudged) == 2 and len(current) == 2 and not rep.still_lapsed

def test_a_due_recheck_never_reissues_a_verdict_that_rests_on_an_uncitable_source(store, clock):
    """AS-232: a verdict issued before the gate (the demo's verdict 4 cites a review) lapses at its deadline and is not re-issued as it is."""
    from airstack.engine import recheck_due
    from airstack.evaluate import evidence_entry
    seed_before(store)
    review = store.append_fact(entity_id="fireflies", metric="counter.review", value="flags credit limits", source="web_search",
                               url="https://javisreview.com/review/fireflies-ai-review-2026/", source_ts=None, observed_at=T0)
    ev = evaluate(store, "fireflies", SEAT_A, ENTS["A"])
    v = store.put_verdict(entity_id="fireflies", context="seat:A", action=ev.action, reason="Issued.", depends_on=ev.depends_on, expires_when=ev.expires_when,
                          evidence=[*ev.evidence, evidence_entry(review)], uncovered=ev.uncovered, issued_at=T0, requirements=SEAT_A, entitlements=ENTS["A"],
                          visibility="public", judge_output={"action": ev.action, "reason": "r", "confidence": 0.9, "citations": [f"f{review.id}"]})
    spark, fake = make_spark(store, clock, rec=recordings(results=[]), run_cap="50", day_cap="50")
    late = "2026-08-17T12:00:00Z"; clock.set(late)
    kind, why = recheck_due(store, spark, store.get_verdict(v.id), late)
    assert (kind, why) == ("lapsed", f"held: the verdict cites a source that is not citable: f{review.id} (javisreview.com)")
    assert store.get_verdict(v.id).status == "LAPSED" and not store.has_successor(v.id) and fake.call_count == 0

# ---- regressions from the 2026-11-03 audit of commit f74b394 ----
def test_an_expired_verdict_is_never_read_as_current(store, clock):
    seed_before(store); issue_seats(store)
    deadline = add_days(T0, FRESH_DAYS)
    at = lambda now: {v["context"]: v["status"] for v in views.get_verdict(store, "fireflies", now=now)["verdicts"]}
    assert set(at(deadline).values()) == {"CURRENT"}             # at the deadline itself: still current
    assert set(at("2026-11-03T00:00:00Z").values()) == {"OVERDUE"}   # the worker is down; the read still refuses to call it current
    assert set(at("2026-08-05T00:00:00Z").values()) == {"CURRENT"}   # an old date read at an old clock is fine

def test_a_failed_due_recheck_leaves_the_verdict_lapsed(store, clock):
    seed_before(store); ids = issue_seats(store)
    rec = recordings(); rec["search"] = RuntimeError("search down")
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    late = "2026-08-17T12:00:00Z"
    rep = run_sync(store, [StaticConnector("all", meet_before_obs())], spark, late)
    for vid in ids.values():
        v = store.get_verdict(vid)
        assert v.status == "LAPSED" and v.last_verified_at == T0 and not store.has_successor(vid)
    assert rep.failed

def test_daily_unchanged_polls_cannot_postpone_the_recheck_forever(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(results=[]), run_cap="50", day_cap="50")
    for day in range(1, 36):
        now = add_days(T0, day)
        run_sync(store, [StaticConnector("all", meet_before_obs())], spark, now)
        if day <= FRESH_DAYS:
            assert store.get_verdict(ids["A"]).fresh_until == add_days(T0, FRESH_DAYS)   # polls never move the deadline
    assert fake.call_count > 0                                   # the semantic recheck DID happen
    assert store.get_verdict(ids["A"]).status == "SUPERSEDED"

def _lapsed_seat(store):
    seed_before(store); ids = issue_seats(store)
    store.lapse_verdict(ids["B"], T_EVENT, "test")
    v = store.get_verdict(ids["B"])
    fields = dict(entity_id="fireflies", context=v.context, action="KEEP", reason="successor", depends_on=v.depends_on, expires_when=v.expires_when,
                  evidence=v.evidence, uncovered=v.uncovered, issued_at=T_EVENT, requirements=v.requirements, entitlements=v.entitlements, visibility="public")
    return v, fields

def test_stale_inputs_at_the_publication_boundary_publish_nothing(store):
    v, fields = _lapsed_seat(store)
    assert store.publish_successor(v.id, lambda: False, **fields) is None
    assert store.get_verdict(v.id).status == "LAPSED" and not store.has_successor(v.id)

def test_the_same_predecessor_can_have_only_one_successor(store):
    v, fields = _lapsed_seat(store)
    assert store.publish_successor(v.id, lambda: True, **fields) is not None
    assert store.publish_successor(v.id, lambda: True, **fields) is None
    with pytest.raises(sqlite3.IntegrityError):                  # even a raw insert is refused by the database
        store.put_verdict(supersedes_id=v.id, **fields)
    assert len([x for x in store.verdicts("fireflies", "seat:B") if x.status == "CURRENT"]) == 1

def test_two_workers_on_separate_connections_publish_at_most_once(tmp_path):
    path = str(tmp_path / "db.sqlite")
    s1 = Store(path); v, fields = _lapsed_seat(s1)
    s2 = Store(path)
    results, barrier = [], threading.Barrier(2)
    def worker(s):
        barrier.wait()
        try:
            results.append(s.publish_successor(v.id, lambda: True, **fields))
        except sqlite3.OperationalError:                         # "database is locked" is a safe loss
            results.append(None)
    ts = [threading.Thread(target=worker, args=(s,)) for s in (s1, s2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(r is not None for r in results) == 1
    assert len([x for x in Store(path).verdicts("fireflies", "seat:B") if x.status == "CURRENT"]) == 1

def _after_event(store):
    seed_before(store)
    for o in meet_event_obs():
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts,
                          observed_at=T_EVENT, effective_at=o.effective_at)

def test_retire_needs_the_seat_to_hold_the_entitlement(store):
    _after_event(store)
    assert evaluate(store, "fireflies", SEAT_A, ENT, now=T_EVENT).action == "RETIRE"
    no_ent = evaluate(store, "fireflies", SEAT_A, [], now=T_EVENT)
    assert no_ent.action != "RETIRE" and {g["id"]: g["status"] for g in no_ent.gates}["edition"] == "fail"

def test_a_capability_effective_in_the_future_is_not_yet_coverage(store):
    seed_before(store)
    for o in meet_event_obs():
        store.append_fact(entity_id=o.entity_id, metric=o.metric, value=o.value, source=o.source, url=o.url, source_ts=o.source_ts,
                          observed_at=T_EVENT, effective_at="2027-01-01T00:00:00Z" if o.metric == "in_person_notes_platforms" else None)
    ev = evaluate(store, "fireflies", SEAT_A, ENT, now="2026-08-20T00:00:00Z")
    assert ev.action is None and {g["id"]: g["status"] for g in ev.gates}["platform"] == "unknown"

def test_the_public_review_schema_accepts_an_entitlement_requirement():
    req = {"id": "edition", "text": "Seat holds Business Standard", "entitlement": "workspace:business_standard",
           "all": [{"key": "meet.listed_editions", "op": "includes", "value": "Business Standard"}]}
    validate({"tools": [{"tool": "fireflies", "requirements": [req], "entitlements": ENT}]}, TOOL_ARGS["review_stack"])

def test_an_added_uncovered_job_changes_the_outcome(store):
    _after_event(store)
    crm = {"id": "crm", "text": "Exports notes to the CRM", "all": [{"key": "meet.crm_export", "op": "eq", "value": True}]}
    assert evaluate(store, "fireflies", SEAT_A + [crm], ENT, now=T_EVENT).action is None   # unknown job: no actionable advice

def test_keep_is_labelled_a_provisional_hold(store):
    _after_event(store)
    ev = evaluate(store, "fireflies", SEAT_B, ENT, now=T_EVENT)
    assert ev.action == "KEEP" and ev.basis.startswith("provisional hold") and "not separately verified" in ev.basis

def test_the_judge_sees_values_requirements_and_entitlements(store, clock):
    seed_before(store); issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    clock.set(T_EVENT); run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    judge = [p for role, _, p in fake.calls if role == "judge"]
    assert judge
    for p in judge:
        assert p["requirements"] and p["entitlements"] in (ENTS["A"], ENTS["B"])     # the seat's own plan, never a default
        langs = [e for e in p["evidence"] if e["key"] == "meet.supported_languages"]
        assert langs and langs[0]["value"] == LANGS and langs[0]["source_url"]

def test_a_search_result_the_provider_never_returned_is_not_evidence(store, clock):
    seed_before(store); ids = issue_seats(store)
    rec = recordings(results=[{"url": "https://invented.example/not-from-search", "title": "x", "snippet": "y", "published": ""}])
    spark, fake = make_spark(store, clock, rec=rec, grounded=False, run_cap="50", day_cap="50")
    clock.set(T_EVENT); rep = run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    assert not rep.rejudged and all(store.get_verdict(i).status == "LAPSED" for i in ids.values())
    assert not [f for f in store.facts_since("2000-01-01T00:00:00Z") if "invented.example" in f.url]

def test_a_low_confidence_judge_blocks_publication(store, clock):
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, rec=recordings(confidence=0.4), run_cap="50", day_cap="50")
    clock.set(T_EVENT); rep = run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    assert not rep.rejudged and all(store.get_verdict(i).status == "LAPSED" for i in ids.values())


# --- contract ---

def test_validator_rejects_malformed_shapes():
    with pytest.raises(SchemaError): validate({"action": "KILL", "reason": "r", "confidence": 0.9, "citations": ["f1"]}, ROLE_SCHEMAS["judge"])
    with pytest.raises(SchemaError): validate({"action": "KEEP", "reason": "r", "confidence": 2, "citations": ["f1"]}, ROLE_SCHEMAS["judge"])
    with pytest.raises(SchemaError): validate({"action": "KEEP", "reason": "r", "confidence": 0.9, "citations": ["not-an-id"]}, ROLE_SCHEMAS["judge"])
    with pytest.raises(SchemaError): validate({"action": "KEEP", "reason": "r", "confidence": 0.9, "citations": ["f1"], "extra": 1}, ROLE_SCHEMAS["judge"])
    validate({"action": "KEEP", "reason": "r", "confidence": 0.9, "citations": ["f1"]}, ROLE_SCHEMAS["judge"])

def test_a_malformed_spark_response_is_rejected_and_nothing_is_saved(store, clock):
    seed_before(store); ids = issue_seats(store)
    rec = recordings(); rec["judge"] = {"action": "RETIRE", "reason": "", "confidence": 0.9}
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    clock.set(T_EVENT)
    rep = run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    assert not rep.rejudged and all(store.get_verdict(i).status == "LAPSED" for i in ids.values())
    assert [v for v in store.verdicts("fireflies") if v.supersedes_id] == []

def test_every_evidence_row_in_every_api_output_has_a_url_and_a_timestamp(store, clock):
    from airstack import views
    seed_before(store); issue_seats(store); issue_public(store)
    for ctx in ("A", "B"):
        for v in views.get_verdict(store, "fireflies", ctx)["verdicts"]:
            assert v["evidence"] and all(e["url"].startswith("http") and e["ts"] for e in v["evidence"])
    assert all(f["url"].startswith("http") for f in views.get_evidence(store, "fireflies")["facts"])

def _scan_files():
    files = [ROOT / "web" / "index.html", *sorted((ROOT / "web" / "src").rglob("*.*")), paths.SITE_DATA, *sorted((ROOT / "backend" / "airstack").rglob("*.py"))]
    for folder in ("SPECS", "JOURNEY"):
        files += sorted((ROOT / folder).rglob("*.md")) if (ROOT / folder).exists() else []
    return files

def test_the_word_kill_never_appears_in_the_ui_the_specs_or_the_outputs(store, clock):
    from airstack import views
    seed_before(store); issue_seats(store)
    blobs = [p.read_text(errors="ignore") for p in _scan_files()] + [json.dumps(views.get_verdict(store, "fireflies")), json.dumps(views.get_evidence(store, "fireflies"))]
    word = "ki" + "ll"
    assert not [b for b in blobs if re.search(r"\b" + word + r"\b", b, re.I)]

def test_no_dollar_figure_anywhere_except_the_credit_readout(store, clock):
    from airstack import views
    seed_before(store); issue_seats(store)
    pattern = r"\$\s?\d"
    for p in (ROOT / "web" / "index.html", *sorted((ROOT / "web" / "src").rglob("*.*")), paths.SITE_DATA):
        assert not re.search(pattern, p.read_text()), f"dollar figure in {p.name}"
    for out in (views.get_verdict(store, "fireflies"), views.get_evidence(store, "fireflies")):
        assert not re.search(pattern, json.dumps(out))

# ---- regressions from the 2026-11-03 audit of commit f74b394 ----
def _walk(schema, depth=1):
    yield schema, depth
    for sub in (schema.get("properties") or {}).values():
        yield from _walk(sub, depth + 1)
    if isinstance(schema.get("items"), dict):
        yield from _walk(schema["items"], depth + 1)
    for k in ("anyOf",):
        for sub in schema.get(k) or []:
            yield from _walk(sub, depth + 1)

@pytest.mark.parametrize("role", sorted(ROLE_SCHEMAS))
def test_every_role_schema_fits_metas_strict_subset(role):
    """dev.meta.ai/docs/structured-output 'Enforce strict mode': every object lists every property in `required`, sets
    additionalProperties:false; no allOf/oneOf anywhere; root is a plain object; nesting <= 10. Type unions are not documented,
    so none are used (unknown dates are the empty string)."""
    root = ROLE_SCHEMAS[role]
    assert root.get("type") == "object" and not ({"anyOf", "oneOf", "allOf", "enum", "not"} & set(root))
    for node, depth in _walk(root):
        assert depth <= 10
        assert not ({"allOf", "oneOf"} & set(node))
        assert not isinstance(node.get("type"), list), f"{role}: undocumented type union"
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, role
            assert sorted(node.get("required", [])) == sorted(node.get("properties", {})), role

def test_unknown_dates_are_empty_strings_not_invented():
    ok = {"results": [{"url": "https://x.test/a", "title": "t", "snippet": "s", "published": ""}]}
    validate(ok, ROLE_SCHEMAS["search"])
    validate({"facts": [{"metric": "m", "value_json": "1", "source_url": "https://x.test/a", "source_ts": ""}]}, ROLE_SCHEMAS["extract"])
    assert "never a guessed date" in _SYSTEM["search"] and "never a guessed date" in _SYSTEM["extract"]

def test_the_request_sends_only_the_documented_subset_and_the_local_validator_keeps_the_rest():
    from airstack.schemas import strip_for_provider, _UNDOCUMENTED
    for role, schema in ROLE_SCHEMAS.items():
        sent = strip_for_provider(schema)
        def keys(n):
            if isinstance(n, dict):
                yield from n
                for v in n.values():
                    yield from keys(v)
            elif isinstance(n, list):
                for v in n:
                    yield from keys(v)
        assert not (set(keys(sent)) & set(_UNDOCUMENTED)), role
        for node, _ in _walk(sent):                                   # required/additionalProperties are untouched
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and sorted(node["required"]) == sorted(node["properties"])
    with pytest.raises(Exception):                                   # the response is still checked against the FULL schema
        validate({"action": "KEEP", "reason": "", "confidence": 2, "citations": []}, ROLE_SCHEMAS["judge"])


# --- golden_demo: The 3-minute demo, end to end, on fixtures. If this passes, the demo can't surprise you on camera. ---

FEED = pathlib.Path(__file__).parent / "fixtures" / "workspace_updates_2026-08.atom"     # REAL entry recorded from Google's feed

def agent_without(question):
    """Fixture for the cold agent: no tools, so no dated evidence. (The on-camera A/B must be a REAL run.)"""
    return {"answer": "KEEP", "sources": []}

def agent_with(mcp, seat):
    v = mcp.call_tool("get_verdict", {"tool": "fireflies", "seat": seat})["verdicts"][0]
    return {"answer": v["action"], "sources": [e["url"] for e in v["evidence"]], "recheck_if": v["recheck_if"]}

def test_golden_demo_every_screen_state(store, clock):
    screens = []
    seed_before(store); ids = issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="0.50", day_cap="10")
    mcp = McpServer(store, now_fn=clock)

    # 0:15  type "Fireflies": both seats KEEP, CURRENT, with evidence
    r = mcp.call_tool("get_verdict", {"tool": "fireflies"})
    assert {v["context"]: (v["action"], v["status"]) for v in r["verdicts"]} == {"seat:A": ("KEEP", "CURRENT"), "seat:B": ("KEEP", "CURRENT")}
    screens.append("current")

    # 0:45  the real Meet post arrives through the real connector
    conn = WorkspaceUpdatesConnector(fetch_text=lambda url: FEED.read_text())
    obs = conn.fetch()
    assert [(o.entity_id, o.metric, o.value, o.source_ts) for o in obs] == [("meet", "in_person_notes", True, "2026-08-13T17:50:38Z"),
                                                                         ("meet", "in_person_notes_platforms", ["Android"], "2026-08-13T17:50:38Z"),
                                                                         ("meet", "in_person_notes_ios_earliest", "2026-08-31", "2026-08-13T17:50:38Z"),
                                                                         ("meet", "listed_editions", ["Business Standard", "Business Plus", "Enterprise Standard", "Enterprise Plus",
                                                                                                      "Google AI Pro", "Google AI Ultra", "Frontline Plus", "Google AI Pro for Education"], "2026-08-13T17:50:38Z")]
    assert obs[0].url.endswith("take-notes-with-me-for-in-person-meetings-is-now-available.html")
    first = []
    real = fake.recordings["search"]                                   # seat A's rules change its answer, so search is the first call
    fake.recordings["search"] = lambda p: (first.append({i: store.get_verdict(i).status for i in ids.values()}), real)[1]
    clock.set(T_EVENT)
    rep = run_sync(store, [conn], spark, T_EVENT)
    assert first[0] == {ids["A"]: "LAPSED", ids["B"]: "LAPSED"}; screens.append("lapsed")
    assert len(rep.rejudged) == 2 and [r for r, _, _ in fake.calls] == ["search", "judge", "classify", "judge"]; screens.append("rejudged")   # one shared search

    # 1:15  seat split, both re-issued, both cite the dated Google post
    now = {v["context"]: v for v in mcp.call_tool("get_verdict", {"tool": "fireflies"})["verdicts"]}
    assert now["seat:A"]["action"] == "RETIRE" and now["seat:B"]["action"] == "KEEP"
    assert now["seat:B"]["uncovered"] == [B_GAP]
    assert all(v["status"] == "CURRENT" and v["supersedes"] for v in now.values())
    assert all(v["judged_by"]["model"] == "fixture (no model call)" for v in now.values())                     # never claims Muse for a fake call
    a_calls, b_calls = now["seat:A"]["judged_by"]["call_ids"], now["seat:B"]["judged_by"]["call_ids"]
    assert len(a_calls) == 2 and len(b_calls) == 3 and a_calls[0] == b_calls[1]                                  # rules decided A; B asked classify; one search served both
    assert any(e["url"] == obs[0].url and e["ts"] == "2026-08-13T17:50:38Z" for e in now["seat:A"]["evidence"])
    assert any("Business Starter" in x for x in now["seat:B"]["recheck_if"])
    screens.append("split")

    # replay is labeled and reconstructs the earlier revision
    rp = mcp.call_tool("get_verdict", {"tool": "fireflies", "seat": "A", "as_of": "2026-08-05"})
    assert rp["replay"] and rp["label"].startswith("Historical replay") and rp["verdicts"][0]["action"] == "KEEP"

    # 2:00  MCP with vs without; MCP reads cost nothing
    before = fake.call_count
    assert agent_without("Should seat A keep paying for Fireflies?") == {"answer": "KEEP", "sources": []}
    a = agent_with(mcp, "A")
    assert a["answer"] == "RETIRE" and obs[0].url in a["sources"] and agent_with(mcp, "B")["answer"] == "KEEP"
    assert fake.call_count == before; screens.append("mcp")

    # header: Meta credit spent today, from the calls log
    assert float(store.spent_today(clock()[:10])) == pytest.approx(4 * 0.001)   # 4 fixture calls at the fake's cost
    assert screens == ["current", "lapsed", "rejudged", "split", "mcp"]

@pytest.mark.private_data
@pytest.mark.skipif(not shutil.which("node"), reason="node is needed to read site-data.js")
def test_the_pages_demo_data_agrees_with_the_engine():
    js = "global.window={};require(%r);console.log(JSON.stringify(window.AIRSTACK_DATA))" % str(paths.SITE_DATA)
    data = json.loads(subprocess.check_output(["node", "-e", js], text=True))
    export = json.loads(paths.DEMO_EXPORT.read_text())
    assert data["meta"]["dataset_version"] == export["about"]["dataset_version"]          # the page names the DB version it shows
    cur = {v["context"]: v for v in export["verdicts"] if v["status"] == "CURRENT"}
    ex = data["examples"]
    assert ex["fireflies|Business Standard|Android"]["verdictId"] == cur["seat:A"]["id"] and ex["fireflies|Business Starter|Android"]["verdictId"] == cur["seat:B"]["id"]
    A = lambda k, p, d: data["pool"][data["answers"][k][p][d]]
    assert A("fireflies", "Business Standard", "Android")["action"] == cur["seat:A"]["action"].lower() == "retire"
    assert A("fireflies", "Business Starter", "Android")["action"] == cur["seat:B"]["action"].lower() == "keep"
    assert all(a["evaluatedAt"] == data["meta"]["checked_at"] for a in data["pool"])
    calls = {c["call_ref"]: c for c in export["calls"]}
    for k, e in ex.items():                                                                # every receipt counts stored calls, nothing else
        v = cur[e["ctx"]]
        assert e["calls"] == len(v["call_ids"]) and e["tokens"] == sum(calls[c]["in_tok"] + calls[c]["out_tok"] for c in v["call_ids"])
    assert [r["ref"] for r in data["execution"]["rows"]] == [c["call_ref"] for c in export["calls"]]   # the table IS the calls table
    change = data["life"]["steps"][1]["caption"]
    assert change["source"]["date"] == "2026-08-13" and change["at"] == "10:50 AM PT"     # the feed's published time, 17:50:38Z
    assert all(r["state"] == "lapsed" for r in data["life"]["steps"][1]["rows"])            # the change step shows both answers needing a second look

def test_while_lapsed_mcp_never_serves_the_old_verdict_as_current(store, clock):
    """Demo beat: pause while lapsed. An agent asking over MCP must see LAPSED, not yesterday's advice dressed as current."""
    seed_before(store); issue_seats(store)
    rec = recordings(); rec["classify"] = rec["search"] = RuntimeError("re-judging paused for the demo")
    spark, fake = make_spark(store, clock, rec=rec, run_cap="50", day_cap="50")
    clock.set(T_EVENT)
    run_sync(store, [WorkspaceUpdatesConnector(fetch_text=lambda url: FEED.read_text())], spark, T_EVENT)
    mcp = McpServer(store)
    for seat in "AB":
        v = mcp.call_tool("get_verdict", {"tool": "fireflies", "seat": seat})["verdicts"][0]
        assert v["status"] == "LAPSED" and v["last_verified_at"] == T0
    assert all(v["status"] != "CURRENT" for v in mcp.call_tool("get_verdict", {"tool": "fireflies"})["verdicts"])


# --- privacy ---

def test_private_seat_context_is_redacted_in_the_calls_log(store, clock):
    seed_before(store); issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    clock.set(T_EVENT); run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    rows = store.calls()
    assert rows and fake.call_count == len(rows)
    redacted = 0
    for r in rows:
        assert "Business Starter, a listed" not in r["request_json"] and "seat:A" not in r["request_json"] and "seat:B" not in r["request_json"]
        body = json.loads(r["request_json"])
        if body.get("redacted"):
            redacted += 1
        else:
            assert "context" not in body                 # an unredacted call carries public facts only (e.g. classify)
    assert redacted >= 2                                 # judge for each of the two seats; search is public research and carries no seat context

def test_the_connector_can_ask_the_feed_for_a_date_window():
    u = window_url("2026-08-12", "2026-08-15")
    assert "published-min=2026-08-12T00:00:00-07:00" in u and "published-max=2026-08-15T00:00:00-07:00" in u and "alt=atom" in u

# ---- regressions from the 2026-11-03 audit of commit f74b394 ----
def _private_canary(store):
    seed_before(store)
    ev = evaluate(store, "fireflies", SEAT_B, ENT)
    return store.put_verdict(entity_id="fireflies", context="seat:private_tenant_b", action=ev.action, reason="CANARY-private-reason",
                             depends_on=ev.depends_on, expires_when=ev.expires_when, evidence=ev.evidence, uncovered=ev.uncovered,
                             issued_at=T0, requirements=SEAT_B, entitlements=ENT)          # default visibility: private

def test_context_free_mcp_calls_never_enumerate_private_seats(store, clock):
    _private_canary(store)
    mcp = McpServer(store, now_fn=clock)
    for name, a in (("get_verdict", {"tool": "fireflies"}), ("get_verdict", {"tool": "fireflies", "seat": "private_tenant_b"}),
                    ("changes_since", {"since": "2026-01-01"})):
        assert "CANARY" not in json.dumps(mcp.call_tool(name, a))

def test_reassessment_search_carries_no_seat_context(store, clock):
    seed_before(store); issue_seats(store)
    spark, fake = make_spark(store, clock, run_cap="50", day_cap="50")
    clock.set(T_EVENT); run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    searches = [p for role, _, p in fake.calls if role == "search"]
    assert searches and all("context" not in p and "requirements" not in p for p in searches)
