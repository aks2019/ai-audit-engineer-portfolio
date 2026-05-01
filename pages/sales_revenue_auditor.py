import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck

st.title("📈 Sales & Revenue Integrity Auditor")
st.caption("SAP HO — CSD, Export, CPD | Ind AS 115 | SAP: VF05 / VA05 / VKM3")

uploaded = st.file_uploader("Upload Sales Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} invoices")

    with st.expander("🔧 Column Mapping"):
        inv_col = st.selectbox("Invoice No", df.columns)
        amt_col = st.selectbox("Amount", df.columns)
        inv_date_col = st.selectbox("Invoice Date", df.columns)
        disp_col = st.selectbox("Dispatch Date", ["None"]+list(df.columns))
        cn_col = st.selectbox("Credit Note No (optional)", ["None"]+list(df.columns))
        cn_date_col = st.selectbox("Credit Note Date (optional)", ["None"]+list(df.columns))
        cust_col = st.selectbox("Customer Name", ["None"]+list(df.columns))

    df = df.rename(columns={inv_col:"invoice_no", amt_col:"amount", inv_date_col:"invoice_date"})
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

    # Credit note concentration in last 3 days
    if cn_date_col != "None":
        df["cn_date"] = pd.to_datetime(df[cn_date_col], errors="coerce")
        df["month_end_3d"] = df["cn_date"].dt.day >= 28 if df["cn_date"].notna().any() else False
        cn_high = df[df["month_end_3d"] & (df["amount"] > df["amount"].quantile(0.80))]
        if not cn_high.empty:
            st.warning(f"Large credit notes in last 3 days of period: {len(cn_high)} (Revenue understatement risk)")
            st.dataframe(cn_high.head(20), use_container_width=True)

    # Ind AS 115 gap
    if disp_col != "None":
        df["dispatch_date"] = pd.to_datetime(df[disp_col], errors="coerce")
        df["gap_days"] = (df["invoice_date"] - df["dispatch_date"]).dt.days
        early = df[df["gap_days"] < -1]
        if not early.empty:
            st.error(f"Invoice before dispatch: {len(early)} rows — Ind AS 115 risk")
            st.dataframe(early[["invoice_no","invoice_date","dispatch_date","gap_days"]].head(20), use_container_width=True)

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _SalesCheck(BaseAuditCheck):
        name = "Sales Revenue Auditor"
        checklist_ref = "Ind AS 115 / SAP HO Sales"
        sap_tcode_standard_alt = "VF05 / VA05"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _SalesCheck()
    log_df = df.head(100).copy()
    log_df["vendor_name"] = log_df.get(cust_col, "Unknown")
    log_df["flag_reason"] = "Sales/revenue anomaly"
    log_df["risk_band"] = "HIGH"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Sales & Revenue", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 Draft findings staged for auditor confirmation")
