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
from utils.compliance_loader import get_pf_esi_rates

st.title("👥 Payroll & HR Audit")
st.caption("Payroll Mgmt 1–21 | SAP: PA30 / PC00_M99_CALC / S_AHR_61016362")

uploaded = st.file_uploader("Upload Payroll Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} employees")

    with st.expander("🔧 Column Mapping"):
        emp_col = st.selectbox("Employee ID", df.columns)
        pan_col = st.selectbox("PAN", df.columns)
        bank_col = st.selectbox("Bank Account", df.columns)
        basic_col = st.selectbox("Basic + DA", df.columns)
        pf_col = st.selectbox("PF Deducted", df.columns)
        esi_col = st.selectbox("ESI Deducted", df.columns)
        gross_col = st.selectbox("Gross Wages", df.columns)
        status_col = st.selectbox("Status", ["None"]+list(df.columns))
        last_att_col = st.selectbox("Last Attendance Date", ["None"]+list(df.columns))

    df = df.rename(columns={emp_col:"employee_id", pan_col:"pan", bank_col:"bank_account",
                            basic_col:"basic_da", pf_col:"pf_deducted", esi_col:"esi_deducted",
                            gross_col:"gross_wages"})

    # Ghost employee checks
    dup_pan = df[df.duplicated("pan", keep=False)]
    dup_bank = df[df.duplicated("bank_account", keep=False)]
    if status_col != "None" and last_att_col != "None":
        df["days_absent"] = (pd.Timestamp.today() - pd.to_datetime(df[last_att_col], errors="coerce")).dt.days
        absent_active = df[(df[status_col] == "Active") & (df["days_absent"] > 90)]
    else:
        absent_active = pd.DataFrame()

    if not dup_pan.empty:
        st.warning(f"Duplicate PAN: {len(dup_pan)} (Ghost employee risk — Payroll 7)")
    if not dup_bank.empty:
        st.warning(f"Duplicate Bank Account: {len(dup_bank)} (Ghost employee risk — Payroll 7)")
    if not absent_active.empty:
        st.warning(f"Active but absent >90 days: {len(absent_active)} (Ghost employee risk)")

    # PF/ESI mismatch
    rates = get_pf_esi_rates()
    df["pf_expected"] = df["basic_da"].clip(upper=rates["pf_wage_ceiling"]) * rates["pf_employee_rate"] / 100
    df["pf_variance"] = (df["pf_deducted"] - df["pf_expected"]).abs()
    df["esi_applicable"] = df["gross_wages"] <= rates["esi_wage_ceiling"]
    df.loc[df["esi_applicable"], "esi_expected"] = df["gross_wages"] * rates["esi_employee_rate"] / 100
    df["esi_variance"] = (df["esi_deducted"] - df.get("esi_expected", 0)).abs()
    pf_esi_flag = df[(df["pf_variance"] > 1) | (df["esi_variance"] > 1)]
    if not pf_esi_flag.empty:
        st.warning(f"PF/ESI mismatch: {len(pf_esi_flag)} employees (Payroll 14 / F&A C.10)")
        st.dataframe(pf_esi_flag[["employee_id","basic_da","pf_deducted","pf_expected","esi_deducted","esi_expected"]].head(20), use_container_width=True)

    # ML anomaly
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
    class _PayrollCheck(BaseAuditCheck):
        name = "Payroll Audit"
        checklist_ref = "Payroll Mgmt 7/14/15"
        sap_tcode_standard_alt = "PA30 / PC00_M99_CALC"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _PayrollCheck()
    log_df = df.head(100).copy()
    log_df["vendor_name"] = log_df["employee_id"]
    log_df["flag_reason"] = "Payroll anomaly"
    log_df["risk_band"] = "HIGH"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Payroll", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 Draft findings staged for auditor confirmation")
