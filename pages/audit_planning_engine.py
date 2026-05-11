import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import _get_llm, get_free_form_chain
from utils.audit_db import load_findings
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

st.title("📅 Predictive Risk-Based Audit Planning Engine")
st.caption("Checklist automation coverage | Annual audit plan generator")

PAGE_KEY = "audit_planning_engine"
render_engagement_selector(PAGE_KEY)
active_engagement_id = get_active_engagement_id(PAGE_KEY)
if active_engagement_id is None:
    st.info("Create an audit engagement first (Audit Session Manager), then come back to generate the plan.")
    st.stop()

# Checklist coverage report
st.subheader("📋 Checklist Automation Coverage")
conn = sqlite3.connect("data/audit.db")
coverage_raw = pd.read_sql_query(
    """
    SELECT
        module_name,
        MAX(area) as sample_area,
        MAX(checklist_ref) as sample_checklist_ref,
        SUM(CASE WHEN draft_status = 'Confirmed' THEN 1 ELSE 0 END) as confirmed_count,
        SUM(CASE WHEN draft_status = 'Draft' THEN 1 ELSE 0 END) as draft_count
    FROM draft_audit_findings
    WHERE engagement_id = ?
    GROUP BY module_name
    ORDER BY confirmed_count DESC, draft_count DESC
    """,
    conn,
    params=(active_engagement_id,),
)
conn.close()

if coverage_raw.empty:
    st.info("No draft/confirmed findings found for this engagement yet. Run detection modules and confirm findings first.")
    coverage = pd.DataFrame([], columns=["checklist_item", "status", "project"])
    auto_pct = 0
else:
    def _status(row):
        if row["confirmed_count"] > 0:
            return "Automated (Confirmed)"
        if row["draft_count"] > 0:
            return "Automated (Draft)"
        return "Manual"

    coverage = pd.DataFrame({
        "checklist_item": coverage_raw["module_name"],
        "status": coverage_raw.apply(_status, axis=1),
        "project": coverage_raw["sample_checklist_ref"].fillna(coverage_raw["module_name"]),
    })
    st.dataframe(coverage, use_container_width=True, hide_index=True)

    confirmed_modules = (coverage_raw["confirmed_count"] > 0).sum()
    auto_pct = confirmed_modules / max(len(coverage_raw), 1) * 100
    st.progress(auto_pct / 100, text=f"{auto_pct:.0f}% of detected modules are confirmed")

# Annual plan generator
st.subheader("🗓️ Annual Audit Plan (LLM-Assisted)")
findings = load_findings(engagement_id=active_engagement_id)
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
