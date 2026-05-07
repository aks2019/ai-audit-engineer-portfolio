import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck

st.title("🔗 Related-Party Transactions Monitor")
st.caption("Vendor Mgmt B.3–B.8 | SAP: FK03 | NetworkX graph analysis")

uploaded = st.file_uploader("Upload Vendor Master (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} vendors")

    with st.expander("🔧 Column Mapping"):
        pan_col = st.selectbox("PAN", ["None"]+list(df.columns))
        bank_col = st.selectbox("Bank Account", ["None"]+list(df.columns))
        addr_col = st.selectbox("Address", ["None"]+list(df.columns))
        name_col = st.selectbox("Vendor Name", df.columns)
        rp_flag = st.selectbox("Related Party Flag", ["None"]+list(df.columns))
        amt_col = st.selectbox("Total Spend (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={name_col:"vendor_name"})
    if rp_flag != "None":
        df = df.rename(columns={rp_flag:"related_party"})
    else:
        df["related_party"] = 0

    # Duplicate PAN / Bank / Address
    flags = []
    if pan_col != "None":
        dup_pan = df[df.duplicated(pan_col, keep=False)]
        if not dup_pan.empty:
            flags.append(f"Duplicate PAN: {len(dup_pan)} vendors (B.3)")
    if bank_col != "None":
        dup_bank = df[df.duplicated(bank_col, keep=False)]
        if not dup_bank.empty:
            flags.append(f"Duplicate Bank Account: {len(dup_bank)} vendors (B.3)")
    if addr_col != "None":
        dup_addr = df[df.duplicated(addr_col, keep=False)]
        if not dup_addr.empty:
            flags.append(f"Duplicate Address: {len(dup_addr)} vendors (B.3)")
    for f in flags:
        st.warning(f)

    # Concentration
    if amt_col != "None":
        total = df[amt_col].sum()
        rp_total = df[df["related_party"]==1][amt_col].sum()
        pct = rp_total / total * 100 if total else 0
        st.metric("Related-Party % of Total Procurement", f"{pct:.1f}%")
        if pct > 10:
            st.warning(f"Related-party concentration >10% — Board approval required (Companies Act Sec 188)")

    # NetworkX graph
    try:
        import networkx as nx
        G = nx.Graph()
        for _, row in df.iterrows():
            G.add_node(row["vendor_name"], related=row.get("related_party",0))
        # Connect vendors sharing PAN
        if pan_col != "None":
            for pan, group in df.groupby(pan_col):
                names = group["vendor_name"].tolist()
                for i in range(len(names)):
                    for j in range(i+1, len(names)):
                        G.add_edge(names[i], names[j], reason="Same PAN")
        st.metric("Graph Nodes", G.number_of_nodes())
        st.metric("Graph Edges (shared attributes)", G.number_of_edges())
    except Exception as e:
        st.info(f"NetworkX graph skipped: {e}")

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _RPCheck(BaseAuditCheck):
        name = "Related Party Monitor"
        checklist_ref = "Vendor Mgmt B.3–B.8"
        sap_tcode_standard_alt = "FK03"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _RPCheck()
    if flags:
        log_df = df.head(100).copy()
        log_df["flag_reason"] = "Related-party anomaly detected"
        log_df["risk_band"] = "HIGH"
        checker.log_to_db(log_df, area="Related Party", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        # ── Stage Findings for Draft Review ──
        from utils.audit_db import stage_findings as _stage_findings
        _staged = _stage_findings(
            log_df,
            module_name="Related Party Monitor",
            run_id=run_id,
            period=datetime.utcnow().strftime("%Y-%m"),
            source_file_name=getattr(uploaded_file, "name", "manual") if 'uploaded_file' in locals() else "manual",
        )
        st.info(f"📋 {_staged} exception(s) staged for your review.")
        st.session_state.draft_run_id = run_id
        st.caption(f"📝 Findings logged to audit.db")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = df if 'df' in locals() and df is not None and not df.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "rpm",
            flagged_df=flagged_rag_df,
            module_name="Related Party Monitor"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("rpm", "Related Party Monitor")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
