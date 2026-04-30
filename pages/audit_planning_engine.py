import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import _get_llm, get_free_form_chain
from utils.audit_db import load_findings

st.title("📅 Predictive Risk-Based Audit Planning Engine")
st.caption("Checklist automation coverage | Annual audit plan generator")

# Checklist coverage report
st.subheader("📋 Checklist Automation Coverage")
coverage = pd.DataFrame([
    {"checklist_item": "Vendor Payments — Anomaly", "status": "Automated", "project": "P1"},
    {"checklist_item": "Vendor Payments — Duplicate", "status": "Automated", "project": "P10"},
    {"checklist_item": "Inventory — Slow-moving", "status": "Automated", "project": "P11"},
    {"checklist_item": "Fixed Assets — CWIP >12mo", "status": "Automated", "project": "P12"},
    {"checklist_item": "Payroll — Ghost Employee", "status": "Automated", "project": "P18"},
    {"checklist_item": "Sales — Credit Note", "status": "Automated", "project": "P19"},
    {"checklist_item": "ITGC — SoD Conflict", "status": "Automated", "project": "P20"},
    {"checklist_item": "Contract — LD Non-recovery", "status": "Automated", "project": "P21"},
    {"checklist_item": "BRS — Stale Cheques", "status": "Automated", "project": "P5"},
    {"checklist_item": "GST — GSTR-2A Mismatch", "status": "Automated", "project": "P8"},
])
st.dataframe(coverage, use_container_width=True, hide_index=True)
auto_pct = len(coverage[coverage["status"]=="Automated"]) / len(coverage) * 100
st.progress(auto_pct/100, text=f"{auto_pct:.0f}% of displayed items automated")

# Annual plan generator
st.subheader("🗓️ Annual Audit Plan (LLM-Assisted)")
findings = load_findings()
if findings.empty:
    st.info("Run detection modules first to generate risk-based plan.")
else:
    summary = findings.groupby("area").agg({"amount_at_risk":"sum","id":"count"}).reset_index()
    summary.columns = ["area","amount_at_risk","finding_count"]
    summary = summary.sort_values("amount_at_risk", ascending=False)
    st.dataframe(summary, use_container_width=True, hide_index=True)

    if st.button("🤖 Draft Annual Plan with LLM"):
        with st.spinner("Querying RAG Bot..."):
            ctx = summary.to_string()
            chain = get_free_form_chain()
            prompt = """Draft a risk-based annual internal audit plan for an Indian FMCG company.
Format: Audit Area | Risk Score | Quarter | Audit Days | Key Risks | Checklist Ref | SAP T-Code | Standard Alt
Use the following risk data:"""
            response = chain.invoke({"context": ctx, "question": prompt})
            st.markdown(response.content)
