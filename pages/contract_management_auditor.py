import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_industry_profile
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "cnt"

st.title("📜 Contract & AMC Management Auditor")
st.caption("Purchasing A.1–A.8 | Contract Labour Act 1970 | SAP: ME33K / ME2K")
render_engagement_selector(PAGE_KEY)

uploaded = st.file_uploader("Upload Contract Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} contracts")

    with st.expander("🔧 Column Mapping"):
        contract_col = st.selectbox("Contract No", df.columns)
        vendor_col = st.selectbox("Vendor", df.columns)
        start_col = st.selectbox("Start Date", df.columns)
        end_col = st.selectbox("End Date", df.columns)
        value_col = st.selectbox("Contract Value", df.columns)
        last_pay_col = st.selectbox("Last Payment Date", ["None"]+list(df.columns))
        ld_rate_col = st.selectbox("LD Rate % (optional)", ["None"]+list(df.columns))
        ld_rec_col = st.selectbox("LD Recovered (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={contract_col:"contract_no", vendor_col:"vendor_name", start_col:"start_date",
                            end_col:"end_date", value_col:"contract_value"})
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    today = pd.Timestamp.today()
    df["days_to_expiry"] = (df["end_date"] - today).dt.days

    # Expiring
    expiring = df[df["days_to_expiry"].between(0, 90)]
    st.metric("Contracts Expiring in 90 Days", len(expiring))
    if not expiring.empty:
        st.dataframe(expiring[["contract_no","vendor_name","end_date","days_to_expiry"]], use_container_width=True)

    # Post-expiry payment
    if last_pay_col != "None":
        df["last_payment_date"] = pd.to_datetime(df[last_pay_col], errors="coerce")
        post = df[df["last_payment_date"] > df["end_date"]]
        if not post.empty:
            st.error(f"Payment after expiry: {len(post)} contracts — unauthorized continuation (Purchasing A.4)")
            st.dataframe(post[["contract_no","vendor_name","end_date","last_payment_date"]], use_container_width=True)

    # LD non-recovery
    if ld_rate_col != "None" and ld_rec_col != "None":
        df["ld_rate_pct"] = pd.to_numeric(df[ld_rate_col], errors="coerce").fillna(0)
        df["ld_recovered"] = pd.to_numeric(df[ld_rec_col], errors="coerce").fillna(0)
        # Simplified: assume all contracts have some delay for demo
        df["ld_due"] = df["contract_value"] * df["ld_rate_pct"] / 100
        ld_short = df[df["ld_recovered"] < df["ld_due"] * 0.9]
        if not ld_short.empty:
            st.warning(f"LD shortfall: {len(ld_short)} contracts (Purchasing A.7)")
            st.dataframe(ld_short[["contract_no","vendor_name","ld_due","ld_recovered"]].head(20), use_container_width=True)

    # Concentration
    profile = get_industry_profile("manufacturing_fmcg")
    conc_thresh = profile.get("thresholds",{}).get("amc_vendor_concentration_pct",40)
    total = df["contract_value"].sum()
    top_vendor = df.groupby("vendor_name")["contract_value"].sum().nlargest(1)
    if not top_vendor.empty:
        pct = top_vendor.iloc[0] / total * 100
        st.metric("Top Vendor Concentration", f"{pct:.1f}%")
        if pct > conc_thresh:
            st.warning(f"Vendor concentration >{conc_thresh}% — diversification review needed")

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _ContractCheck(BaseAuditCheck):
        name = "Contract Management"
        checklist_ref = "Purchasing A.1–A.8"
        sap_tcode_standard_alt = "ME33K / ME2K"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _ContractCheck()
    log_df = df.head(100).copy()
    log_df["flag_reason"] = "Contract management anomaly"
    log_df["risk_band"] = "MEDIUM"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Contracts", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        # ── Stage Findings for Draft Review ──
        from utils.audit_db import stage_findings as _stage_findings
        _staged = _stage_findings(
            log_df,
            module_name="Contract Management Auditor",
            run_id=run_id,
            period=datetime.utcnow().strftime("%Y-%m"),
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.info(f"📋 {_staged} exception(s) staged for your review.")
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.caption(f"📝 Findings logged")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = df if 'df' in locals() and df is not None and not df.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "cnt",
            flagged_df=flagged_rag_df,
            module_name="Contract Management Auditor"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("cnt", "Contract Management Auditor")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
