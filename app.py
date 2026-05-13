import streamlit as st
import yaml
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.industry_filter import (
    get_current_profile_name, set_current_profile_name,
    is_page_enabled
)
from utils.audit_db import load_findings, get_kpis
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id
from core.init_audit_system import initialize_audit_system
from core.rbac import init_rbac, get_user, has_permission, verify_password, hash_password, log_governance_action

st.set_page_config(page_title="AI Audit Engineer", page_icon="🚨", layout="wide")

# ── RBAC INITIALIZATION ─────────────────────────────────────────────
# Initialize RBAC tables on first run
if "rbac_initialized" not in st.session_state:
    init_rbac()
    st.session_state["rbac_initialized"] = True

# ── LOGIN GATE ─────────────────────────────────────────────────────
# Initialize session state for authentication
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "current_role" not in st.session_state:
    st.session_state["current_role"] = None

def login_user(username: str, password: str = None) -> bool:
    """Authenticate user and set session state."""
    if not password:
        return False

    user = get_user(username)
    if user and user.get("status") == "Active":
        stored_hash = user.get("password_hash")

        # If password_hash is missing (pre-upgrade DB), allow first-time migration
        # only when password matches the default expectation.
        if stored_hash:
            if not verify_password(password, stored_hash):
                return False
        else:
            default_password = os.getenv("AUDIT_DEFAULT_PASSWORD")
            expected_plain = default_password if default_password is not None else username
            if password != expected_plain:
                return False

            # Upgrade this user record to hashed password.
            import sqlite3
            conn = sqlite3.connect("data/audit.db")
            conn.execute(
                "UPDATE audit_users SET password_hash=? WHERE username=?",
                (hash_password(password), username),
            )
            conn.commit()
            conn.close()

        st.session_state["logged_in"] = True
        st.session_state["current_user"] = username
        st.session_state["current_role"] = user.get("role", "viewer")
        # Update last login
        import sqlite3
        conn = sqlite3.connect("data/audit.db")
        conn.execute("UPDATE audit_users SET last_login = CURRENT_TIMESTAMP WHERE username = ?", (username,))
        conn.commit()
        conn.close()

        log_governance_action(username, "LOGIN", entity_type="auth")
        return True
    return False

def logout_user():
    """Clear session state and log out."""
    current_user = st.session_state.get("current_user")
    if current_user:
        log_governance_action(current_user, "LOGOUT", entity_type="auth")

    st.session_state["logged_in"] = False
    st.session_state["current_user"] = None
    st.session_state["current_role"] = None
    st.rerun()

# ── SIDEBAR ────────────────────────────────────────────────────────
st.sidebar.title("AI Audit Engineer")

# Login/Logout Section
if not st.session_state["logged_in"]:
    with st.sidebar.expander("🔐 Login", expanded=True):
        login_username = st.text_input("Username", placeholder="Enter username", key="login_user_input")
        login_password = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass_input")
        col_login, col_guest = st.columns(2)
        with col_login:
            if st.button("Login", type="primary", use_container_width=True):
                if login_user(login_username, login_password):
                    st.success(f"Welcome, {login_username}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials or inactive user")
        with col_guest:
            if st.button("Guest", use_container_width=True):
                # Set as guest viewer
                st.session_state["logged_in"] = True
                st.session_state["current_user"] = "guest"
                st.session_state["current_role"] = "viewer"
                st.rerun()
    
    st.sidebar.divider()
    st.sidebar.warning("⚠️ You are browsing as guest. Some features may be restricted.")
else:
    # Display logged-in user info
    user_info = get_user(st.session_state["current_user"])
    display_name = user_info.get("display_name", st.session_state["current_user"]) if user_info else st.session_state["current_user"]
    
    with st.sidebar.expander(f"👤 {display_name} ({st.session_state['current_role'].upper()})", expanded=True):
        st.markdown(f"**Role:** {st.session_state['current_role'].capitalize()}")
        if user_info and user_info.get("email"):
            st.markdown(f"**Email:** {user_info.get('email')}")
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
    
    st.sidebar.divider()

profiles = ["manufacturing_fmcg", "it_services", "healthcare_pharma", "retail", "financial_services"]
current = get_current_profile_name()
selected = st.sidebar.selectbox("🏭 Industry Profile", profiles, index=profiles.index(current) if current in profiles else 0)
if selected != current:
    set_current_profile_name(selected)
    st.sidebar.success(f"Switched to {selected}")
    st.rerun()

st.sidebar.divider()

nav_registry_path = Path(__file__).parent / "config" / "navigation_registry.yaml"
nav_registry = {}
try:
    if nav_registry_path.exists():
        nav_registry = yaml.safe_load(nav_registry_path.read_text(encoding="utf-8")) or {}
except Exception as e:
    st.sidebar.warning(f"Navigation registry could not be loaded: {e}")

phases = nav_registry.get("phases", [])
st.sidebar.markdown("### Main Pages")
st.sidebar.page_link("app.py", label="Home Dashboard")

visible_phases = []
for i, phase in enumerate(phases):
    visible_items = []
    for item in phase.get("items", []):
        module_id = item.get("module_id")
        if module_id and not is_page_enabled(module_id):
            continue
        visible_items.append(item)
    if visible_items:
        visible_phases.append({**phase, "items": visible_items, "_index": i})

if visible_phases:
    phase_labels = [phase.get("label", f"Phase {phase['_index'] + 1}") for phase in visible_phases]
    selected_phase_label = st.sidebar.selectbox("Filter menu by workstream", phase_labels, key="sidebar_phase_filter")
    selected_phase = visible_phases[phase_labels.index(selected_phase_label)]

    page_labels = [item.get("label", item["page"]) for item in selected_phase.get("items", [])]
    selected_page_label = st.sidebar.selectbox("Select page", page_labels, key="sidebar_page_filter")
    selected_item = selected_phase["items"][page_labels.index(selected_page_label)]
    permission_key = selected_item.get("permission_key")
    disabled = bool(permission_key) and not has_permission(st.session_state["current_user"], permission_key)

    if disabled:
        st.sidebar.warning("Your current role cannot open this page.")
    elif st.sidebar.button("Open selected page", type="primary", use_container_width=True):
        st.switch_page(selected_item["page"])

# Role Badge
st.sidebar.divider()
role_badge = {
    "admin": "🔴 Admin",
    "auditor": "🟡 Auditor", 
    "reviewer": "🔵 Reviewer",
    "viewer": "⚪ Viewer"
}.get(st.session_state["current_role"], "⚪ Guest")
st.sidebar.caption(f"Session: {role_badge}")

with st.sidebar.expander("📚 SAP T-Code Reference"):
    st.markdown("""
| Z-Tcode | Standard Alt |
|---|---|
| ZVOTAGE | FBL1N / S_ALR_87012085 |
| ZCOTAGEN | FBL5N / S_ALR_87012197 |
| ZMFGSTK | MB52 + MB5M |
| ZWR/ZWR1 | MB51 (551/552) |
| ZPRD | COOIS |
| ZSRNEW/ZSEG | VF05 / VA05 |
| ZEREG/ZCOTAGE | FBL3N |
""")

# ── COVER PAGE ─────────────────────────────────────────────────────

# Dashboard visual system. Uses Streamlit theme variables so light/dark mode is preserved.
st.markdown("""
<style>
    :root {
        --audit-border: rgba(125, 125, 125, 0.22);
        --audit-teal: #0e7490;
        --audit-blue: #2563eb;
        --audit-amber: #d97706;
        --audit-green: #059669;
    }
    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, rgba(14, 116, 144, 0.12), rgba(37, 99, 235, 0.08) 42%, rgba(5, 150, 105, 0.08)),
            var(--secondary-background-color);
        border-right: 1px solid var(--audit-border);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        letter-spacing: 0;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] {
        padding: 6px 0 2px 0;
    }
    [data-testid="stSidebar"] div[data-testid="stExpander"] {
        border: 1px solid var(--audit-border);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.03);
    }
    .audit-hero {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--audit-border);
        border-radius: 10px;
        padding: 30px 32px;
        margin-bottom: 18px;
        background:
            radial-gradient(circle at 92% 12%, rgba(217, 119, 6, 0.18), transparent 28%),
            linear-gradient(135deg, rgba(14, 116, 144, 0.18), rgba(37, 99, 235, 0.12) 55%, rgba(5, 150, 105, 0.12)),
            var(--background-color);
    }
    .audit-hero-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.7fr) minmax(260px, 0.8fr);
        gap: 22px;
        align-items: center;
    }
    .audit-kicker {
        margin: 0 0 9px 0;
        color: var(--audit-teal);
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
    }
    .audit-title {
        margin: 0;
        color: var(--text-color);
        font-size: 2.55rem;
        line-height: 1.04;
        letter-spacing: 0;
        font-weight: 780;
    }
    .audit-subtitle {
        margin: 13px 0 0 0;
        color: var(--text-color);
        opacity: 0.8;
        font-size: 1.04rem;
        max-width: 960px;
    }
    .audit-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 20px;
    }
    .audit-pill {
        border: 1px solid var(--audit-border);
        border-radius: 999px;
        padding: 7px 12px;
        background: var(--secondary-background-color);
        color: var(--text-color);
        font-size: 0.84rem;
    }
    .hero-stack {
        border: 1px solid var(--audit-border);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.05);
        padding: 14px;
    }
    .hero-stack div {
        display: flex;
        justify-content: space-between;
        gap: 18px;
        padding: 10px 2px;
        border-bottom: 1px solid rgba(125, 125, 125, 0.18);
        color: var(--text-color);
        font-size: 0.9rem;
    }
    .hero-stack div:last-child { border-bottom: 0; }
    .hero-stack strong { color: var(--audit-teal); }
    .section-band {
        border: 1px solid var(--audit-border);
        border-radius: 10px;
        padding: 22px;
        margin: 20px 0;
    }
    .band-teal {
        background: linear-gradient(135deg, rgba(14, 116, 144, 0.13), rgba(14, 116, 144, 0.04)), var(--background-color);
    }
    .band-blue {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(37, 99, 235, 0.035)), var(--background-color);
    }
    .band-green {
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.13), rgba(217, 119, 6, 0.05)), var(--background-color);
    }
    .band-heading {
        margin-bottom: 16px;
    }
    .band-heading span {
        display: inline-block;
        color: var(--audit-teal);
        font-size: 0.78rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0;
        margin-bottom: 4px;
    }
    .band-heading h2 {
        margin: 0;
        color: var(--text-color);
        font-size: 1.28rem;
        letter-spacing: 0;
    }
    .band-heading p {
        margin: 7px 0 0 0;
        color: var(--text-color);
        opacity: 0.74;
        max-width: 900px;
    }
    .audit-grid {
        display: grid;
        gap: 14px;
    }
    .audit-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .audit-grid.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .audit-panel {
        border: 1px solid var(--audit-border);
        border-radius: 8px;
        padding: 17px 17px 15px 17px;
        height: 100%;
        background: var(--secondary-background-color);
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.035);
    }
    .audit-panel h3 {
        margin: 0 0 8px 0;
        color: var(--text-color);
        font-size: 1.01rem;
        letter-spacing: 0;
    }
    .audit-panel p {
        margin: 0;
        color: var(--text-color);
        opacity: 0.76;
        font-size: 0.9rem;
        line-height: 1.45;
    }
    .audit-line { border-left: 4px solid var(--audit-teal); }
    .audit-line-blue { border-left-color: var(--audit-blue); }
    .audit-line-amber { border-left-color: var(--audit-amber); }
    .audit-line-green { border-left-color: var(--audit-green); }
    .flow-step {
        border: 1px solid var(--audit-border);
        border-radius: 8px;
        padding: 15px;
        background: var(--secondary-background-color);
        height: 100%;
    }
    .flow-step strong {
        display: block;
        margin-bottom: 5px;
        color: var(--text-color);
    }
    .flow-step span {
        color: var(--text-color);
        opacity: 0.74;
        font-size: 0.88rem;
    }
    @media (max-width: 920px) {
        .audit-hero-grid,
        .audit-grid.three,
        .audit-grid.four {
            grid-template-columns: 1fr;
        }
        .audit-title { font-size: 2rem; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<section class="audit-hero">
    <div class="audit-hero-grid">
        <div>
            <p class="audit-kicker">Audit OS May-2026</p>
            <h1 class="audit-title">SARVAGYA - AI Audit Engineer</h1>
            <p class="audit-subtitle">
                A practical command center for engagement-scoped detection, maker-checker finding review,
                policy-grounded RAG analysis, SAP data-pack testing, and management-ready reporting.
            </p>
            <div class="audit-strip">
                <span class="audit-pill">100% population testing</span>
                <span class="audit-pill">Engagement-linked findings</span>
                <span class="audit-pill">Draft to review to confirm workflow</span>
                <span class="audit-pill">Policy RAG + standards registry</span>
                <span class="audit-pill">SAP, finance, compliance, ITGC</span>
            </div>
        </div>
        <aside class="hero-stack">
            <div><span>Core idea</span><strong>Audit OS</strong></div>
            <div><span>Evidence flow</span><strong>Upload to finding</strong></div>
            <div><span>AI layer</span><strong>RAG + analytics</strong></div>
            <div><span>Output</span><strong>Board-ready packs</strong></div>
        </aside>
    </div>
</section>
""", unsafe_allow_html=True)

# Initialize all core tables (idempotent — safe on every startup)
if "audit_system_initialized" not in st.session_state:
    initialize_audit_system()
    st.session_state["audit_system_initialized"] = True

# Engagement link and live findings dashboard
render_engagement_selector("home")
active_engagement_id = get_active_engagement_id("home")
if active_engagement_id is None:
    total_findings = 0
    open_findings = 0
    critical_findings = 0
    high_findings = 0
else:
    findings = load_findings(engagement_id=active_engagement_id)
    total_findings = len(findings)
    open_findings = len(findings[findings["status"] == "Open"]) if not findings.empty else 0
    critical_findings = len(findings[findings["risk_band"] == "CRITICAL"]) if not findings.empty else 0
    high_findings = len(findings[findings["risk_band"] == "HIGH"]) if not findings.empty else 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Findings", total_findings)
m2.metric("Open", open_findings)
m3.metric("Critical", critical_findings)
m4.metric("High", high_findings)
m5.metric("Audit Modules", 27)

st.divider()

# Operating model
st.markdown("""
<section class="section-band band-teal">
    <div class="band-heading">
        <span>Operating Model</span>
        <h2>From data upload to audit committee output</h2>
        <p>The dashboard mirrors the actual audit flow: scope the engagement, run procedures, review exceptions, then report outcomes.</p>
    </div>
    <div class="audit-grid three">
        <div class="audit-panel audit-line">
            <h3>Engagement Control</h3>
            <p>Every detection page links draft findings to the active engagement selected above, keeping audit work scoped to a client, period, and workpaper context.</p>
        </div>
        <div class="audit-panel audit-line-blue">
            <h3>Detection and Evidence</h3>
            <p>Modules analyze SAP extracts, ledgers, contracts, payroll, receivables, inventory, BRS, GST/TDS, fixed assets, ITGC, and financial statement packs.</p>
        </div>
        <div class="audit-panel audit-line-amber">
            <h3>Review and Reporting</h3>
            <p>Exceptions are staged for auditor review before entering the official trail, then flow into workflow, risk dashboards, committee packs, and KPI reporting.</p>
        </div>
    </div>
</section>
""", unsafe_allow_html=True)

# Architecture highlights
st.markdown("""
<section class="section-band band-blue">
    <div class="band-heading">
        <span>Architecture Signals</span>
        <h2>Built like an audit system, not a demo notebook</h2>
        <p>Reusable helpers, central audit tables, role-aware navigation, and policy-grounded AI keep the platform coherent as modules grow.</p>
    </div>
    <div class="audit-grid four">
        <div class="audit-panel audit-line">
            <h3>Column Intelligence</h3>
            <p>SAP and spreadsheet field synonyms are normalized through reusable mapping helpers.</p>
        </div>
        <div class="audit-panel audit-line-blue">
            <h3>Compliance Data</h3>
            <p>Rates and calendars are externalized in configuration instead of being buried in page code.</p>
        </div>
        <div class="audit-panel audit-line-green">
            <h3>Audit Trail</h3>
            <p>Findings, drafts, workflow, KPIs, engagements, and evidence share one SQLite audit store.</p>
        </div>
        <div class="audit-panel audit-line-amber">
            <h3>Governance Ready</h3>
            <p>RBAC, role-aware navigation, and maker-checker patterns are designed into the workflow.</p>
        </div>
    </div>
</section>
""", unsafe_allow_html=True)

# Quick start guide
st.markdown("""
<section class="section-band band-green">
    <div class="band-heading">
        <span>Recommended Flow</span>
        <h2>Use it like an audit file</h2>
        <p>Start with scope, move through fieldwork, review what matters, then package the audit story for management.</p>
    </div>
    <div class="audit-grid four">
        <div class="flow-step">
            <strong>1. Set engagement</strong>
            <span>Create or select an engagement, then keep it active before running detection.</span>
        </div>
        <div class="flow-step">
            <strong>2. Run testing</strong>
            <span>Upload SAP, ledger, payroll, contract, or compliance extracts in the relevant module.</span>
        </div>
        <div class="flow-step">
            <strong>3. Review drafts</strong>
            <span>Confirm valid exceptions into official findings and discard false positives.</span>
        </div>
        <div class="flow-step">
            <strong>4. Report outcomes</strong>
            <span>Use workflow, risk register, report center, KPI dashboard, and committee pack.</span>
        </div>
    </div>
</section>
""", unsafe_allow_html=True)

# Footer
st.caption("""
**AI Audit Engineer v5.1** | Built with Streamlit, XGBoost, SHAP, pgvector, and ReportLab.  
For architecture details see `PROJECT_BLUEPRINT.md`. For operations see `USER_GUIDE.md`.
""")
