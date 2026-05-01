import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck

st.title("🔐 IT General Controls & SAP Authorization Audit")
st.caption("Companies Act Section 143(3)(i) | SoD Matrix | SAP: SU01 / SUIM / SM20")

# Built-in SoD Conflict Matrix
SOD_CONFLICTS = [
    {"a": "FK01", "b": "F110", "risk": "CRITICAL", "desc": "Vendor Create + Payment Run", "ref": "COSO Principle 10"},
    {"a": "ME21N","b": "MIGO", "risk": "CRITICAL", "desc": "PO Create + GRN Approval", "ref": "Purchasing A.22"},
    {"a": "PC00", "b": "PA30", "risk": "CRITICAL", "desc": "Payroll Run + HR Master", "ref": "Payroll Mgmt 15"},
    {"a": "FD01", "b": "VF11", "risk": "HIGH",     "desc": "Customer Create + Invoice Cancel"},
    {"a": "FB50", "b": "FBV0", "risk": "HIGH",     "desc": "Journal Entry + Journal Approval"},
    {"a": "FS00", "b": "FB50", "risk": "HIGH",     "desc": "GL Account Create + Journal Post"},
]

uploaded = st.file_uploader("Upload SUIM User Access Dump (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} access records")

    with st.expander("🔧 Column Mapping"):
        user_col = st.selectbox("User ID", df.columns)
        tcode_col = st.selectbox("T-Code", df.columns)
        role_col = st.selectbox("Role (optional)", ["None"]+list(df.columns))
        last_login_col = st.selectbox("Last Login (optional)", ["None"]+list(df.columns))
        status_col = st.selectbox("Status (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={user_col:"user_id", tcode_col:"tcode"})

    # SoD check
    conflicts = []
    for c in SOD_CONFLICTS:
        a_users = set(df[df["tcode"] == c["a"]]["user_id"])
        b_users = set(df[df["tcode"] == c["b"]]["user_id"])
        for user in a_users & b_users:
            conflicts.append({**c, "user_id": user})
    if conflicts:
        conf_df = pd.DataFrame(conflicts)
        st.error(f"🚨 {len(conf_df)} SoD conflicts detected")
        st.dataframe(conf_df, use_container_width=True)
    else:
        st.success("No SoD conflicts detected.")

    # Privileged access
    if role_col != "None":
        privileged = df[df[role_col].isin(["SAP_ALL","SAP_NEW"])]
        if not privileged.empty:
            st.warning(f"Privileged roles: {len(privileged)} assignments")

    # Inactive users
    if last_login_col != "None" and status_col != "None":
        df["last_login_dt"] = pd.to_datetime(df[last_login_col], errors="coerce")
        df["days_since_login"] = (datetime.today() - df["last_login_dt"]).dt.days
        inactive = df[(df["days_since_login"] > 90) & (df[status_col] == "Active")]
        if not inactive.empty:
            st.warning(f"Inactive active users: {len(inactive)} (last login >90 days)")

    # Generic IDs
    generic = df[df["user_id"].str.upper().isin(["ADMIN","TEST","TEMP","BACKUP"])]
    if not generic.empty:
        st.error(f"Generic user IDs: {len(generic)} — immediate remediation required")

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _ITGCCheck(BaseAuditCheck):
        name = "ITGC SAP Access"
        checklist_ref = "COSO Principle 10 / Companies Act 143(3)(i)"
        sap_tcode_standard_alt = "SU01 / SUIM / SM20"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _ITGCCheck()
    if conflicts:
        log_df = pd.DataFrame(conflicts)
        log_df["amount_at_risk"] = 0
        log_df["vendor_name"] = log_df["user_id"]
        log_df["flag_reason"] = log_df["desc"]
        log_df["risk_band"] = log_df["risk"]
        checker.log_to_db(log_df, area="ITGC", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 {len(log_df)} SoD draft findings staged for auditor confirmation")
