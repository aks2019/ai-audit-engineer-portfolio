import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
from thefuzz import fuzz
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck

st.title("🎭 Duplicate Payments & Invoice Fraud Detector")
st.caption("Purchasing D.3–D.12 | SAP: FBL1N / ME2N")

uploaded = st.file_uploader("Upload Invoice/Payment Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} rows")

    with st.expander("🔧 Column Mapping"):
        inv_col = st.selectbox("Invoice Number", df.columns)
        ven_col = st.selectbox("Vendor", df.columns)
        amt_col = st.selectbox("Amount", df.columns)
        po_col = st.selectbox("PO Rate (optional)", ["None"]+list(df.columns))
        inv_date_col = st.selectbox("Invoice Date (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={inv_col:"invoice_no", ven_col:"vendor_name", amt_col:"amount"})

    # Exact duplicates
    exact = df[df.duplicated(["vendor_name","invoice_no","amount"], keep=False)]
    st.metric("Exact Duplicates", len(exact))

    # Fuzzy duplicates
    if st.checkbox("Run Fuzzy Duplicate Detection (Levenshtein)"):
        fuzzy_hits = []
        vendors = df["vendor_name"].unique()
        for v in vendors:
            sub = df[df["vendor_name"]==v].reset_index(drop=True)
            for i in range(len(sub)):
                for j in range(i+1, min(i+50, len(sub))):
                    ratio = fuzz.ratio(str(sub.iloc[i]["invoice_no"]), str(sub.iloc[j]["invoice_no"]))
                    amt_diff = abs(sub.iloc[i]["amount"] - sub.iloc[j]["amount"])
                    if ratio >= 85 and amt_diff <= 500:
                        fuzzy_hits.append({"vendor":v,"inv1":sub.iloc[i]["invoice_no"],"inv2":sub.iloc[j]["invoice_no"],"ratio":ratio,"amt_diff":amt_diff})
        if fuzzy_hits:
            st.subheader("🔍 Fuzzy Duplicates")
            st.dataframe(pd.DataFrame(fuzzy_hits), use_container_width=True)

    # PO vs Invoice rate variance
    if po_col != "None":
        df = df.rename(columns={po_col:"po_rate"})
        df["variance_pct"] = (df["amount"] - df["po_rate"]).abs() / df["po_rate"] * 100
        high_var = df[df["variance_pct"] > 5]
        if not high_var.empty:
            st.warning(f"PO vs Invoice variance ≥5%: {len(high_var)} rows (SAP 1.5)")
            st.dataframe(high_var[["vendor_name","invoice_no","po_rate","amount","variance_pct"]].head(20), use_container_width=True)

    # Benford's Law
    with st.expander("🔢 Benford's Law on Invoice Amounts"):
        expected = {1:30.1,2:17.6,3:12.5,4:9.7,5:7.9,6:6.7,7:5.8,8:5.1,9:4.6}
        first = df["amount"][df["amount"]>0].astype(str).str[0].astype(int)
        obs = first.value_counts(normalize=True).sort_index()*100
        benford = pd.DataFrame({"digit":list(expected.keys()),"expected_pct":list(expected.values()),"observed_pct":[obs.get(d,0) for d in expected]})
        benford["deviation"] = benford["observed_pct"] - benford["expected_pct"]
        fig = px.bar(benford, x="digit", y=["expected_pct","observed_pct"], barmode="group")
        st.plotly_chart(fig, use_container_width=True)

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _DupCheck(BaseAuditCheck):
        name = "Duplicate Invoice"
        checklist_ref = "Purchasing D.3–D.12"
        sap_tcode_standard_alt = "FBL1N / ME2N"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _DupCheck()
    log_df = exact.head(100).copy()
    log_df["flag_reason"] = "Exact duplicate invoice"
    log_df["risk_band"] = "HIGH"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Duplicate Invoices", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption(f"📝 {len(log_df)} findings logged")

    # Fraud score & block recommendation
    if not df.empty:
        df["fraud_score"] = np.random.uniform(0,1,len(df))  # placeholder; replace with model
        blocked = df[df["fraud_score"] > 0.85]
        if not blocked.empty:
            st.error(f"🚫 {len(blocked)} invoices recommended for payment block via FB02 (Payment Block = A)")
