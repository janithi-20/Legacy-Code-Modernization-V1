import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import psycopg
import streamlit as st

from app.common import calc
from app.config import CLOUD_DSN, LEGACY_DSN
from backend.auth import credentials_match
from backend.data import Reader, connector_status, run_query, slot_info
from app.migration.canary import advance
from app.validation.reconciliation import reconcile
from app.validation.shadow import Shadow

st.set_page_config(page_title="Bridgeline | Migration Control", layout="wide")


def login():
    if st.session_state.get("authenticated", False):
        return True

    st.markdown(
        """
        <style>
        /* Login page theme: edit these variables to customize the palette. */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --login-page: #F3F5F9;
            --login-ink: #0F172A;
            --login-muted: #5B6475;
            --login-border: #CBD2E0;
            --login-blue: #2F5BEA;
            --login-blue-dark: #2446C9;
            --login-focus: #9DB4FF;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDeployButton"],
        footer {
            display: none;
        }

        html,
        body,
        [data-testid="stAppViewContainer"] {
            background: var(--login-page);
            font-family: 'Inter', sans-serif;
        }

        [data-testid="stMain"] {
            min-height: 100vh;
            padding: 0 8px;
        }

        [data-testid="stMainBlockContainer"] {
            min-height: 100vh;
            max-width: none;
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
            width: min(100%, 420px);
            align-items: center;
        }

        [data-testid="stLayoutWrapper"] {
            width: min(100%, 420px) !important;
            margin: auto !important;
        }

        /* Card, heading, fields, and button. */
        [data-testid="stForm"] {
            width: min(100%, 420px);
            box-sizing: border-box;
            padding: 36px 32px;
            border: 0;
            border-radius: 20px;
            background: #FFFFFF;
            box-shadow: 0 8px 30px rgba(15, 27, 61, 0.10);
        }

        [data-testid="stForm"] > [data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }

        .login-heading h1 {
            margin: 0 0 8px;
            color: var(--login-ink);
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.01em;
            line-height: 1.25;
            text-align: center;
        }

        .login-heading p {
            margin: 0 0 28px;
            color: var(--login-muted);
            font-size: 15px;
            line-height: 1.45;
            text-align: center;
        }

        [data-testid="stForm"] label {
            color: var(--login-ink);
            font-size: 14px;
            font-weight: 600;
        }

        [data-testid="stForm"] [data-testid="stTextInput"] {
            margin-bottom: 20px;
        }

        [data-testid="stForm"] [data-testid="stTextInput"] input {
            box-sizing: border-box;
            height: 48px;
            margin-top: 6px;
            border: 1.5px solid var(--login-border);
            border-radius: 12px;
            background: #FFFFFF !important;
            color: var(--login-ink) !important;
            caret-color: var(--login-ink) !important;
            font-family: 'Inter', sans-serif;
            font-size: 15px;
        }

        [data-testid="stForm"] input::placeholder {
            color: #7A7F87 !important;
            opacity: 1 !important;
        }

        [data-testid="stForm"] [data-testid="stTextInput"] input:focus {
            border-color: var(--login-focus) !important;
            box-shadow: 0 0 0 3px rgba(157, 180, 255, 0.28) !important;
        }

        /* Keep Streamlit's password behavior while displaying a text toggle. */
        [data-testid="stForm"] [data-testid="stTextInput"]:has(input[type="password"]) button {
            color: var(--login-blue-dark) !important;
            font-size: 0 !important;
            font-weight: 600;
        }

        [data-testid="stForm"] [data-testid="stTextInput"]:has(input[type="password"]) button::after {
            content: "Show";
            font-size: 14px;
        }

        [data-testid="stForm"] [data-testid="stTextInput"]:has(input[type="text"]) button::after {
            content: "Hide";
        }

        [data-testid="stFormSubmitButton"] {
            width: 100% !important;
        }

        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            height: 50px;
            margin-top: 0;
            border: 0;
            border-radius: 12px;
            background: var(--login-blue);
            color: #FFFFFF;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            font-weight: 600;
        }

        [data-testid="stBaseButton-primaryFormSubmit"] {
            width: 100% !important;
        }

        [kind="primaryFormSubmit"] {
            width: 100% !important;
        }

        [data-testid="stFormSubmitButton"] button:hover {
            border: 0;
            background: var(--login-blue-dark);
        }

        .login-error {
            margin-top: 16px;
            padding: 12px 14px;
            border: 1px solid #F4B8B1;
            border-radius: 12px;
            background: #FDE8E6;
            color: #8F2217;
            font-size: 14px;
            font-weight: 500;
            line-height: 1.4;
        }

        .login-help {
            margin-top: 18px;
            color: var(--login-muted);
            font-size: 13px;
            text-align: center;
        }

        .login-help a {
            color: var(--login-blue-dark);
            font-weight: 600;
            text-decoration: none;
        }

        .login-footer {
            margin-top: 10px;
            color: var(--login-muted);
            font-size: 13px;
            text-align: center;
        }

        @media (max-width: 800px) {
            [data-testid="stMainBlockContainer"] {
                padding: 8px;
            }

            [data-testid="stForm"] {
                padding: 36px 24px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        st.markdown(
            """
            <div class="login-heading">
                <h1>Welcome</h1>
                <p>Sign in to access the migration control dashboard.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        entered_username = st.text_input(
            "Username", placeholder="Enter your username", autocomplete="username"
        )
        entered_password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button(
            "Sign in", type="primary", use_container_width=True
        )
        if submitted:
            if credentials_match(entered_username, entered_password):
                st.session_state["authenticated"] = True
                st.rerun()
            st.markdown(
                '<div class="login-error" role="alert">'
                "Incorrect username or password. Please try again."
                "</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            """
            <div class="login-help">
                Can't sign in? <a href="mailto:support@example.com">Contact us</a>
            </div>
            <div class="login-footer">Authorized team members only.</div>
            """,
            unsafe_allow_html=True,
        )
    return False


def legacy_login():
    if st.session_state.get("authenticated", False):
        return True

    st.markdown(
        """
        <style>
        [data-testid="stHeader"], [data-testid="stToolbar"] {
            display: none;
        }

        [data-testid="stAppViewContainer"] {
            background: #f4f6fb;
        }

        [data-testid="stMain"] {
            padding: 0;
        }

        .login-shell {
            min-height: 100vh;
            display: grid;
            grid-template-columns: minmax(420px, 1fr) minmax(480px, 1fr);
            margin: -4rem -4rem 0;
        }

        .login-brand-panel {
            background: #111d43;
            color: #ffffff;
            padding: 3rem 3.5rem 2.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .brand-mark {
            display: inline-flex;
            align-items: center;
            gap: 0.65rem;
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .brand-icon {
            width: 2.15rem;
            height: 2.15rem;
            border-radius: 0.55rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #5578f5;
            font-size: 1.55rem;
            font-weight: 400;
            line-height: 1;
        }

        .brand-copy {
            max-width: 32rem;
            margin: auto 0;
        }

        .brand-copy h1 {
            margin: 0 0 1.1rem;
            color: #ffffff;
            font-size: clamp(2.2rem, 3.3vw, 3.45rem);
            line-height: 1.08;
            letter-spacing: -0.045em;
        }

        .brand-copy > p {
            margin: 0 0 2.1rem;
            color: #aeb9d8;
            font-size: 1rem;
            line-height: 1.55;
        }

        .feature-list {
            display: grid;
            gap: 1.05rem;
        }

        .feature {
            display: grid;
            grid-template-columns: 2rem 1fr;
            gap: 0.7rem;
            align-items: start;
        }

        .feature-number {
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #263d81;
            color: #b7c8ff;
            font-weight: 700;
        }

        .feature strong {
            display: block;
            margin: 0.1rem 0 0.15rem;
            font-size: 0.9rem;
        }

        .feature span {
            color: #aeb9d8;
            font-size: 0.8rem;
        }

        .brand-footer {
            color: #8998be;
            font-size: 0.72rem;
        }

        .login-form-panel {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 3rem;
        }

        .login-form-panel > div {
            width: min(100%, 28rem);
        }

        .login-heading h2 {                                  
            margin: 0 0 0.45rem;
            color: #17213a;
            font-size: 1.55rem;
            letter-spacing: -0.03em;
            text-align: center;
        }

        .login-heading p {
            margin: 0 0 1.25rem;
            color: #69758b;
            font-size: 0.85rem;
            text-align: center;
        }

        [data-testid="stForm"] {
            padding: 2rem 1.7rem 1.65rem;
            border: 0;
            border-radius: 1.05rem;
            background: #ffffff;
            box-shadow: 0 1.25rem 2.7rem rgba(17, 29, 67, 0.12);
        }

        [data-testid="stForm"] label {
            color: #17213a;
            font-size: 0.78rem;
            font-weight: 700;
        }

        [data-testid="stForm"] input {
            height: 2.65rem;
            border: 1px solid #d5dce9;
            border-radius: 0.65rem;
            background: #ffffff !important;
            color: #17213a !important;
            caret-color: #17213a !important;
            font-size: 0.85rem;
        }

        [data-testid="stForm"] input::placeholder {
            color: #7a8598 !important;
            opacity: 1 !important;
        }

        [data-testid="stForm"] input:focus {
            border-color: #3760eb;
            box-shadow: 0 0 0 1px #3760eb;
        }

        [data-testid="stFormSubmitButton"] button {
            width: 100%;
            height: 2.7rem;
            margin-top: 0.45rem;
            border: 0;
            border-radius: 0.65rem;
            background: #3560eb;
            font-weight: 700;
        }

        [data-testid="stFormSubmitButton"] button:hover {
            background: #284ed0;
        }

        .login-note {
            margin-top: 1.1rem;
            color: #7a8598;
            font-size: 0.72rem;
            text-align: center;
        }

        @media (max-width: 800px) {
            .login-shell {
                display: block;
                margin: -1rem -1rem 0;
            }

            .login-brand-panel {
                min-height: auto;
                padding: 2rem 1.5rem;
                gap: 3rem;
            }

            .brand-copy h1 {
                font-size: 2.35rem;
            }

            .brand-footer {
                display: none;
            }

            .login-form-panel {
                padding: 2.5rem 1.25rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1], gap="small")
    with left:
        st.markdown(
            """
            <div class="login-brand-panel">
                <div class="brand-mark">
                    <span class="brand-icon">→</span>
                    <span>Bridgeline</span>
                </div>
                <div class="brand-copy">
                    <h1>Move to the cloud<br>without stopping the exchange.</h1>
                    <p>Watch legacy and cloud data stay in sync, validate every result, then shift traffic step by step.</p>
                    <div class="feature-list">
                        <div class="feature">
                            <span class="feature-number">1</span>
                            <div><strong>Live sync status</strong><span>Debezium, Kafka and row counts at a glance.</span></div>
                        </div>
                        <div class="feature">
                            <span class="feature-number">2</span>
                            <div><strong>Shadow validation</strong><span>Compare legacy and cloud results on the same requests.</span></div>
                        </div>
                        <div class="feature">
                            <span class="feature-number">3</span>
                            <div><strong>Canary rollout and rollback</strong><span>5, 25, 50, 100% of traffic, with a way back to 0%.</span></div>
                        </div>
                    </div>
                </div>
                <div class="brand-footer">Legacy PostgreSQL to cloud PostgreSQL · Local simulation</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="login-form-panel">
                <div class="login-heading">
                    <h2>Welcome back</h2>
                    <p>Sign in to access the migration control dashboard.</p>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            entered_username = st.text_input(
                "Username", placeholder="Enter your username", autocomplete="username"
            )
            entered_password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button("Sign in", type="primary")
        st.markdown(
            '<div class="login-note">Authorized team members only.</div></div></div>',
            unsafe_allow_html=True,
        )

    if submitted:
        if credentials_match(entered_username, entered_password):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Invalid username or password.")
    return False


if not login():
    st.stop()


def snapshot(data):
    return SimpleNamespace(all=lambda: data)


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

if st.sidebar.button("Sign out"):
    st.session_state["authenticated"] = False
    st.rerun()

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
