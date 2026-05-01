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
from utils.compliance_loader import load_compliance_calendar

st.title("🏦 BRS Anomaly & Auto-Matching Agent")
st.caption("Bank Reconciliation + Treasury Checklist A.2, A.3, A.10, A.13, A.14e, A.20 | SAP: FF67 + FBL3N")

bank_file = st.file_uploader("Upload Bank Statement (CSV/Excel)", type=["csv","xlsx"], key="bank")
gl_file   = st.file_uploader("Upload GL Extract (CSV/Excel)", type=["csv","xlsx"], key="gl")

if bank_file and gl_file:
    bdf = pd.read_csv(bank_file) if bank_file.name.endswith(".csv") else pd.read_excel(bank_file)
    gdf = pd.read_excel(gl_file) if gl_file.name.endswith(".xlsx") else pd.read_csv(gl_file)
    st.success(f"Loaded Bank: {len(bdf):,} rows | GL: {len(gdf):,} rows")

    with st.expander("🔧 Column Mapping"):
        b_amount = st.selectbox("Bank Amount", bdf.columns, key="b_amt")
        b_date   = st.selectbox("Bank Date", bdf.columns, key="b_dt")
        b_narr   = st.selectbox("Bank Narration (optional)", ["None"]+list(bdf.columns), key="b_narr")
        g_amount = st.selectbox("GL Amount", gdf.columns, key="g_amt")
        g_date   = st.selectbox("GL Date", gdf.columns, key="g_dt")
        g_narr   = st.selectbox("GL Narration (optional)", ["None"]+list(gdf.columns), key="g_narr")

    bdf = bdf.rename(columns={b_amount:"amount", b_date:"date"})
    gdf = gdf.rename(columns={g_amount:"amount", g_date:"date"})
    bdf["date"] = pd.to_datetime(bdf["date"], errors="coerce")
    gdf["date"] = pd.to_datetime(gdf["date"], errors="coerce")

    with st.spinner("Auto-matching bank vs GL..."):
        matched = []
        unmatched_bank = []
        for _, brow in bdf.iterrows():
            hits = gdf[
                (gdf["amount"].abs() - abs(brow["amount"])).abs() <= 0.01
            ].copy()
            if not hits.empty:
                hits["day_diff"] = (hits["date"] - brow["date"]).dt.days.abs()
                best = hits.sort_values("day_diff").head(1)
                if not best.empty and best.iloc[0]["day_diff"] <= 3:
                    matched.append({"bank_amt": brow["amount"], "gl_amt": best.iloc[0]["amount"],
                                    "bank_date": brow["date"], "gl_date": best.iloc[0]["date"],
                                    "days_diff": best.iloc[0]["day_diff"]})
                    gdf = gdf.drop(best.index)
                    continue
            unmatched_bank.append(brow)
        unmatched_bank = pd.DataFrame(unmatched_bank)

    st.metric("Auto-Matched", len(matched))
    st.metric("Unmatched Bank Items", len(unmatched_bank))

    if not unmatched_bank.empty:
        st.subheader("⚠️ Unmatched Bank Items")
        st.dataframe(unmatched_bank, use_container_width=True)

        # Rules
        rules = []
        if not unmatched_bank.empty:
            cal = load_compliance_calendar()
            # Stale cheques >6 months
            unmatched_bank["age_days"] = (datetime.today() - unmatched_bank["date"]).dt.days
            stale = unmatched_bank[unmatched_bank["age_days"] > 180]
            if not stale.empty:
                rules.append(f"Stale cheques >6 months: {len(stale)} (Treasury A.13)")
            # Cash not deposited same day (A.20) — simplistic: amount > 50k and age > 0
            cash_delay = unmatched_bank[(unmatched_bank["amount"].abs() > 50000) & (unmatched_bank["age_days"] > 0)]
            if not cash_delay.empty:
                rules.append(f"Cash not deposited same day: {len(cash_delay)} (Treasury A.20)")
        for r in rules:
            st.warning(r)

        # IsolationForest on unmatched
        if len(unmatched_bank) >= 10:
            X = unmatched_bank[["amount"]].copy().fillna(0)
            iso = IsolationForest(contamination=0.05, random_state=42)
            unmatched_bank["anomaly_score"] = iso.fit_predict(X)
            high_risk = unmatched_bank[unmatched_bank["anomaly_score"] == -1]
            if not high_risk.empty:
                st.subheader("🚨 High-Risk Unmatched Items (IsolationForest)")
                st.dataframe(high_risk, use_container_width=True)

        # Log to SQLite
        init_audit_db()
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        class _BRSCheck(BaseAuditCheck):
            name = "BRS Reconciliation"
            checklist_ref = "Treasury A.2/A.3"
            sap_tcode_standard_alt = "FF67 / FBL3N"
            def detect(self, df: pd.DataFrame) -> pd.DataFrame:
                return df
        checker = _BRSCheck()
        log_df = unmatched_bank.head(100).copy()
        log_df["flag_reason"] = "Unmatched bank item"
        log_df["risk_band"] = "HIGH"
        if not log_df.empty:
            checker.log_to_db(log_df, area="Bank Reconciliation", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
            st.caption(f"📝 {len(log_df)} draft findings staged for auditor confirmation")
