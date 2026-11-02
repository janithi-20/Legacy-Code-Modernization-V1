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
from app.migration.canary import STEPS, advance
from app.validation.reconciliation import reconcile
from app.validation.shadow import Shadow
from backend.auth import credentials_match

CONNECTOR_URL = "http://localhost:8083/connectors/legacy-trades-connector/status"
COLS = "report_id, symbol, quantity, price, notional, fee"

st.set_page_config(page_title="Migration Control Center", page_icon="🛰️", layout="wide")

CSS = """
<style>
.block-container{padding-top:1.5rem;max-width:1250px}
header[data-testid="stHeader"]{background:transparent}
#MainMenu,footer{visibility:hidden}
.hero{background:linear-gradient(120deg,#0f172a 0%,#1e3a8a 55%,#6d28d9 100%);border-radius:20px;
padding:28px 34px;color:#fff;display:flex;justify-content:space-between;align-items:center;gap:20px;
box-shadow:0 10px 40px rgba(79,70,229,.35);margin-bottom:22px}
.hero h1{margin:0;font-size:2rem;font-weight:800;letter-spacing:.3px;color:#fff}
.hero p{margin:6px 0 0;opacity:.85;font-size:.95rem;max-width:640px}
.verdict{padding:14px 26px;border-radius:999px;font-weight:800;letter-spacing:1.5px;font-size:1.05rem;white-space:nowrap;color:#fff}
.verdict.ok{background:#16a34a;box-shadow:0 0 0 6px rgba(34,197,94,.25)}
.verdict.bad{background:#dc2626;box-shadow:0 0 0 6px rgba(239,68,68,.25)}
.sec{font-size:1.15rem;font-weight:700;margin:28px 0 12px;color:#e2e8f0;display:flex;align-items:center;gap:10px}
.sec .bar{width:5px;height:22px;border-radius:3px;background:linear-gradient(#38bdf8,#a78bfa)}
.kpi{background:linear-gradient(145deg,#111827,#1f2937);border:1px solid #334155;border-radius:16px;
padding:18px 20px 16px 24px;position:relative;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.3)}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--c)}
.kpi .lab{color:#94a3b8;font-size:.78rem;text-transform:uppercase;letter-spacing:1.2px}
.kpi .val{font-size:2.3rem;font-weight:800;color:#f8fafc;line-height:1.15}
.kpi .sub{color:#64748b;font-size:.78rem}
.pipe{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap}
.node{flex:1;min-width:150px;background:#0f172a;border:1px solid #334155;border-radius:16px;padding:16px 10px;text-align:center}
.node .ico{font-size:1.8rem}
.node .nm{font-weight:700;color:#f1f5f9;margin-top:4px}
.node .st{font-size:.76rem;margin-top:8px;display:inline-block;padding:3px 12px;border-radius:999px;font-weight:700}
.node .sub{color:#64748b;font-size:.74rem;margin-top:8px}
.st.ok{background:rgba(34,197,94,.15);color:#4ade80}
.st.bad{background:rgba(239,68,68,.15);color:#f87171}
.st.warn{background:rgba(245,158,11,.15);color:#fbbf24}
.st.idle{background:rgba(148,163,184,.15);color:#cbd5e1}
.arrow{align-self:center;font-size:1.5rem;color:#38bdf8}
.donut{width:170px;height:170px;border-radius:50%;display:grid;place-items:center;margin:6px auto}
.hole{width:126px;height:126px;border-radius:50%;background:#0b1020;display:flex;flex-direction:column;align-items:center;justify-content:center}
.hole b{font-size:2rem;color:#f8fafc}
.hole span{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px}
.chk{display:flex;align-items:center;gap:12px;padding:11px 16px;margin-bottom:8px;border-radius:12px;
background:#0f172a;border:1px solid #334155;color:#e2e8f0;font-weight:600}
.chk .dot{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:.9rem;font-weight:800;color:#fff}
.chk.ok{border-color:rgba(34,197,94,.5)}
.chk.ok .dot{background:#16a34a}
.chk.bad{border-color:rgba(239,68,68,.5)}
.chk.bad .dot{background:#dc2626}
.stepper{display:flex;align-items:center;margin:8px 0 14px}
.stepper .c{width:66px;height:66px;border-radius:50%;display:grid;place-items:center;font-weight:800;
border:2px solid #334155;color:#94a3b8;background:#0f172a}
.stepper .done .c{background:#16a34a;border-color:#16a34a;color:#fff}
.stepper .cur .c{background:linear-gradient(135deg,#6366f1,#a855f7);border-color:#a78bfa;color:#fff;box-shadow:0 0 0 6px rgba(139,92,246,.25)}
.stepper .line{flex:1;height:3px;background:#334155;margin:0 6px}
.stButton>button,div[data-testid="stButton"]>button{border-radius:12px;font-weight:700;border:0;
background:linear-gradient(135deg,#6366f1,#a855f7);color:#fff;padding:.55rem 1.3rem}
.stButton>button:hover,div[data-testid="stButton"]>button:hover{filter:brightness(1.15);color:#fff}
.login-shell{min-height:100vh;display:flex;align-items:flex-start;justify-content:center;background:#031421;padding:0 0 40px;margin:0 -1rem 0 -1rem}
.login-card{max-width:1280px;width:100%;padding:14px 0 0;border-radius:0;background:transparent;border:0;box-shadow:none}
.login-brand{font-size:3rem;font-weight:800;color:#f4f6f8;text-align:center;margin:0 0 14px}
.login-sub{font-size:1.05rem;color:#dfe7ef;line-height:1.5;text-align:left;margin:0 0 18px;padding-left:0}
.login-form{padding-top:0}
[data-testid="stForm"]{display:block}
[data-testid="stBaseInputLabel"]{font-size:1rem;font-weight:700;color:#f4f7fb;margin-bottom:8px}
[data-testid="stTextInputRoot"], [data-testid="stBaseInputContainer"]{border-radius:12px !important; border:1px solid rgba(177,189,204,.55) !important; background:#f5f5f5 !important;}
.stTextInput>div>div>input, .stTextInput input, .stTextInput>div>div>input:focus, .stTextInput input:focus{border-radius:12px !important; background:#f5f5f5 !important; color:#1b2430 !important; font-size:1.1rem !important; box-shadow:none !important;}
.stTextInput input::placeholder{color:#8e97a1; font-size:1rem;}
.stButton>button,div[data-testid="stButton"]>button{width:100%;border-radius:12px;font-weight:700;border:1px solid rgba(164,175,191,.65);background:#2f3c4f;color:#f3f5f8;padding:.7rem 1.2rem;font-size:1.1rem;box-shadow:none;margin-top:18px}
.stButton>button:hover,div[data-testid="stButton"]>button:hover{filter:brightness(1.06);color:#fff}
</style>
"""


def render(markup):
    st.markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


render(CSS)


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def login_screen():
    st.markdown("<div class='login-shell'>", unsafe_allow_html=True)
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("<h1 class='login-brand'>Welcome</h1>", unsafe_allow_html=True)
    st.markdown("<div class='login-sub'>Sign in to access the migration control dashboard.</div>", unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        st.markdown("<div class='login-form'>", unsafe_allow_html=True)
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign in")
        st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if credentials_match(username, password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
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
    target = "Amazon RDS (AWS)" if "amazonaws.com" in CLOUD_DSN else "local Docker database"
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
    slot_text = "log slot active" if slot_ok else "log slot inactive"
    nodes = [
        node_html("🗄️", "Legacy PostgreSQL", "online", "ok", "keeps accepting trades"),
        node_html("📡", "Debezium", state.lower(), "ok" if connector_ok else "bad", slot_text),
        node_html("🚌", "Kafka topic", "streaming" if connector_ok else "waiting",
                  "ok" if connector_ok else "warn", "legacy.public.trades"),
        node_html("⚙️", "Python consumer", "on demand", "idle", "runs with the demo"),
        node_html("☁️", "Cloud database", "online", "ok", target),
    ]
    render('<div class="pipe">' + '<div class="arrow">➜</div>'.join(nodes) + '</div>')
    lag_bytes = slot["lag_bytes"] if slot and slot["lag_bytes"] is not None else "n/a"
    st.caption(f"Replication slot lag: {lag_bytes} bytes")

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
    auto = st.toggle("Auto-refresh every 5 seconds", value=False)
    st.button("Refresh now")
    st.caption("Reads both databases and the Debezium connector. "
               "It never changes your data.")

st.fragment(run_every=5 if auto else None)(live_panel)()

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
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        kpi("Compared", shadow.total, "same requests, both rules", "#38bdf8")
    with s2:
        kpi("Matched", shadow.match, "identical results", "#22c55e")
    with s3:
        kpi("Mismatched", shadow.mismatch, "different results",
            "#ef4444" if shadow.mismatch else "#22c55e")
    with s4:
        kpi("Errors", shadow.errors, "failed comparisons", "#ef4444" if shadow.errors else "#22c55e")
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