import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_industry_profile

st.title("💰 Customer Receivables & Bad Debt Detector")
st.caption("Depot 5 / SAP HO 15 | SAP: FBL5N / S_ALR_87012197")

uploaded = st.file_uploader("Upload Customer Outstanding (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} customer records")

    with st.expander("🔧 Column Mapping"):
        amt_col = st.selectbox("Outstanding Amount", df.columns)
        days_col = st.selectbox("Days Overdue", df.columns)
        cust_col = st.selectbox("Customer Name", df.columns)
        limit_col = st.selectbox("Credit Limit (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={amt_col:"amount", days_col:"days_overdue", cust_col:"customer_name"})
    if limit_col != "None":
        df = df.rename(columns={limit_col:"credit_limit"})
        df["limit_breach"] = df["amount"] > df["credit_limit"]
    else:
        df["credit_limit"] = 0
        df["limit_breach"] = False

    profile = get_industry_profile("manufacturing_fmcg")
    critical_days = profile.get("thresholds", {}).get("days_overdue_critical", 60)

    df["opportunity_cost"] = df["amount"] * 0.12 / 365 * df["days_overdue"]
    critical = df[df["days_overdue"] > critical_days]
    limit_breach = df[df["limit_breach"]]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Outstanding", f"{df['amount'].sum():,.0f} ₹")
    col2.metric(f">{critical_days} Days Critical", f"{len(critical):,}")
    col3.metric("Opportunity Cost (12%)", f"{df['opportunity_cost'].sum():,.0f} ₹")

    if not critical.empty:
        st.subheader("🔴 Critical Overdue Customers")
        st.dataframe(critical[["customer_name","amount","days_overdue","opportunity_cost"]].nlargest(20,"amount"), use_container_width=True)

    if not limit_breach.empty:
        st.subheader("⚠️ Credit Limit Breaches")
        st.dataframe(limit_breach[["customer_name","amount","credit_limit"]], use_container_width=True)

    # XGBoost bad debt classifier
    if len(df) >= 20:
        try:
            from xgboost import XGBClassifier
            X = df[["amount","days_overdue"]].fillna(0)
            y = (df["days_overdue"] > critical_days).astype(int)
            xgb = XGBClassifier(n_estimators=100, max_depth=3, random_state=42, eval_metric="logloss", use_label_encoder=False)
            xgb.fit(X, y)
            df["bad_debt_prob"] = xgb.predict_proba(X)[:,1]
            top_risk = df.nlargest(10, "bad_debt_prob")
            st.subheader("🤖 Top 10 Bad Debt Risk (XGBoost)")
            st.dataframe(top_risk[["customer_name","amount","days_overdue","bad_debt_prob"]], use_container_width=True)
        except Exception as e:
            st.info(f"XGBoost skipped: {e}")

    # Log to SQLite
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _ReceivablesCheck(BaseAuditCheck):
        name = "Receivables Bad Debt"
        checklist_ref = "SAP Depot 5 / HO 15"
        sap_tcode_standard_alt = "FBL5N / S_ALR_87012197"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _ReceivablesCheck()
    log_df = critical.head(100).copy()
    log_df["vendor_name"] = log_df["customer_name"]
    log_df["flag_reason"] = f"Overdue >{critical_days} days"
    log_df["risk_band"] = "HIGH"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Receivables", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 {len(log_df)} draft findings staged for auditor confirmation")
