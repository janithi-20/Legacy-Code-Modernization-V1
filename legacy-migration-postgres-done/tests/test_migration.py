from app.common import calc
from app.legacy.service import Legacy
from app.cloud.service import Cloud
from app.cdc.consumer import run_cdc
from app.validation.shadow import Shadow
from app.validation.reconciliation import reconcile
from app.router.routing import Router
from app.migration.canary import advance
from app.migration.rollback import rollback

def make(bug=False):
    return Legacy(), Cloud(bug=bug)

def test_fee_rounding():
    assert calc(100, "25.50") == ("2550.00", "1.28")

def test_trade_saved_in_legacy():
    l, _ = make()
    l.submit("T1", "ABC", 100, "25.50")
    assert l.all()["T1"]["fee"] == "1.28"

def test_cdc_replicates_and_reconciles():
    l, c = make()
    for i in range(5):
        l.submit(f"T{i}", "ABC", 10, "1.00")
    assert run_cdc(l, c) == 0
    assert reconcile(l, c) == dict(missing=[], extra=[], different=[])

def test_duplicate_events_ignored():
    l, c = make()
    l.submit("T1", "ABC", 100, "25.50")
    seq, row = l.changes_after(0)[0]
    assert c.apply(seq, row) and not c.apply(seq, row)
    assert len(c.all()) == 1

def test_out_of_order_events():
    l, c = make()
    l.submit("T1", "ABC", 100, "25.50")
    l.submit("T1", "ABC", 200, "25.50")
    for seq, row in reversed(l.changes_after(0)):
        c.apply(seq, row)
    assert c.all()["T1"]["quantity"] == 200

def test_consumer_resumes():
    l, c = make()
    for i in range(10):
        l.submit(f"T{i}", "ABC", 10, "1.00")
    assert run_cdc(l, c, limit=4) == 6
    assert run_cdc(l, c) == 0

def test_missing_record_detected():
    l, c = make()
    l.submit("T1", "ABC", 1, "1.00")
    assert reconcile(l, c)["missing"] == ["T1"]

def test_bug_blocks_cutover():
    l, c = make(bug=True)
    s = Shadow()
    s.compare(l, c, dict(symbol="ABC", quantity=100, price="25.50"))
    assert s.mismatch == 1 and not s.cutover_allowed(0)

def test_canary_deterministic_and_gated():
    l, c = make()
    r, s = Router(l, c), Shadow()
    assert not advance(r, s, 0)               # no evidence yet -> blocked
    s.compare(l, c, dict(symbol="ABC", quantity=100, price="25.50"))
    assert advance(r, s, 0) and r.percent == 5
    assert r.route("TRD-1") == r.route("TRD-1")
    assert not advance(r, s, 3)               # replication lag -> blocked

def test_cloud_outage_and_rollback_keep_all_trades():
    l, c = make()
    r = Router(l, c)
    r.percent = 100
    for i in range(3):
        r.submit(f"C{i}", "ABC", 10, "1.00")  # accepted by cloud only
    c.healthy = False
    assert r.submit("L1", "ABC", 10, "1.00")[0] == "legacy"   # fallback
    rollback(r, l, c)
    run_cdc(l, c)
    assert len(l.all()) == 4
    assert reconcile(l, c) == dict(missing=[], extra=[], different=[])
