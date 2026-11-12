import json
import os
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
from app.migration.canary import STEPS, advance
from app.validation.reconciliation import reconcile
from app.validation.shadow import Shadow
from backend.auth import credentials_match

CONNECTOR_URL = os.getenv(
    "CONNECTOR_URL",
    "http://localhost:8083/connectors/legacy-trades-connector/status",
)
COLS = "report_id, symbol, quantity, price, notional, fee"

st.set_page_config(page_title="Migration Control Center", page_icon="🛰️", layout="wide")

def render(markup):
    st.markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def load_stylesheet():
    """Load the frontend stylesheet used by the Streamlit dashboard."""
    stylesheet_path = pathlib.Path(__file__).with_name("style.css")
    stylesheet = stylesheet_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{stylesheet}</style>", unsafe_allow_html=True)


load_stylesheet()


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 5


def login_screen():
    with st.container(key="login-page"):
        with st.form("login_form", clear_on_submit=False):
            render(
                "<h1 class='login-title'>Welcome back</h1>"
                "<p class='login-sub'>Sign in to access the migration control dashboard.</p>"
            )
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in")
            render('<p class="login-foot">Authorized team members only.</p>')
            render(
                '<p class="login-contact">Can\'t sign in? '
                '<a href="mailto:support@versatile.com">Contact us</a></p>'
            )

    if submitted:
        if credentials_match(username, password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.stop()


if not st.session_state.authenticated:
    login_screen()


def section(icon, title):
    render(f'<div class="sec"><span class="bar"></span>{icon} {title}</div>')


def kpi(label, value, sub, color):
    render(f'<div class="kpi" style="--c:{color}"><div class="lab">{label}</div>'
           f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')


def hero(allowed, label, subtitle):
    cls = "ok" if allowed else "bad"
    render(f'<div class="hero"><div><h1>🛰️ Migration Control Center</h1><p>{subtitle}</p></div>'
           f'<div class="verdict {cls}">{label}</div></div>')


def node_html(icon, name, status, kind, sub=""):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (f'<div class="node"><div class="ico">{icon}</div><div class="nm">{name}</div>'
            f'<span class="st {kind}">{status}</span>{sub_html}</div>')


def donut(pct, label, good):
    color = "#22c55e" if good else "#f59e0b"
    render(f'<div class="donut" style="background:conic-gradient({color} {pct * 3.6}deg,#1f2937 0)">'
           f'<div class="hole"><b>{pct}%</b><span>{label}</span></div></div>')


def check(label, ok):
    cls = "ok" if ok else "bad"
    mark = "✓" if ok else "✕"
    render(f'<div class="chk {cls}"><span class="dot">{mark}</span>{label}</div>')


def stepper(pct):
    parts = []
    for s in STEPS:
        cls = "done" if s < pct else ("cur" if s == pct else "")
        parts.append(f'<div class="{cls}"><div class="c">{s}%</div></div>')
    render('<div class="stepper">' + '<div class="line"></div>'.join(parts) + '</div>')


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
    target = "Amazon RDS (AWS)" if "amazonaws.com" in CLOUD_DSN else "Docker database"
    subtitle = ("Legacy trade reporting to the cloud with real-time CDC, shadow validation "
                f"and canary rollout. Cloud target: {target}")
    try:
        a = Reader(LEGACY_DSN).all()
        b = Reader(CLOUD_DSN).all()
        slot = slot_info()
    except Exception as exc:
        st.session_state["lag"] = None
        hero(False, "OFFLINE", subtitle)
        st.error(f"Could not read the databases: {exc}")
        st.info("Check the containers with docker compose ps. "
                "If the tables are missing, run python demo.py once.")
        return

    rec = reconcile(snapshot(a), snapshot(b))
    missing, extra, different = len(rec["missing"]), len(rec["extra"]), len(rec["different"])
    state, tasks = connector_status()
    connector_ok = state == "RUNNING" and bool(tasks) and all(t == "RUNNING" for t in tasks)
    slot_ok = bool(slot and slot["active"])
    in_sync = missing == 0 and extra == 0 and different == 0
    st.session_state["lag"] = missing

    shadow = st.session_state.get("shadow")
    shadow_ok = shadow is not None and shadow.cutover_allowed(missing)
    checks = [
        ("Debezium connector and task are RUNNING", connector_ok),
        ("Replication slot is active", slot_ok),
        ("Cloud matches legacy (reconciliation clean)", in_sync),
        ("Shadow validation passed with 0 mismatches", shadow_ok),
    ]
    allowed = all(ok for _, ok in checks)

    hero(allowed, "CUTOVER ALLOWED" if allowed else "CUTOVER BLOCKED", subtitle)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Legacy trades", len(a), "source of truth", "#38bdf8")
    with c2:
        kpi("Cloud trades", len(b), target, "#a78bfa")
    with c3:
        kpi("Missing in cloud", missing, "waiting to be copied" if missing else "nothing waiting",
            "#f59e0b" if missing else "#22c55e")
    with c4:
        kpi("Different rows", different, "values disagree" if different else "all values match",
            "#ef4444" if different else "#22c55e")

    section("🔗", "Data pipeline")
    nodes = [
        node_html("🗄️", "Legacy PostgreSQL", "online", "ok"),
        node_html("📡", "Debezium", state.lower(), "ok" if connector_ok else "bad"),
        node_html("🚌", "Kafka topic", "streaming" if connector_ok else "waiting",
                  "ok" if connector_ok else "warn"),
        node_html("⚙️", "Python consumer", "on demand", "idle"),
        node_html("☁️", "Cloud database", "online", "ok"),
    ]
    render('<div class="pipe">' + '<div class="arrow">➜</div>'.join(nodes) + '</div>')

    section("🧭", "Cutover decision")
    total = len(a)
    pct_sync = 100 if total == 0 else max(0, round(100 * (total - missing) / total))
    if not in_sync:
        pct_sync = min(pct_sync, 99)
    left, right = st.columns([1, 2])
    with left:
        donut(pct_sync, "in sync" if in_sync else "syncing", in_sync)
    with right:
        for label, ok in checks:
            check(label, ok)

    section("📋", "Latest trades")
    tab_legacy, tab_cloud = st.tabs(["Legacy", "Cloud"])
    for tab, data in ((tab_legacy, a), (tab_cloud, b)):
        with tab:
            recent = sorted(data.values(), key=lambda r: r["report_id"], reverse=True)[:10]
            st.dataframe(pd.DataFrame(recent), hide_index=True)


with st.sidebar:
    st.markdown("### Controls")
    st.toggle("Auto-refresh", key="auto_refresh")
    st.selectbox(
        "Refresh interval",
        [5, 10, 30],
        format_func=lambda seconds: f"{seconds} seconds",
        key="refresh_interval",
        disabled=not st.session_state.auto_refresh,
    )
    st.caption("Reads both databases and the Debezium connector. "
               "It never changes your data.")
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True, key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.pop("shadow", None)
        st.rerun()

refresh_interval = st.session_state.refresh_interval if st.session_state.auto_refresh else None
st.fragment(run_every=refresh_interval)(live_panel)()

section("🧪", "Shadow validation")
st.caption("Runs the same requests through the legacy rule and the cloud rule and compares the results.")
col_a, col_b, col_c = st.columns(3)
count = col_a.number_input("Number of comparisons", min_value=10, max_value=500, value=30, step=10)
inject_bug = col_b.checkbox("Inject cloud rounding bug (negative test)")
if col_c.button("Run shadow validation"):
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
    s1, s2, s3 = st.columns(3)
    with s1:
        kpi("Compared", shadow.total, "same requests, both rules", "#38bdf8")
    with s2:
        kpi("Matched", shadow.match, "identical results", "#22c55e")
    with s3:
        kpi("Mismatched", shadow.mismatch, "different results",
            "#ef4444" if shadow.mismatch else "#22c55e")
    rate = shadow.match / shadow.total if shadow.total else 0
    st.progress(rate, text=f"Match rate {rate:.0%}")
    if shadow.reasons:
        st.dataframe(pd.DataFrame({"Mismatch details (first 10)": shadow.reasons[:10]}),
                     hide_index=True)

section("🚦", "Canary rollout")
st.caption("Shows how the real canary gate behaves. It does not change a live router.")
percent = st.session_state.setdefault("pct", 0)
stepper(percent)
btn_a, btn_b, _ = st.columns([1, 1, 2])
if btn_a.button("Advance one step"):
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

st.caption("Local simulation. The shadow validation and canary panels demonstrate the gate logic "
           "and do not control a live router.")