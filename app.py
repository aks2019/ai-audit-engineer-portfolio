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
for i, phase in enumerate(phases):
    st.sidebar.markdown(f"**{phase.get('label', f'Phase {i+1}') }**")
    for item in phase.get("items", []):
        page = item["page"]
        label = item.get("label", page)

        module_id = item.get("module_id")
        if module_id and not is_page_enabled(module_id):
            continue

        permission_key = item.get("permission_key")
        disabled = bool(permission_key) and not has_permission(st.session_state["current_user"], permission_key)
        st.sidebar.page_link(page, label=label, disabled=disabled)

    if i < len(phases) - 1:
        st.sidebar.divider()

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

# Hero banner
st.markdown("""
<div style="background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem;">
    <h1 style="color: white; margin: 0; font-size: 2.5rem;">🚀 SARVAGYA - AI Audit Engineer</h1>
    <p style="color: #dbeafe; margin-top: 0.5rem; font-size: 1.2rem;">
        Internal Audit Intelligence Platform — <strong>100% Population Testing</strong> | 
        <strong>Cloud & Local Ready</strong> | <strong>26 Audit Modules</strong>
    </p>
    <p style="color: #93c5fd; margin-top: 0.3rem; font-size: 0.95rem;">
        Created by <strong>Ashok Kumar Sharma</strong> | 
        <a href="https://github.com/aks2019/ai-audit-engineer-portfolio" style="color: #93c5fd;">GitHub</a> | 
        <a href="https://aiauditengineer.onrender.com" style="color: #93c5fd;">Live Deploy</a>
    </p>
</div>
""", unsafe_allow_html=True)

# Initialize all core tables (idempotent — safe on every startup)
if "audit_system_initialized" not in st.session_state:
    initialize_audit_system()
    st.session_state["audit_system_initialized"] = True

# Live metrics from SQLite
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
m1.metric("📁 Total Findings", total_findings)
m2.metric("🔴 Open", open_findings)
m3.metric("💣 Critical", critical_findings)
m4.metric("🔶 High", high_findings)
m5.metric("🎯 Modules", 27)

st.divider()

# Phase cards
st.subheader("🗂️ Platform Modules")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div style="background: var(--secondary-background-color); padding: 1.2rem; border-radius: 10px; border-left: 5px solid #0284c7;">
        <h4 style="margin-top:0; color: var(--text-color);">🔍 Detection Engine</h4>
        <p style="font-size: 0.9rem; color: var(--text-color);">
            AI-powered detection across Payments, Inventory, Fixed Assets, Payroll, Sales, Contracts, GST/TDS, ITGC, BRS, and more.
            Powered by IsolationForest + XGBoost ensembles with SHAP explainability.
        </p>
        <p style="font-size: 0.8rem; color: var(--text-color); opacity: 0.7;">13 modules (P1, P5–P14, P18–P21)</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background: var(--secondary-background-color); padding: 1.2rem; border-radius: 10px; border-left: 5px solid #7c3aed;">
        <h4 style="margin-top:0; color: var(--text-color);">🧠 Analysis & RAG</h4>
        <p style="font-size: 0.9rem; color: var(--text-color);">
            Policy RAG Bot with pgvector + Gemini 1.5 Pro, Dynamic Audit Builder with 5 no-code templates,
            Financial Statement Auditor, NLP Document Intelligence, and Audit Planning Engine.
        </p>
        <p style="font-size: 0.8rem; color: var(--text-color); opacity: 0.7;">6 modules (P2–P4, P14, P23, P25)</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="background: var(--secondary-background-color); padding: 1.2rem; border-radius: 10px; border-left: 5px solid #ea580c;">
        <h4 style="margin-top:0; color: var(--text-color);">📊 Reporting & Governance</h4>
        <p style="font-size: 0.9rem; color: var(--text-color);">
            Risk Register with 5×5 heat maps, Audit Report Center with CFO-ready MIS,
            Audit Committee Pack with editable ATR, KPI Dashboard, and Multi-Company views.
        </p>
        <p style="font-size: 0.8rem; color: var(--text-color); opacity: 0.7;">7 modules (P7, P15–P17, P22, P24, P26)</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Architecture highlights
st.subheader("⚙️ Architecture Highlights")
arch1, arch2, arch3, arch4 = st.columns(4)
arch1.info("**Zero Hardcoded Columns**\n\nSAP field synonym auto-detection via `utils/column_mapper.py`")
arch2.info("**Zero Hardcoded Compliance**\n\nGST/TDS/PF/ESI rates live in YAML — edit, no restart")
arch3.info("**Plugin Architecture**\n\nAdd a new audit check = 1 new class. Zero page changes.")
arch4.info("**Shared Audit Trail**\n\nSingle SQLite `data/audit.db` — all 26 modules read/write")

st.divider()

# Quick start guide
st.subheader("⚠️ Quick Start")
qs1, qs2, qs3 = st.columns(3)
with qs1:
    st.markdown("""
    **1. Select Industry**  
    Choose Manufacturing, IT, Healthcare, Retail, or Financial Services from the sidebar.
    """)
with qs2:
    st.markdown("""
    **2. Upload SAP Data**  
    Go to any Detection module, upload your CSV/Excel, map columns, and run AI analysis.
    """)
with qs3:
    st.markdown("""
    **3. Review & Report**  
    Findings auto-log to SQLite. Use P22 Workflow to track status, P17 for Board packs.
    """)

st.divider()

# Category-wise Module Quick Reference
st.subheader("📋 Module Quick Reference")
mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown("""
    **Detection (P1, P3–P6, P8–P14, P18–P22, P25)**
    - P1: Payment Anomaly Detector
    - P3: Dynamic Audit Builder
    - P4: Financial Statement Auditor
    - P5: BRS Reconciliation
    - P6: Receivables & Bad Debt
    - P8: GST/TDS Compliance
    - P9: Related-Party Monitor
    - P10: Duplicate Invoice Detector
    - P11: Inventory Anomaly
    - P12: Fixed Asset Auditor
    - P13: Expense Claim Auditor
    - P18: Payroll Audit
    - P19: Sales Revenue Auditor
    - P20: ITGC & SAP Access
    - P21: SAP Data Pack Auditor
    - P22: Contract Management
    - P25: Statistical Sampling
    """)
with mc2:
    st.markdown("""
    **Analysis & RAG (P2, P14, P23)**
    - P2: Policy RAG Bot
    - P14: Audit Planning Engine
    - P23: NLP Document Intelligence
    """)
with mc3:
    st.markdown("""
    **Reporting & Governance (P7, P15–P17, P24, P26)**
    - P7: Unified Dashboard
    - P15: Risk Register
    - P16: Audit Report Center
    - P17: Audit Committee Pack
    - P24: Multi-Company View
    - P26: Audit KPI Dashboard
    """)

st.divider()

# Footer
st.caption("""
**AI Audit Engineer v5.1** | Built with Streamlit, Gemini 1.5 Pro, XGBoost, SHAP, pgvector, and ReportLab.  
For architecture details see `PROJECT_BLUEPRINT.md`. For operations see `USER_GUIDE.md`.
""")