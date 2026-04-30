import streamlit as st
import pandas as pd
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import load_tb_raw, llm_draft_financial_statements, generate_financial_audit_report
from datetime import datetime

st.title("📊 SAP Financial Statement Auditor")
st.caption("LLM-Powered (Manufacturing + Trading + P&L + BS + Cash Flow) | Zero Hardcoding | RAG Audit")

uploaded_tb = st.file_uploader("Upload Current SAP Trial Balance (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_tb:
    with st.spinner("Loading TB + LLM drafting full statements (Manufacturing + Trading + P&L + BS + Cash Flow)..."):
        raw_df = load_tb_raw(uploaded_tb)
        drafted = llm_draft_financial_statements(raw_df)
        
        if "error" in drafted:
            st.error("LLM JSON parse failed — showing raw output for debugging")
            st.code(drafted["raw_llm_output"], language="text")
        else:
            st.success("✅ LLM-drafted statements ready")
    
    # Manufacturing Account
    if "manufacturing" in drafted:
        st.subheader("Manufacturing Account")
        mfg_df = pd.DataFrame([drafted["manufacturing"]]).T.reset_index()
        mfg_df.columns = ["Particulars", "Amount (₹)"]
        st.dataframe(mfg_df.round(2), use_container_width=True, hide_index=True)
    
    # Trading Account
    if "trading" in drafted:
        st.subheader("Trading Account")
        trading_df = pd.DataFrame([drafted["trading"]]).T.reset_index()
        trading_df.columns = ["Particulars", "Amount (₹)"]
        st.dataframe(trading_df.round(2), use_container_width=True, hide_index=True)
    
    # P&L
    if "pl" in drafted:
        st.subheader("Profit & Loss Account")
        pl_df = pd.DataFrame([drafted["pl"]]).T.reset_index()
        pl_df.columns = ["Particulars", "Amount (₹)"]
        st.dataframe(pl_df.round(2), use_container_width=True, hide_index=True)
    
    # Balance Sheet
    if "bs" in drafted:
        st.subheader("Balance Sheet")
        bs_df = pd.DataFrame([drafted["bs"]]).T.reset_index()
        bs_df.columns = ["Particulars", "Amount (₹)"]
        st.dataframe(bs_df.round(2), use_container_width=True, hide_index=True)
    
    # Cash Flow (approx)
    if "cash_flow_approx" in drafted:
        st.subheader("Cash Flow Statement (Approximate from TB changes)")
        cf_df = pd.DataFrame([drafted["cash_flow_approx"]]).T.reset_index()
        cf_df.columns = ["Particulars", "Amount (₹)"]
        st.dataframe(cf_df.round(2), use_container_width=True, hide_index=True)
    
    # Major Heads
    if "major_heads" in drafted:
        st.subheader("📋 Major Accounting Heads Breakdown")
        major_df = pd.DataFrame(drafted["major_heads"])
        st.dataframe(major_df, use_container_width=True, hide_index=True)
    
    if st.button("🔍 Generate RAG Audit Report (Full Statements + Policy Check)", type="primary", use_container_width=True):
        with st.spinner("Running hybrid pgvector RAG..."):
            result = generate_financial_audit_report(drafted)
            st.markdown("### Audit-Ready Executive Summary")
            st.markdown(result["audit_summary"])
            st.caption(f"Audit log hash: `{result['log_hash']}` | Citations: {len(result['citations'])}")
            
            with st.expander("📚 Sources & References"):
                for cit in result["citations"]:
                    st.markdown(f"- {cit}")
            
            st.download_button("📥 Download Full Audit Report JSON", 
                               data=json.dumps(result, indent=2), file_name=f"fs_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.json")