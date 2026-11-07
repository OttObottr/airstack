# spec: AS-020 AS-022 AS-026 AS-027 AS-030 AS-055 AS-062 AS-136 AS-141 AS-206 AS-283 AS-306
from conftest import *
import ast, json, os, pathlib, pytest, random, run_ab, subprocess, sys, textwrap
from airstack import account_guard as ag, paths
from airstack.account_guard import AccountCapReached, AccountGuard
from airstack.budget import BudgetExceeded, BudgetGuard, max_cost
from airstack.mcp_server import McpServer
from airstack.schemas import SchemaError
from airstack.spark import _SYSTEM
from airstack.store import Store
from conftest import Clock
from decimal import Decimal
from types import SimpleNamespace


# --- money ---

def spend(store, clock, amount):
    store._q("INSERT INTO budget_ledger(tool,reserved,spent,state,at) VALUES('x',?,?,'SETTLED',?)", (str(amount), str(amount), clock()))
    store.log_call(role="judge", model="m", effort="", in_tok=0, out_tok=0, cached_tok=0, latency_ms=0, cost=str(amount), request_json="{}",
                   response_json="{}", ts=clock(), tool="x", kind="call", call_ref="c", search_executed=0)

def test_run_over_cap_is_refused_before_the_call_goes_out(store, clock):
    """Each call reserves its MAXIMUM cost first, so the job's committed money can never pass its cap (was: 0.60 allowed under 0.50)."""
    ceiling = max_cost("classify", {"tool": "t"}, _SYSTEM["classify"])
    cap = ceiling * 2 + ceiling / 2                                     # room for two worst-case calls, not three
    spark, fake = make_spark(store, clock, cost=str(ceiling), run_cap=str(cap))   # every call costs its full maximum
    spark.call("classify", {"tool": "t"}, tool="t"); spark.call("classify", {"tool": "t"}, tool="t")
    assert fake.call_count == 2
    with pytest.raises(BudgetExceeded) as e:
        spark.call("classify", {"tool": "t"}, tool="t")
    assert e.value.reason == "job_cap" and fake.call_count == 2
    assert store._committed("WHERE job_id=?", (spark.guard.job_id("t"),)) <= cap

def test_run_cap_refuses_when_the_estimate_alone_would_cross_it(store, clock):
    spark, fake = make_spark(store, clock, run_cap="0.50")
    jid = spark.guard.begin_tool("t")
    store._q("INSERT INTO budget_ledger(tool,reserved,spent,state,at,job_id) VALUES('t','0.499','0.499','SETTLED',?,?)", (clock(), jid))
    with pytest.raises(BudgetExceeded):
        spark.call("judge", {}, tool="t")
    assert fake.call_count == 0

def test_a_day_over_cap_is_refused_and_the_next_day_is_allowed(store, clock):
    spend(store, clock, "9.999")
    spark, fake = make_spark(store, clock, day_cap="10")
    with pytest.raises(BudgetExceeded) as e:
        spark.call("judge", {}, tool="t")
    assert e.value.reason == "day_cap" and fake.call_count == 0
    clock.set("2026-08-02T00:00:01Z")
    spark.call("classify", {"tool": "t"}, tool="t")
    assert fake.call_count == 1

def test_lifetime_cap_stops_spend_below_the_dashboard_limit(store, clock):
    spend(store, clock, "119.999")
    spark, fake = make_spark(store, clock, total_cap="120", day_cap="1000")
    with pytest.raises(BudgetExceeded) as e:
        spark.call("judge", {}, tool="t")
    assert e.value.reason == "total_cap" and fake.call_count == 0

def test_two_workers_cannot_both_spend_the_same_headroom(store, clock):
    from airstack.budget import BudgetGuard
    a, b = BudgetGuard(store, clock, day_cap="0.06"), BudgetGuard(store, clock, day_cap="0.06")
    a.check("t1", "call", Decimal("0.05"))                     # worker A reserves; its call is still in flight
    with pytest.raises(BudgetExceeded) as e:
        b.check("t2", "call", Decimal("0.05"))                 # worker B sees A's open reservation
    assert e.value.reason == "day_cap"

def test_the_run_cap_is_per_tool_job_so_a_batch_of_ten_tools_is_not_stopped_by_it(store, clock):
    ceiling = max_cost("classify", {"tool": "t"}, _SYSTEM["classify"])
    cap = ceiling * 2 + ceiling / 2                                     # room for two worst-case calls in one job, not for twenty in one run
    spark, fake = make_spark(store, clock, cost=str(ceiling), run_cap=str(cap), day_cap="50")
    for i in range(10):
        spark.guard.begin_tool(f"tool{i}")
        spark.call("classify", {"tool": f"tool{i}"}, tool=f"tool{i}"); spark.call("classify", {"tool": f"tool{i}"}, tool=f"tool{i}")
        spark.guard.end_tool(f"tool{i}")
    assert fake.call_count == 20

def test_per_tool_call_cap_is_8(store, clock):
    spark, fake = make_spark(store, clock, cost="0.0001", run_cap="50", day_cap="50")
    for _ in range(8):
        spark.call("classify", {"tool": "t"}, tool="t")
    with pytest.raises(BudgetExceeded) as e:
        spark.call("classify", {"tool": "t"}, tool="t")
    assert e.value.reason == "tool_calls" and fake.call_count == 8
    spark.guard.begin_tool("t")
    spark.call("classify", {"tool": "t"}, tool="t")

def test_per_tool_search_cap_is_4(store, clock):
    spark, fake = make_spark(store, clock, cost="0.0001", run_cap="50", day_cap="50")
    for _ in range(4):
        spark.call("search", {"tool": "t"}, tool="t")
    with pytest.raises(BudgetExceeded) as e:
        spark.call("search", {"tool": "t"}, tool="t")
    assert e.value.reason == "tool_searches" and fake.call_count == 4

def test_every_mcp_tool_makes_zero_spark_calls(store, clock):
    seed_before(store); issue_seats(store); issue_public(store)
    _, fake = make_spark(store, clock)
    review = {"tools": [{"tool": "fireflies", "seat": "A"}, {"tool": "fireflies", "requirements": SEAT_B}]}
    srv = McpServer(store)
    args = {"get_verdict": {"tool": "fireflies"}, "get_evidence": {"tool": "fireflies"}, "changes_since": {"since": "2026-01-01"}, "review_stack": review,
            "get_entity": {"tool": "fireflies"}}
    assert set(args) == set(srv.tool_names)
    for name, a in args.items():
        srv.call_tool(name, a)
    assert fake.call_count == 0

def test_public_read_modules_cannot_even_import_spark():
    base = pathlib.Path(__file__).resolve().parents[1] / "airstack"
    banned = {"spark", "engine", "budget"}
    for name in ("views.py", "mcp_server.py"):
        for node in ast.walk(ast.parse((base / name).read_text())):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for m in mods:
                assert not (set(m.replace(".", " ").split()) & banned), f"{name} imports {m}"

def test_a_failed_or_timed_out_call_is_still_charged(store, clock):
    rec = recordings(); rec["classify"] = TimeoutError("no answer")
    spark, fake = make_spark(store, clock, rec=rec)
    with pytest.raises(TimeoutError):
        spark.call("classify", {"tool": "t"}, tool="t")
    assert store.spent_today(clock()[:10]) > 0 and spark.guard.run_spent > 0

def test_an_offline_memo_miss_reserves_and_records_nothing(store, clock):
    from airstack.corpus import Corpus
    from airstack.spark import FakeSpark, GuardedSpark, ReplayMiss
    corpus = Corpus(store)
    spark = GuardedSpark(FakeSpark({}, replay_only=True), store, BudgetGuard(store, clock), clock, memo=corpus)
    with pytest.raises(ReplayMiss):
        spark.call("classify", {"tool": "missing"}, tool="missing")
    assert store.calls() == [] and store.ledger() == []
    assert store._c.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0

def test_standard_replay_uses_the_paid_memo_without_spend(store, clock):
    from airstack.config import MODEL
    from airstack.corpus import Corpus
    from airstack.spark import FakeSpark, GuardedSpark, memo_key
    corpus, payload = Corpus(store), {"product": "Acme", "page_url": "https://acme.test/pricing", "part": 1, "text": "Acme Free $0"}
    corpus.put(memo_key("pricing", payload, MODEL), {"call_ref": "paid-earlier", "data": {"plans": []}, "model": MODEL})
    fake = FakeSpark({}, model=MODEL, replay_only=True)
    result = GuardedSpark(fake, store, BudgetGuard(store, clock), clock, memo=corpus).call("pricing", payload, tool="acme")
    assert result.call_id == "paid-earlier" and fake.call_count == 0 and store.ledger() == []
    assert len(store.calls()) == 1 and store.calls()[0]["kind"] == "cached" and store.calls()[0]["cost"] == "0"

def test_an_atomic_write_failure_preserves_the_previous_artifact(tmp_path, monkeypatch):
    import airstack.files as files
    out = tmp_path / "pricing.json"; out.write_bytes(b"previous-complete-snapshot")
    monkeypatch.setattr(files.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("interrupted replace")))
    with pytest.raises(OSError):
        files.atomic_write_text(out, "partial-new-snapshot")
    assert out.read_bytes() == b"previous-complete-snapshot" and list(tmp_path.iterdir()) == [out]

def test_oversized_stack_review_is_rejected(store):
    seed_before(store); issue_seats(store)
    srv = McpServer(store)
    assert srv.call_tool("review_stack", {"tools": [{"tool": "fireflies"}] * 25})["results"]
    with pytest.raises(SchemaError):
        srv.call_tool("review_stack", {"tools": [{"tool": "fireflies"}] * 26})

def test_the_real_env_file_is_ignored_and_never_tracked():
    repo = pathlib.Path(__file__).resolve().parents[2]
    if subprocess.run(["git", "-C", str(repo), "rev-parse"], capture_output=True).returncode:
        pytest.skip("not a git checkout")
    assert subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", ".env"]).returncode == 0           # ignored
    assert ".env" not in subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split()   # and not tracked

def test_a_key_in_the_environment_never_reaches_an_mcp_answer_or_a_call_log(store, clock, monkeypatch):
    """Behaviour only: scanning files and history for secrets is the job of the secret scanner (pre-commit hook and CI), not ours."""
    fake_key = "sk-" + "t" * 28
    monkeypatch.setenv("MODEL_API_KEY", fake_key)
    seed_before(store); issue_seats(store)
    outputs = [json.dumps(McpServer(store).call_tool("get_verdict", {"tool": "fireflies"}))]
    spark, _ = make_spark(store, clock); spark.call("classify", {"tool": "t"}, tool="t")
    outputs += [f"{r['role']} {r['request_json']} {r['response_json']}" for r in store.calls()]
    assert all(fake_key not in o for o in outputs)

# ---- regressions from the 2026-11-03 audit of commit f74b394 ----
def test_a_call_that_costs_more_than_its_maximum_pauses_all_paid_work(store, clock):
    spark, fake = make_spark(store, clock, cost="0.12", run_cap="0.10", day_cap="0.10", total_cap="0.10")
    with pytest.raises(BudgetExceeded) as e:
        spark.call("classify", {"tool": "t"}, tool="t")
    assert e.value.reason == "bound_exceeded" and store.paused()
    with pytest.raises(BudgetExceeded) as e:                     # nothing else goes out until a person resumes
        spark.call("classify", {"tool": "t"}, tool="u")
    assert e.value.reason == "paused" and fake.call_count == 1

def test_a_reservation_is_the_worst_case_not_a_guess():
    small, big = max_cost("classify", {"tool": "t"}), max_cost("search", {"tool": "t"})
    assert Decimal("0") < small < big                            # search adds the query allowance
    with pytest.raises(BudgetExceeded) as e:
        max_cost("judge", {"blob": "x" * 50_000})
    assert e.value.reason == "input_too_large"

def test_in_flight_reservations_count_against_the_job_cap(store, clock):
    g = BudgetGuard(store, clock, job_cap="0.06", day_cap="10")
    g.begin_tool("t")
    g.check("t", "call", Decimal("0.05"))                        # still outstanding
    with pytest.raises(BudgetExceeded) as e:
        g.check("t", "call", Decimal("0.05"))
    assert e.value.reason == "job_cap"

def test_an_uncertain_charge_stays_reserved_at_its_maximum(store, clock):
    rec = recordings(); rec["classify"] = TimeoutError("accepted by the provider, then the socket died")
    spark, fake = make_spark(store, clock, rec=rec)
    with pytest.raises(TimeoutError):
        spark.call("classify", {"tool": "t"}, tool="t")
    row = store.ledger()[-1]
    assert row["state"] == "UNCERTAIN" and Decimal(row["reserved"]) == max_cost("classify", {"tool": "t"}, _SYSTEM["classify"])
    assert store.spent_today(clock()[:10]) == Decimal(row["reserved"])
    store.reconcile(row["id"], "0.002")                         # a person checks the provider's usage page
    assert store.spent_today(clock()[:10]) == Decimal("0.002")

def test_duplicate_job_delivery_is_refused(store, clock):
    a, b = BudgetGuard(store, clock), BudgetGuard(store, clock)
    a.begin_tool("fireflies", dedupe_key="reassess:7")
    with pytest.raises(BudgetExceeded) as e:
        b.begin_tool("fireflies", dedupe_key="reassess:7")
    assert e.value.reason == "duplicate_job"
    a.end_tool("fireflies")
    b.begin_tool("fireflies", dedupe_key="reassess:7")          # a closed job can be retried

def test_two_processes_on_one_database_file_share_one_ledger(tmp_path, clock):
    path = str(tmp_path / "db.sqlite")
    s1, s2 = Store(path), Store(path)
    BudgetGuard(s1, clock, day_cap="0.06").check("t1", "call", Decimal("0.05"))
    with pytest.raises(BudgetExceeded) as e:
        BudgetGuard(s2, clock, day_cap="0.06").check("t2", "call", Decimal("0.05"))
    assert e.value.reason == "day_cap"

def test_preflight_prints_settings_never_secrets(monkeypatch, capsys):
     
    import preflight
    monkeypatch.setenv("MODEL_API_KEY", "PLACEHOLDER-never-printed-9876")
    preflight.main(env_file=None)
    out = capsys.readouterr().out
    assert "PLACEHOLDER-never-printed-9876" not in out and "MODEL_API_KEY: present" in out and "account authorization" in out
    assert "committed" not in out and "remaining $" not in out

def test_notifications_get_no_response(store):
    srv = McpServer(store)
    assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["id"] == 1

def test_the_stdio_loop_writes_nothing_for_a_notification(tmp_path):
    import subprocess, sys
    root = pathlib.Path(__file__).resolve().parents[1]
    msgs = '{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    out = subprocess.run([sys.executable, "-m", "airstack.mcp_server", str(tmp_path / "x.db")], input=msgs, capture_output=True, text=True,
                         cwd=root, timeout=30).stdout.strip().splitlines()
    assert len(out) == 1 and json.loads(out[0])["id"] == 2


# --- account_guard: The account-wide ceiling: nothing may ever be billed to the card. Meta has no hard cap, so this is the cap. ---

BACKEND = pathlib.Path(__file__).resolve().parents[1]

class FakeNet:
    """Stands in for the Responses client: records every request that would have left the machine."""
    def __init__(self, *, in_tok=100, out_tok=50, fail=None, data=None):
        self.sent, self.in_tok, self.out_tok, self.fail = [], in_tok, out_tok, fail
        self.data = data or {"label": "minor", "material": False, "rationale": "fake"}
        self.responses = self
    def create(self, **kw):
        self.sent.append(kw)
        if self.fail:
            raise self.fail
        return SimpleNamespace(output=[], usage=SimpleNamespace(input_tokens=self.in_tok, output_tokens=self.out_tok),
                               output_text=json.dumps(self.data), id=f"resp_{len(self.sent)}")

def live(account, net):
    from airstack.spark import LiveSpark
    ls = LiveSpark(api_key="placeholder-not-a-key", account=account)
    ls._client = net
    return ls

CLASSIFY = ("classify", {"tool": "t", "changes": []})

# ---------------- the ceiling itself ----------------
def test_configuration_can_lower_the_ceiling_but_never_raise_it(monkeypatch):
    monkeypatch.setenv("AIRSTACK_HARD_CEILING_USD", "7")
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "7")
    assert ag.account_cap() == Decimal("7")
    for raw in ("1000", "100000"):
        monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", raw)
        assert ag.account_cap() == Decimal("7")
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "5")
    assert ag.account_cap() == Decimal("5")

def test_the_lifetime_budget_setting_can_never_exceed_the_ceiling():
    code = "import os; os.environ['AIRSTACK_HARD_CEILING_USD']='3'; os.environ['TOTAL_BUDGET_USD']='500'; import airstack.config as c; print(c.TOTAL_BUDGET)"
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True).stdout.strip()
    assert Decimal(out) == Decimal("3")

def test_price_environment_can_raise_reservations_but_never_lower_reviewed_floors():
    code = ("import os; os.environ['SPARK_PRICE_IN_PER_MTOK']='0.01'; os.environ['SPARK_PRICE_OUT_PER_MTOK']='0.01'; "
            "os.environ['SPARK_PRICE_PER_SEARCH']='0.00001'; import airstack.config as c; "
            "print(c.PRICE_IN_PER_MTOK, c.PRICE_OUT_PER_MTOK, c.PRICE_PER_SEARCH)")
    low = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True).stdout.split()
    assert list(map(Decimal, low)) == [Decimal("1.25"), Decimal("4.25"), Decimal("0.0025")]
    high = code.replace("'0.01'", "'9'", 2).replace("'0.00001'", "'1'")
    raised = subprocess.run([sys.executable, "-c", high], cwd=BACKEND, capture_output=True, text=True, check=True).stdout.split()
    assert list(map(Decimal, raised)) == [Decimal("9"), Decimal("9"), Decimal("1")]

def test_the_default_ledger_lives_outside_the_repo_so_regenerating_a_database_never_resets_it():
    assert ag.DEFAULT_LEDGER.is_absolute() and BACKEND.parent not in ag.DEFAULT_LEDGER.parents

# ---------------- the ledger ----------------
def test_reservations_stop_at_the_ceiling(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "1.00")
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    for _ in range(4):
        g.reserve("judge", "0.25")
    with pytest.raises(AccountCapReached) as e:
        g.reserve("judge", "0.01")
    assert e.value.reason == "account_cap" and g.committed() == Decimal("1.00")

def test_a_cheaper_actual_cost_still_counts_at_its_full_maximum(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    rid = g.reserve("search", "0.04"); g.settle(rid, "0.001")
    assert g.committed() == Decimal("0.04")                     # over-count is the safe direction

def test_a_reported_cost_above_its_maximum_counts_at_the_reported_cost(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    rid = g.reserve("judge", "0.01"); g.settle(rid, "0.30")
    assert g.committed() == Decimal("0.30")

def test_an_uncertain_call_stays_counted(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    g.uncertain(g.reserve("judge", "0.02"))
    assert g.committed() == Decimal("0.02")

def test_the_ledger_survives_a_restart(tmp_path):
    p = tmp_path / "l.sqlite"
    AccountGuard(p, tmp_path / "STOP").reserve("judge", "0.50")
    assert AccountGuard(p, tmp_path / "STOP").committed() == Decimal("0.50")

def test_two_guards_on_one_file_share_one_total(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "0.10")
    a, b = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"), AccountGuard(tmp_path / "l.sqlite", tmp_path / "S")
    a.reserve("judge", "0.06")
    with pytest.raises(AccountCapReached):
        b.reserve("judge", "0.06")

def test_eight_concurrent_processes_cannot_overspend_together(tmp_path):
    """Eight separate Python processes cannot reserve more than the private ceiling at the same moment."""
    led = tmp_path / "l.sqlite"
    AccountGuard(led, tmp_path / "STOP")                           # create the file first
    worker = textwrap.dedent(f"""
        import sys; 
        from airstack.account_guard import AccountGuard, AccountCapReached
        g = AccountGuard({str(led)!r}, {str(tmp_path / 'STOP')!r})
        try:
            g.reserve("judge", "0.2"); print("OK")
        except AccountCapReached:
            print("REFUSED")""")
    env = {**os.environ, "AIRSTACK_HARD_CEILING_USD": "1", "AIRSTACK_ACCOUNT_CAP_USD": "1"}
    procs = [subprocess.Popen([sys.executable, "-c", worker], stdout=subprocess.PIPE, text=True, env=env) for _ in range(8)]
    results = [p.communicate(timeout=60)[0].strip() for p in procs]
    assert results.count("OK") == 5 and results.count("REFUSED") == 3
    assert AccountGuard(led, tmp_path / "STOP").committed() == Decimal("1")

@pytest.mark.parametrize("seed", range(20))
def test_random_sequences_across_three_guards_never_pass_the_ceiling(tmp_path, monkeypatch, seed):
    """Reservations alone can never pass the ceiling. A reported cost above its maximum (a mispriced call) can,
    but only once: the ledger stops itself, and no later reservation ever succeeds."""
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "3")
    rnd = random.Random(seed)
    gs = [AccountGuard(tmp_path / "l.sqlite", tmp_path / "S") for _ in range(3)]
    overrun_excess, overran = Decimal(0), False
    for _ in range(400):
        g = rnd.choice(gs)
        try:
            maximum = Decimal(rnd.randint(1, 90)) / 1000
            rid = g.reserve("judge", maximum)
        except AccountCapReached:
            continue
        assert not overran, "a reservation succeeded after an overrun"
        r = rnd.random()
        if r < 0.6:
            spent = Decimal(rnd.randint(0, 90)) / 1000 if rnd.random() < 0.05 else maximum * Decimal(rnd.random())
            g.settle(rid, spent)
            if spent > maximum:
                overran, overrun_excess = True, overrun_excess + spent - maximum
        elif r < 0.8:
            g.uncertain(rid)
        assert gs[0].committed() <= Decimal("3") + overrun_excess
    assert gs[0].committed() <= Decimal("3") + overrun_excess

def test_a_stop_file_refuses_everything(tmp_path):
    stop = tmp_path / "STOP"
    g = AccountGuard(tmp_path / "l.sqlite", stop)
    stop.touch()
    with pytest.raises(AccountCapReached) as e:
        g.reserve("classify", "0.001")
    assert e.value.reason == "stopped"

def test_a_recorded_stop_outlives_the_process(tmp_path):
    AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP").stop("test overrun")
    with pytest.raises(AccountCapReached):
        AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP").reserve("classify", "0.001")

def test_the_account_stop_is_a_budget_stop_everywhere():
    assert issubclass(AccountCapReached, BudgetExceeded)

# ---------------- the live client: reserve BEFORE the network ----------------
def test_a_refused_call_never_reaches_the_network(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "0.001")      # smaller than one classify maximum
    net = FakeNet(); ls = live(AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"), net)
    with pytest.raises(AccountCapReached):
        ls.call(*CLASSIFY, tool="t")
    assert net.sent == []

def test_every_call_that_does_go_out_was_reserved_first(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"); net = FakeNet(); ls = live(g, net)
    for _ in range(5):
        ls.call(*CLASSIFY, tool="t")
    rows = g.rows()
    assert len(net.sent) == len(rows) == 5 and all(r[5] == "SETTLED" for r in rows)
    assert g.committed() == 5 * max_cost(*CLASSIFY, _SYSTEM["classify"])

def test_the_live_client_is_capped_even_without_the_per_database_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "0.05")
    net = FakeNet(); ls = live(AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"), net)
    sent = 0
    with pytest.raises(AccountCapReached):
        for _ in range(1000):
            ls.call(*CLASSIFY, tool="t"); sent += 1
    assert sent == len(net.sent) and sent * max_cost(*CLASSIFY, _SYSTEM["classify"]) <= Decimal("0.05")

def test_a_network_error_is_counted_and_re_raised(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"); ls = live(g, FakeNet(fail=TimeoutError("socket died")))
    with pytest.raises(TimeoutError):
        ls.call(*CLASSIFY, tool="t")
    assert g.rows()[-1][5] == "UNCERTAIN" and g.committed() > 0

def test_a_response_with_no_usage_stops_all_live_calls(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"); net = FakeNet(in_tok=0, out_tok=0); ls = live(g, net)
    ls.call(*CLASSIFY, tool="t")
    with pytest.raises(AccountCapReached) as e:
        ls.call(*CLASSIFY, tool="t")
    assert e.value.reason == "stopped" and len(net.sent) == 1

def test_an_overrun_stops_all_live_calls(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"); net = FakeNet(in_tok=5_000_000, out_tok=50); ls = live(g, net)
    ls.call(*CLASSIFY, tool="t")
    with pytest.raises(AccountCapReached):
        ls.call(*CLASSIFY, tool="t")
    assert len(net.sent) == 1

def test_an_oversized_input_is_refused_before_reserving_or_sending(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"); net = FakeNet(); ls = live(g, net)
    with pytest.raises(BudgetExceeded):
        ls.call("judge", {"blob": "x" * 50_000}, tool="t")
    assert net.sent == [] and g.rows() == []

def test_live_research_uses_the_reviewed_model_set(tmp_path):
    from airstack.spark import LiveSpark
    from airstack.config import MODEL, MODEL_PRICES, WONDER_MODEL
    client = LiveSpark(api_key="placeholder-not-a-key", account=AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"))
    roles = ("profile", "catalog", "classify", "judge", "extract", "brief", "pricing", "place")
    assert {client.model_for(role) for role in roles} == {MODEL, WONDER_MODEL}
    assert all(client.model_for(role) in MODEL_PRICES for role in roles)

def test_an_unpriced_model_is_refused_and_memo_keys_include_the_reviewed_model():
    from airstack.budget import max_cost
    from airstack.spark import memo_key
    from airstack.config import MODEL, WONDER_MODEL
    payload = {"product": "X", "page_kind": "home", "page_url": "https://x.example/", "part": 1, "text": "x" * 3000}
    assert memo_key("profile", payload, WONDER_MODEL) != memo_key("profile", payload, MODEL)
    with pytest.raises(BudgetExceeded):
        max_cost("profile", payload, "", "some-unpriced-model")

def test_requests_are_bounded_and_never_retried(tmp_path):
    net = FakeNet(); ls = live(AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"), net)
    ls.call(*CLASSIFY, tool="t")
    kw = net.sent[0]
    assert kw["model"] == "muse-spark-1.3" and kw["max_output_tokens"] == 4096 and "tools" not in kw

def test_the_http_client_sends_one_attempt_with_the_key_only_in_the_header():
    import http.server, threading, urllib.error
    from airstack.spark import _Client
    seen, status = [], [500]
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, self.headers["Authorization"], self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(status[0])
            if status[0] == 302:
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/stolen")
            self.end_headers(); self.wfile.write(b'{"id":"r1","usage":{"input_tokens":3,"output_tokens":4}}')
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = _Client("placeholder-not-a-key", f"http://127.0.0.1:{srv.server_port}/v1")
        with pytest.raises(urllib.error.HTTPError):
            c.responses.create(model="m", input="x")
        assert len(seen) == 1, "a failed request is never retried"
        status[0] = 302
        with pytest.raises(urllib.error.HTTPError):
            c.responses.create(model="m", input="x")
        assert len(seen) == 2 and all(path != "/stolen" for path, _, _ in seen), "a redirect never receives the bearer token"
        status[0] = 200
        r = c.responses.create(model="m", input="x")
        assert (r.id, r.usage.input_tokens, r.usage.output_tokens) == ("r1", 3, 4)
        assert seen[2][0] == "/v1/responses" and seen[2][1] == "Bearer placeholder-not-a-key" and b"placeholder" not in seen[2][2]
    finally:
        srv.shutdown()

def test_end_to_end_a_sync_with_the_live_client_stops_at_the_account_ceiling(store, clock, tmp_path, monkeypatch):
    """The whole engine with a live client on a fake network: the account ceiling holds even with generous per-database caps."""
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "0.02")
    from airstack.budget import BudgetGuard
    from airstack.engine import run_sync
    from airstack.spark import GuardedSpark
    from airstack.connectors.workspace_updates import StaticConnector
    seed_before(store); issue_seats(store)
    net = FakeNet(data={"label": "capability_shock", "material": True, "rationale": "fake"})
    spark = GuardedSpark(live(AccountGuard(tmp_path / "l.sqlite", tmp_path / "S"), net), store,
                         BudgetGuard(store, clock, job_cap="50", day_cap="50", total_cap="50"), clock)
    clock.set(T_EVENT); run_sync(store, [StaticConnector("w", meet_event_obs())], spark, T_EVENT)
    assert len(net.sent) <= 2                                      # two classify maxima fit under $0.02, the next is refused
    assert sum(r["state"] == "SETTLED" and Decimal(r["spent"]) == 0 for r in store.ledger()) >= 1   # refused calls cost nothing locally

# ---------------- a billed answer that cannot be parsed ----------------
class NoJsonNet(FakeNet):
    """The provider answered and reported usage, but the final text is empty (e.g. the output budget ran out during search)."""
    def create(self, **kw):
        self.sent.append(kw)
        return SimpleNamespace(output=[SimpleNamespace(type="web_search_call"), SimpleNamespace(type="reasoning")], output_text="", status="incomplete",
                               incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                               usage=SimpleNamespace(input_tokens=self.in_tok, output_tokens=self.out_tok), id="resp_nojson")

def test_an_answer_that_is_not_json_settles_at_its_real_cost_and_the_diagnostic_holds_no_content(tmp_path):
    from airstack.spark import SparkOutputError
    acct = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    ls = live(acct, NoJsonNet(in_tok=1000, out_tok=2048))
    with pytest.raises(SparkOutputError) as e:
        ls.call("classify", {"tool": "t", "changes": []}, tool="t")
    (row,) = acct.rows()
    assert row[5] == "SETTLED" and Decimal(row[4]) == (Decimal(1000) * Decimal("1.25") + Decimal(2048) * Decimal("4.25")) / 1_000_000
    assert Decimal(row[4]) <= Decimal(row[3]) and not acct.stopped()
    assert "incomplete=max_output_tokens" in str(e.value) and "text_chars=0" in str(e.value) and "web_search_call" in str(e.value)

def test_an_answer_that_is_not_json_and_reports_no_usage_stays_reserved_at_its_maximum(tmp_path):
    from airstack.spark import SparkOutputError
    acct = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    ls = live(acct, NoJsonNet(in_tok=0, out_tok=0))
    with pytest.raises(SparkOutputError):
        ls.call("classify", {"tool": "t", "changes": []}, tool="t")
    (row,) = acct.rows()
    assert row[5] == "UNCERTAIN" and acct.committed() == Decimal(row[3])

def test_the_guarded_client_logs_an_unparseable_answer_and_settles_its_reservation(store, clock, tmp_path):
    from airstack.budget import BudgetGuard
    from airstack.spark import GuardedSpark, SparkOutputError
    acct = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    gs = GuardedSpark(live(acct, NoJsonNet(in_tok=500, out_tok=300)), store, BudgetGuard(store, clock, job_cap="0.50", day_cap="10", total_cap="10"), clock)
    with pytest.raises(SparkOutputError):
        gs.call("classify", {"tool": "t", "changes": []}, tool="t")
    (r,) = store.ledger()
    assert r["state"] == "SETTLED" and Decimal(r["spent"]) < Decimal(r["reserved"]) and not store.paused()
    call = store._c.execute("SELECT call_ref, response_json FROM calls").fetchall()[-1]
    assert call[0] == "resp_nojson" and "unparseable_output" in call[1]

def test_every_request_asks_for_low_reasoning_and_leaves_room_for_the_answer(tmp_path):
    """Meta counts reasoning tokens inside max_output_tokens; 2048 at default effort returned no text. Effort 'none' is a 400, so never send it."""
    from airstack.config import MAX_OUTPUT_TOKENS, REASONING_EFFORT
    net = FakeNet()
    live(AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP"), net).call(*CLASSIFY, tool="t")
    (sent,) = net.sent
    assert sent["reasoning"] == {"effort": "low"} and REASONING_EFFORT != "none"
    assert sent["max_output_tokens"] == MAX_OUTPUT_TOKENS >= 4096

def test_paid_web_search_has_no_live_execution_path(tmp_path):
    net = FakeNet(); account = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP"); ls = live(account, net)
    with pytest.raises(BudgetExceeded) as error:
        ls.call("search", {"tool": "t", "topic": "x", "changes": []}, tool="t")
    with pytest.raises(BudgetExceeded):
        ls.respond("free-form", input="x", tools=[{"type": "web_search"}])
    assert error.value.reason == "search_disabled" and net.sent == [] and account.rows() == []

# ---------------- explicit authorization ----------------
def test_live_research_requires_an_explicit_account_cap(tmp_path, monkeypatch):
    monkeypatch.delenv("AIRSTACK_ACCOUNT_CAP_USD", raising=False)
    net = FakeNet(); account = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP"); ls = live(account, net)
    with pytest.raises(AccountCapReached) as e:
        ls.call(*CLASSIFY, tool="t")
    assert e.value.reason == "account_cap" and "live research is off" in str(e.value)
    with pytest.raises(AccountCapReached):
        ls.respond("ab-run", input="hi")
    assert net.sent == [] and account.committed() == Decimal(0)

@pytest.mark.parametrize("raw", [None, "", "0", "-5", "nan", "inf", "abc", " "])
def test_a_missing_or_malformed_private_ceiling_means_zero(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("AIRSTACK_HARD_CEILING_USD", raising=False)
    else:
        monkeypatch.setenv("AIRSTACK_HARD_CEILING_USD", raw)
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "999")
    assert ag.private_ceiling() == Decimal(0) and ag.account_cap() == Decimal(0)

@pytest.mark.parametrize("raw", ["", "0", "-5", "nan", "inf", "-inf", "abc", " "])
def test_a_missing_negative_or_malformed_cap_means_zero(monkeypatch, raw):
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", raw)
    assert ag.account_cap() == Decimal(0)

def test_an_explicit_zero_job_cap_stays_zero(store, clock):
    from airstack.budget import BudgetGuard
    assert BudgetGuard(store, clock, job_cap=0).job_cap == 0 and BudgetGuard(store, clock, job_cap=0, run_cap=5).job_cap == 0
    assert BudgetGuard(store, clock, job_cap=None, run_cap=5).job_cap == 5

def test_only_the_guarded_live_client_can_reach_the_provider():
    """One door: the provider SDK is imported and called only inside spark.py's LiveSpark, which reserves first (call and respond)."""
    hits = [str(p.relative_to(BACKEND.parent)) for p in BACKEND.rglob("*.py") if "tests" not in p.parts and "responses.create" in p.read_text()]
    assert hits == ["backend/airstack/spark.py"], hits
    src = (BACKEND / "airstack" / "spark.py").read_text()
    for fn in ("def call(self, role, payload, *, tool, kind=None):\n        ", "def respond(self, label, **kw):"):
        body = src[src.rindex(fn, src.index("class LiveSpark")):]
        assert body.index("reserve(") < body.index("responses.create"), fn

def test_nothing_public_can_reach_a_research_provider_or_holds_its_key():
    """The page and its data files never name a provider API host or key: a cache miss cannot buy inference.
    (A company's homepage, such as openai.com in the directory, is a listing, not an endpoint.)"""
    root = BACKEND.parent
    public = [root / "web" / "index.html", *(root / "web" / "src").rglob("*.*"), root / "web" / "public" / "sw.js",
              paths.SITE_DATA, paths.MARKET_DATA, paths.DIRECTORY, paths.PROFILES]
    for f in public:
        text = f.read_text()
        assert not any(w in text for w in ("api.meta.ai", "api.openai.com", "MODEL_API_KEY", "Bearer ")), f.name

def test_the_reserved_maximum_covers_every_input_meta_has_ever_counted_including_symbol_heavy_pages():
    """A page of decorative dots (hive.com) read as 32,334 input tokens for 14,772 characters and tripped the overrun stop.
    The bound is now per UTF-8 byte, so it covers that page and every call recorded in the market corpus."""
    import sqlite3
    from airstack.budget import max_cost
    from airstack.config import MODEL, MODEL_PRICES, MAX_OUTPUT_TOKENS
    from airstack.spark import _SYSTEM
    dots = {"product": "Hive", "page_kind": "home", "page_url": "https://hive.com/", "part": 1, "text": "Hive\n" + ". ·" * 4900}
    rate_in, rate_out = MODEL_PRICES[MODEL]
    seen = (Decimal(32334) * rate_in + Decimal(MAX_OUTPUT_TOKENS) * rate_out) / Decimal(1_000_000)
    assert max_cost("profile", dots, _SYSTEM["profile"], MODEL) > seen
    db = paths.MARKET_DB
    if db.exists():
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for role, model, tin, tout, req in c.execute("SELECT role, model, in_tok, out_tok, request_json FROM calls WHERE kind='call' AND in_tok IS NOT NULL AND request_json IS NOT NULL"):
            if model not in MODEL_PRICES or role not in _SYSTEM:
                continue
            ri, ro = MODEL_PRICES[model]
            real = (Decimal(int(tin)) * ri + Decimal(int(tout)) * ro) / Decimal(1_000_000)
            payload = __import__("json").loads(req)
            if "omitted" in payload or "withheld" in payload:
                continue                                              # the published snapshot drops third-party text: nothing to bound
            try:
                bound = max_cost(role, payload, _SYSTEM[role], model)
            except Exception:
                continue                                              # an envelope the guard refuses today is never sent
            assert bound >= real, (role, model, tin, tout)

def test_a_recorded_stop_holds_until_the_owner_clears_it_with_a_reason_and_a_new_stop_holds_again(tmp_path):
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    g.stop("call 1 reported more than its maximum")
    assert g.stopped()
    with pytest.raises(ValueError):
        g.clear("  ")
    g.clear("owner: bound fixed per byte, resume")
    assert not g.stopped() and g._c.execute("SELECT COUNT(*) FROM stops").fetchone()[0] == 1   # history is kept
    g.stop("another overrun")
    assert g.stopped()

def test_research_that_is_off_stays_off_whatever_the_prices_say_and_a_zero_estimate_is_refused(tmp_path, monkeypatch):
    """R3-001: with the cap at $0, even a call estimated at $0 never reaches dispatch; with a cap, a zero or broken estimate is refused."""
    from airstack.account_guard import AccountCapReached
    g = AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")
    monkeypatch.delenv("AIRSTACK_ACCOUNT_CAP_USD", raising=False)
    for m in ("0", "0.000001"):
        with pytest.raises(AccountCapReached):
            g.reserve("profile", m)
    monkeypatch.setenv("AIRSTACK_ACCOUNT_CAP_USD", "5")
    for m in ("0", "-1", "NaN"):
        with pytest.raises(AccountCapReached):
            g.reserve("profile", m)
    assert g._c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 0
    rid = g.reserve("profile", "0.01"); g.settle(rid, "0.02", "r")             # an overrun settles and stops in one transaction
    assert g.stopped()
    with pytest.raises(AccountCapReached):
        g.reserve("profile", "0.01")


# --- ab: The A/B harness: same agent and question, with and without AirStack; resumable, append-only, every call in the account ledger. ---

def msg(obj):
    return SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text=json.dumps(obj), annotations=[])])

class Net:
    def __init__(self): self.sent = []; self.responses = self
    def create(self, **kw):
        self.sent.append(kw)
        u = SimpleNamespace(input_tokens=300, output_tokens=80)
        asked = any(i.get("type") == "function_call_output" for i in kw["input"] if isinstance(i, dict))
        if kw.get("tools") and not asked:                                    # first "with" call: the agent asks AirStack
            fc = SimpleNamespace(type="function_call", call_id="c1", name="get_verdict", arguments=json.dumps({"tool": "fireflies", "seat": "B"}))
            return SimpleNamespace(output=[fc], output_text="", usage=u, id=f"r{len(self.sent)}")
        action = "KEEP" if any(i.get("type") == "function_call_output" for i in kw["input"] if isinstance(i, dict)) else "RETIRE"
        return SimpleNamespace(output=[msg({"action": action, "reason": "because"})], output_text="", usage=u, id=f"r{len(self.sent)}")

def ab_live(tmp_path, net):
    from airstack.spark import LiveSpark
    ls = LiveSpark(api_key="placeholder-not-a-key", account=AccountGuard(tmp_path / "l.sqlite", tmp_path / "STOP")); ls._client = net
    return ls

def test_three_runs_each_side_saved_verbatim_and_the_with_side_really_reads_airstack(store, clock, tmp_path):
    seed_before(store); issue_seats(store)
    net, out = Net(), tmp_path / "ab.json"
    d = run_ab.main(ab_live(tmp_path, net), store, path=out)
    assert [x["side"] for x in d["runs"]] == ["without"] * 3 + ["with"] * 3
    assert all(not x["tool_calls"] and len(x["calls"]) == 1 for x in d["runs"][:3])
    w = d["runs"][3]
    assert w["tool_calls"][0]["verdict"]["action"] == "KEEP" and w["tool_calls"][0]["evidence_urls"] and len(w["calls"]) == 2
    assert not any("tools" in kw for kw in net.sent[:3])                               # the "without" side has no tool at all
    assert all(kw.get("tool_choice", "auto") == "auto" for kw in net.sent)                 # Meta accepts only "auto"
    assert json.loads(out.read_text()) == d and len(ab_live(tmp_path, net).account.rows()) == 9   # 3 + 3x2 calls, each in the ledger

def test_a_second_run_is_free_and_only_missing_runs_are_made(store, clock, tmp_path):
    seed_before(store); issue_seats(store)
    out = tmp_path / "ab.json"
    run_ab.main(ab_live(tmp_path, Net()), store, path=out)
    data = json.loads(out.read_text()); data["runs"] = data["runs"][:4]; out.write_text(json.dumps(data))   # pretend it stopped after 4
    net = Net()
    d = run_ab.main(ab_live(tmp_path, net), store, path=out)
    assert len(net.sent) == 4 and len(d["runs"]) == 6 and d["runs"][:4] == data["runs"]   # 2 missing "with" runs x 2 calls; nothing redone
    net2 = Net(); run_ab.main(ab_live(tmp_path, net2), store, path=out)
    assert net2.sent == []                                                              # complete: zero calls


# --- reconcile: The reconciliation refuses when we under-count what the provider says was spent, or when request counts drift. ---

def run(tmp_path, left, requests, rows):
    led = tmp_path / "led.sqlite"
    from airstack.account_guard import AccountGuard
    g = AccountGuard(led, tmp_path / "STOP")
    for r, s in rows:
        rid = g.reserve("profile", r); g.settle(rid, s)
    env = {**os.environ, "AIRSTACK_ACCOUNT_LEDGER": str(led), "AIRSTACK_STOP_FILE": str(tmp_path / "STOP"), "HOME": str(tmp_path)}
    return subprocess.run([sys.executable, str(ROOT / "tools" / "reconcile.py"), "--credits-left", left, "--requests", str(requests)], capture_output=True, text=True, env=env)

@pytest.mark.private_data
def test_reconcile_agrees_when_counts_match_and_refuses_when_we_under_count(tmp_path):
    ok = run(tmp_path, "149.95", 2, [("0.04", "0.03"), ("0.04", "0.03")])          # Meta used 0.05, we settled 0.06: we over-count, counts agree
    assert ok.returncode == 0 and "RECONCILED" in ok.stdout, ok.stdout + ok.stderr
    t2 = tmp_path / "b"; t2.mkdir()
    under = run(t2, "149.00", 2, [("0.04", "0.03"), ("0.04", "0.03")])            # Meta used 1.00, we think 0.06: refuse
    assert under.returncode == 1 and "NOT RECONCILED" in under.stdout
    t3 = tmp_path / "c"; t3.mkdir()
    drift = run(t3, "149.95", 9, [("0.04", "0.03"), ("0.04", "0.03")])            # Meta saw 9 requests, we reserved 2: refuse
    assert drift.returncode == 1
    assert (tmp_path / ".airstack" / "reconciliation.log").read_text().count("\n") == 1

def test_a_rounded_request_count_is_checked_as_the_range_it_can_mean():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reconcile", ROOT / "tools" / "reconcile.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.shown("421") == (421, 421) and m.shown("4.8k") == (4750, 4849) and m.shown("12k") == (11500, 12499)


# --- live_smoke: opt-in provider contract check under one $0.10 guard ---

@pytest.mark.live
@pytest.mark.skipif(os.environ.get("AIRSTACK_LIVE_SMOKE") != "1", reason="opt-in: set AIRSTACK_LIVE_SMOKE=1 (real calls, capped at $0.10 total)")
def test_live_smoke_returns_schema_valid_outputs_within_reservations(store):
    import preflight
    preflight.load_env(ROOT / ".env")
    assert os.environ.get("MODEL_API_KEY"), "put MODEL_API_KEY in .env first"
    from airstack.budget import BudgetGuard
    from airstack.spark import GuardedSpark, LiveSpark
    clock = Clock("2026-11-04T00:00:00Z")
    spark = GuardedSpark(LiveSpark(), store, BudgetGuard(store, clock, job_cap="0.10", day_cap="0.10", total_cap="0.10"), clock)
    src = [{"url": "https://support.google.com/meet/answer/14754931",
            "text": "Take notes for me is available in English, French, German, Italian, Japanese, Korean, Portuguese and Spanish.", "fetched_at": "2026-11-04"}]
    spark.call("classify", {"tool": "fireflies", "changes": [{"key": "meet.in_person_notes", "value": True,
                   "url": "https://workspaceupdates.googleblog.com/2026/08/take-notes-with-me-for-in-person-meetings-is-now-available.html", "ts": "2026-08-13T17:50:38Z"}]}, tool="fireflies")
    x = spark.call("extract", {"tool": "meet", "sources": src}, tool="fireflies")
    assert all(f["source_url"] == src[0]["url"] for f in x.data["facts"])          # cites only the supplied source
    j = spark.call("judge", {"tool": "fireflies", "context": "public", "proposed_action": "KEEP", "uncovered": ["Available on iOS"],
                             "requirements": [{"text": "Available on iOS", "status": "fail"}], "entitlements": [],
                             "new_evidence": ["f1"], "evidence": [{"id": "f1", "key": "meet.supported_languages", "value": ["English", "French", "German"],
                             "source_url": src[0]["url"], "published": "", "observed": "2026-11-04", "effective": None}]}, tool="fireflies")
    assert j.data["action"] in ("BUILD", "BUY", "KEEP", "RETIRE") and set(j.data["citations"]) <= {"f1"}
    rows = store.ledger()
    assert len(rows) == 3 and all(r["state"] == "SETTLED" and Decimal(r["spent"]) <= Decimal(r["reserved"]) for r in rows)
    assert sum(Decimal(r["spent"]) for r in rows) <= Decimal("0.10") and not store.paused()
    print(f"\nsmoke: 4 calls, ${sum(Decimal(r['spent']) for r in rows)}, search grounded results {len(grounded)}/{len(s.data['results'])}")
