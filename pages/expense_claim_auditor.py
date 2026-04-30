import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_expense_policy

st.title("✈️ Expense & Travel Claim Auditor")
st.caption("Payroll Mgmt 7a,14,15,21 | SAP: PC00_M99_CALC / PA30")

uploaded = st.file_uploader("Upload Expense Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} claims")

    with st.expander("🔧 Column Mapping"):
        emp_col = st.selectbox("Employee ID", df.columns)
        grade_col = st.selectbox("Grade", ["None"]+list(df.columns))
        amt_col = st.selectbox("Claim Amount", df.columns)
        type_col = st.selectbox("Claim Type", ["None"]+list(df.columns))
        app_col = st.selectbox("Approver (optional)", ["None"]+list(df.columns))
        doc_col = st.selectbox("Docs Attached (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={emp_col:"employee_id", amt_col:"amount"})
    policy = get_expense_policy()
    limits = policy.get("grade_daily_limits",{})

    # Over-limit
    if grade_col != "None":
        df["daily_limit"] = df[grade_col].map(limits).fillna(2000)
        over = df[df["amount"] > df["daily_limit"]]
        if not over.empty:
            st.warning(f"Over-limit claims: {len(over)} (Payroll Mgmt 7a)")
            st.dataframe(over.head(20), use_container_width=True)

    # Self-approved
    if app_col != "None":
        self_app = df[df["employee_id"] == df[app_col]]
        if not self_app.empty:
            st.error(f"Self-approved claims: {len(self_app)} — SOD violation (Payroll 15)")

    # No docs
    if doc_col != "None":
        no_doc = df[df[doc_col] == 0]
        max_no_doc = policy.get("max_claim_without_docs",500)
        high_no_doc = no_doc[no_doc["amount"] > max_no_doc]
        if not high_no_doc.empty:
            st.warning(f"Claims >₹{max_no_doc} without docs: {len(high_no_doc)}")

    # IsolationForest
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) >= 2 and len(df) >= 10:
        X = df[num_cols].fillna(0)
        iso = IsolationForest(contamination=0.05, random_state=42)
        df["anomaly"] = iso.fit_predict(X)
        anom = df[df["anomaly"] == -1]
        if not anom.empty:
            st.subheader("🚨 ML Anomalies")
            st.dataframe(anom.head(20), use_container_width=True)

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _ExpCheck(BaseAuditCheck):
        name = "Expense Claim Auditor"
        checklist_ref = "Payroll Mgmt 7a/14/15"
        sap_tcode_standard_alt = "PC00_M99_CALC / PA30"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _ExpCheck()
    log_df = df.head(100).copy()
    log_df["vendor_name"] = log_df["employee_id"]
    log_df["flag_reason"] = "Expense claim anomaly"
    log_df["risk_band"] = "MEDIUM"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Expense Claims", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 Findings logged")
