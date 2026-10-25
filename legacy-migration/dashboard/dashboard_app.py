import json
import pathlib
import sys
import urllib.error
import urllib.request
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import psycopg
import streamlit as st
from psycopg.rows import dict_row

from app.common import calc
from app.config import CLOUD_DSN, LEGACY_DSN
from app.migration.canary import advance
from app.validation.reconciliation import reconcile
from app.validation.shadow import Shadow

CONNECTOR_URL = "http://localhost:8083/connectors/legacy-trades-connector/status"
COLS = "report_id, symbol, quantity, price, notional, fee"

st.set_page_config(page_title="Migration Dashboard", layout="wide")


def run_query(dsn, sql):
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True) as conn:
        return conn.execute(sql).fetchall()


class Reader:
    """Read-only view of a trades table (never creates, clears or changes data)."""

    def __init__(self, dsn):
        self.dsn = dsn

    def all(self):
        rows = run_query(self.dsn, f"SELECT {COLS} FROM trades")
        return {r["report_id"]: r for r in rows}


def snapshot(data):
    return SimpleNamespace(all=lambda: data)


def connector_status():
    try:
        with urllib.request.urlopen(CONNECTOR_URL, timeout=3) as resp:
            info = json.load(resp)
        return info["connector"]["state"], [t["state"] for t in info.get("tasks", [])]
    except urllib.error.HTTPError as exc:
        return ("NOT REGISTERED" if exc.code == 404 else "ERROR"), []
    except Exception:
        return "UNREACHABLE", []


def slot_info():
    rows = run_query(
        LEGACY_DSN,
        "SELECT active, "
        "pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)::bigint AS lag_bytes "
        "FROM pg_replication_slots WHERE slot_name = 'legacy_slot'")
    return rows[0] if rows else None


class SimulatedSystem:
    """Same fee rule as the project. bug=True mimics the cloud rounding bug."""

    def __init__(self, bug=False):
        self.bug = bug

    def compute(self, symbol, quantity, price):
        return calc(quantity, price, self.bug)


def live_panel():
    try:
        a = Reader(LEGACY_DSN).all()
        b = Reader(CLOUD_DSN).all()
        slot = slot_info()
    except Exception as exc:
        st.session_state["lag"] = None
        st.error(f"Could not read the databases: {exc}")
        st.info("Check the containers with: docker compose ps. "
                "If the tables are missing, run python demo.py once.")
        return

    rec = reconcile(snapshot(a), snapshot(b))
    missing, extra, different = len(rec["missing"]), len(rec["extra"]), len(rec["different"])
    state, tasks = connector_status()
    connector_ok = state == "RUNNING" and bool(tasks) and all(t == "RUNNING" for t in tasks)
    slot_ok = bool(slot and slot["active"])
    in_sync = missing == 0 and extra == 0 and different == 0
    st.session_state["lag"] = missing

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Legacy trades", len(a))
    m2.metric("Cloud trades", len(b))
    m3.metric("Missing in cloud", missing)
    m4.metric("Different rows", different)

    m5, m6, m7 = st.columns(3)
    m5.metric("Debezium connector", state)
    m6.metric("Replication slot",
              "active" if slot_ok else ("inactive" if slot else "not found"))
    lag_bytes = slot["lag_bytes"] if slot and slot["lag_bytes"] is not None else "n/a"
    m7.metric("WAL lag (bytes)", lag_bytes)

    st.bar_chart(pd.DataFrame({"trades": [len(a), len(b)]}, index=["Legacy", "Cloud"]))
    if in_sync:
        st.success("Cloud matches legacy: nothing missing, extra or different.")
    else:
        st.warning(f"Cloud differs from legacy: {missing} missing, "
                   f"{extra} extra, {different} different.")

    shadow = st.session_state.get("shadow")
    shadow_ok = shadow is not None and shadow.cutover_allowed(missing)
    st.subheader("Cutover decision")
    checks = [
        ("Debezium connector and task RUNNING", connector_ok),
        ("Replication slot active", slot_ok),
        ("Cloud matches legacy (reconciliation clean)", in_sync),
        ("Shadow validation run with 0 mismatches", shadow_ok),
    ]
    for label, ok in checks:
        st.write(("PASS  " if ok else "FAIL  ") + label)
    if all(ok for _, ok in checks):
        st.success("CUTOVER ALLOWED")
    else:
        st.error("CUTOVER BLOCKED")

    left, right = st.columns(2)
    for col, name, data in ((left, "Legacy", a), (right, "Cloud", b)):
        col.caption(f"Latest {name} trades")
        recent = sorted(data.values(), key=lambda r: r["report_id"], reverse=True)[:10]
        col.dataframe(pd.DataFrame(recent), hide_index=True)


st.title("Migration Dashboard")
st.caption("Legacy PostgreSQL to cloud PostgreSQL through Debezium and Kafka. "
           "Local simulation.")

auto = st.sidebar.toggle("Auto-refresh every 5 seconds", value=False)
st.sidebar.button("Refresh now")

st.header("1. Live status")
st.fragment(run_every=5 if auto else None)(live_panel)()

st.header("2. Shadow validation")
st.caption("Runs the same requests through the legacy rule and the cloud rule "
           "and compares the results.")
col_a, col_b = st.columns(2)
count = col_a.number_input("Number of comparisons", min_value=10, max_value=500,
                           value=30, step=10)
inject_bug = col_b.checkbox("Inject cloud rounding bug (negative test)")
if st.button("Run shadow validation"):
    result = Shadow()
    for qty in range(100, 100 + int(count)):
        result.compare(SimulatedSystem(), SimulatedSystem(inject_bug),
                       dict(symbol="ABC", quantity=qty, price="25.50"))
    st.session_state["shadow"] = result
    st.rerun()

shadow = st.session_state.get("shadow")
if shadow is None:
    st.info("Shadow validation has not been run yet.")
else:
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Compared", shadow.total)
    s2.metric("Matched", shadow.match)
    s3.metric("Mismatched", shadow.mismatch)
    s4.metric("Errors", shadow.errors)
    if shadow.reasons:
        st.dataframe(pd.DataFrame({"Mismatch details (first 10)": shadow.reasons[:10]}),
                     hide_index=True)

st.header("3. Canary rollout (gate demo)")
st.caption("Shows how the real canary gate behaves. It does not change a live router.")
percent = st.session_state.setdefault("pct", 0)
st.progress(percent / 100, text=f"Traffic to cloud: {percent}%")
btn_a, btn_b = st.columns(2)
if btn_a.button("Advance one step (0, 5, 25, 50, 100)"):
    lag = st.session_state.get("lag")
    if lag is None:
        st.warning("Live data is unavailable, so the gate stays closed.")
    else:
        router = SimpleNamespace(percent=percent)
        if advance(router, st.session_state.get("shadow") or Shadow(), lag):
            st.session_state["pct"] = router.percent
            st.rerun()
        else:
            st.warning("Blocked: the gates are not met. See the cutover decision above.")
if btn_b.button("Roll back to 0%"):
    st.session_state["pct"] = 0
    st.rerun()