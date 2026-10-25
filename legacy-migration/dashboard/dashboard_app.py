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
    """Read-only view of a trades table."""

    def __init__(self, dsn):
        self.dsn = dsn

    def all(self):
        rows = run_query(self.dsn, f"SELECT {COLS} FROM trades")
        return {row["report_id"]: row for row in rows}


def snapshot(data):
    return SimpleNamespace(all=lambda: data)


def connector_status():
    try:
        with urllib.request.urlopen(CONNECTOR_URL, timeout=3) as response:
            info = json.load(response)
        connector = info.get("connector", {})
        tasks = info.get("tasks", [])
        task_states = [
            task.get("state", "UNKNOWN")
            for task in tasks
            if isinstance(task, dict)
        ]
        return connector.get("state", "UNKNOWN"), task_states
    except urllib.error.HTTPError as exc:
        return ("NOT REGISTERED" if exc.code == 404 else "ERROR"), []
    except (OSError, ValueError, KeyError):
        return "UNREACHABLE", []


def slot_info():
    rows = run_query(
        LEGACY_DSN,
        "SELECT active, "
        "pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)::bigint AS lag_bytes "
        "FROM pg_replication_slots WHERE slot_name = 'legacy_slot'",
    )
    return rows[0] if rows else None


class SimulatedSystem:
    """Apply the project fee rule, optionally reproducing the cloud bug."""

    def __init__(self, bug=False):
        self.bug = bug

    def compute(self, symbol, quantity, price):
        return calc(quantity, price, self.bug)


def live_panel():
    try:
        legacy = Reader(LEGACY_DSN).all()
        cloud = Reader(CLOUD_DSN).all()
        slot = slot_info()
    except (OSError, psycopg.Error) as exc:
        st.session_state["lag"] = None
        st.error(f"Could not read the databases: {exc}")
        st.info(
            "Check the containers with: docker compose ps. "
            "If the tables are missing, run python demo.py once."
        )
        return

    reconciliation = reconcile(snapshot(legacy), snapshot(cloud))
    missing = len(reconciliation["missing"])
    extra = len(reconciliation["extra"])
    different = len(reconciliation["different"])
    connector, tasks = connector_status()
    connector_ok = (
        connector == "RUNNING"
        and bool(tasks)
        and all(task == "RUNNING" for task in tasks)
    )
    slot_ok = bool(slot and slot["active"])
    in_sync = missing == 0 and extra == 0 and different == 0
    st.session_state["lag"] = missing

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Legacy trades", len(legacy))
    m2.metric("Cloud trades", len(cloud))
    m3.metric("Missing in cloud", missing)
    m4.metric("Different rows", different)

    m5, m6, m7 = st.columns(3)
    m5.metric("Debezium connector", connector)
    m6.metric(
        "Replication slot",
        "active" if slot_ok else ("inactive" if slot else "not found"),
    )
    lag_bytes = slot["lag_bytes"] if slot and slot["lag_bytes"] is not None else "n/a"
    m7.metric("WAL lag (bytes)", lag_bytes)

    st.bar_chart(
        pd.DataFrame({"trades": [len(legacy), len(cloud)]}, index=["Legacy", "Cloud"])
    )
    if in_sync:
        st.success("Cloud matches legacy: nothing missing, extra or different.")
    else:
        st.warning(
            f"Cloud differs from legacy: {missing} missing, "
            f"{extra} extra, {different} different."
        )

    shadow = st.session_state.get("shadow")
    shadow_ok = shadow is not None and shadow.cutover_allowed(missing)
    st.subheader("Cutover decision")
    checks = [
        ("Debezium connector and task RUNNING", connector_ok),
        ("Replication slot active", slot_ok),
        ("Cloud matches legacy (reconciliation clean)", in_sync),
        ("Shadow validation run with 0 mismatches", shadow_ok),
    ]
    for label, passed in checks:
        st.write(("PASS  " if passed else "FAIL  ") + label)
    if all(passed for _, passed in checks):
        st.success("CUTOVER ALLOWED")
    else:
        st.error("CUTOVER BLOCKED")

    left, right = st.columns(2)
    for column, name, data in (
        (left, "Legacy", legacy),
        (right, "Cloud", cloud),
    ):
        column.caption(f"Latest {name} trades")
        recent = sorted(data.values(), key=lambda row: row["report_id"], reverse=True)[:10]
        column.dataframe(pd.DataFrame(recent), hide_index=True)


st.title("Migration Dashboard")
st.caption(
    "Legacy PostgreSQL to cloud PostgreSQL through Debezium and Kafka. "
    "Local simulation."
)

auto_refresh = st.sidebar.toggle("Auto-refresh every 5 seconds", value=False)
st.sidebar.button("Refresh now")

st.header("1. Live status")
if hasattr(st, "fragment"):
    st.fragment(run_every=5 if auto_refresh else None)(live_panel)()
else:
    live_panel()

st.header("2. Shadow validation")
st.caption(
    "Runs the same requests through the legacy rule and the cloud rule "
    "and compares the results."
)
col_a, col_b = st.columns(2)
count = col_a.number_input(
    "Number of comparisons", min_value=10, max_value=500, value=30, step=10
)
inject_bug = col_b.checkbox("Inject cloud rounding bug (negative test)")
if st.button("Run shadow validation"):
    result = Shadow()
    for quantity in range(100, 100 + int(count)):
        request = dict(symbol="ABC", quantity=quantity, price="25.50")
        result.compare(
            SimulatedSystem(),
            SimulatedSystem(inject_bug),
            request,
        )
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
        st.dataframe(
            pd.DataFrame({"Mismatch details (first 10)": shadow.reasons[:10]}),
            hide_index=True,
        )

st.header("3. Canary rollout (gate demo)")
st.caption("Shows how the real canary gate behaves. It does not change a live router.")
percent = st.session_state.setdefault("pct", 0)
st.progress(percent / 100, text=f"Traffic to cloud: {percent}%")
advance_button, rollback_button = st.columns(2)
if advance_button.button("Advance one step (0, 5, 25, 50, 100)"):
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
if rollback_button.button("Roll back to 0%"):
    st.session_state["pct"] = 0
    st.rerun()
