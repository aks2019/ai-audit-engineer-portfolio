import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
from sklearn.neural_network import MLPRegressor

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_depreciation_rate, load_compliance_calendar

st.title("🏭 Fixed Asset Addition & Depreciation Auditor")
st.caption("Fixed Assets A.1–A.13, B.1–B.41 | SAP: AS03 / AFAB")

uploaded = st.file_uploader("Upload Asset Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} assets")

    with st.expander("🔧 Column Mapping"):
        desc_col = st.selectbox("Asset Description", df.columns)
        cost_col = st.selectbox("Acquisition Cost", df.columns)
        acc_dep_col = st.selectbox("Accumulated Depreciation", df.columns)
        rate_col = st.selectbox("Applied Depreciation Rate %", df.columns)
        asset_class_col = st.selectbox("Asset Class", ["None"]+list(df.columns))
        date_col = st.selectbox("Acquisition Date (optional)", ["None"]+list(df.columns))
        approved_col = st.selectbox("Capex Approved (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={desc_col:"asset_description", cost_col:"cost", acc_dep_col:"accumulated_depreciation", rate_col:"applied_rate"})
    cal = load_compliance_calendar()

    # Revenue vs capital
    rev_keywords = cal.get("fixed_assets",{}).get("revenue_keywords",[])
    df["revenue_flag"] = df["asset_description"].astype(str).str.lower().apply(lambda x: any(k in x for k in rev_keywords))
    rev = df[df["revenue_flag"]]
    if not rev.empty:
        st.warning(f"Revenue-like keyword detected in {len(rev)} assets — capitalisation review needed")
        st.dataframe(rev[["asset_description","cost"]].head(20), use_container_width=True)

    # Depreciation rate variance
    if asset_class_col != "None":
        df["expected_rate"] = df[asset_class_col].apply(lambda c: get_depreciation_rate(str(c)))
        df["rate_variance"] = (df["applied_rate"] - df["expected_rate"]).abs()
        var = df[df["rate_variance"] > 0.5]
        if not var.empty:
            st.warning(f"Depreciation rate variance >0.5%: {len(var)} assets")
            st.dataframe(var[["asset_description",asset_class_col,"applied_rate","expected_rate"]].head(20), use_container_width=True)

    # Unapproved capex
    if approved_col != "None":
        thresh = cal.get("fixed_assets",{}).get("capex_approval_threshold",100000)
        unapproved = df[(df[approved_col] != 1) & (df["cost"] > thresh)]
        if not unapproved.empty:
            st.error(f"Unapproved capex >₹{thresh:,}: {len(unapproved)} assets (Fixed Assets B.4)")

    # Autoencoder anomaly
    num_cols = ["cost","accumulated_depreciation","applied_rate"]
    num_cols = [c for c in num_cols if c in df.columns]
    if len(num_cols) >= 2 and len(df) >= 10:
        X = df[num_cols].fillna(0)
        ae = MLPRegressor(hidden_layer_sizes=(8,4,8), max_iter=500, random_state=42)
        ae.fit(X, X)
        recon = ae.predict(X)
        mse = np.mean((X - recon)**2, axis=1)
        df["autoencoder_mse"] = mse
        top_ae = df.nlargest(10, "autoencoder_mse")
        st.subheader("🤖 Autoencoder Anomalies")
        st.dataframe(top_ae[["asset_description"]+num_cols+["autoencoder_mse"]], use_container_width=True)

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _FACheck(BaseAuditCheck):
        name = "Fixed Asset Auditor"
        checklist_ref = "Fixed Assets A.1–A.13"
        sap_tcode_standard_alt = "AS03 / AFAB"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _FACheck()
    log_df = df.head(100).copy()
    log_df["vendor_name"] = log_df["asset_description"]
    log_df["flag_reason"] = "Fixed asset anomaly"
    log_df["risk_band"] = "MEDIUM"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Fixed Assets", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 Draft findings staged for auditor confirmation")
