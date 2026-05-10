import streamlit as st
import pandas as pd
import re
from datetime import datetime
import sys
from pathlib import Path
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import load_findings, init_audit_db
from utils.rag_engine import _get_llm, get_free_form_chain


def _unique_excel_sheet_name(area: object, used: set[str]) -> str:
    """Build a non-empty, Excel-legal, unique sheet title (max 31 chars)."""
    if pd.isna(area):
        base = "Unnamed"
    else:
        t = str(area).strip()
        base = t if t else "Unnamed"
    safe = re.sub(r"[\[\]:*?/\\]", "_", base)
    safe = (safe[:31]).strip() or "Unnamed"
    name = safe
    n = 2
    while name in used:
        suffix = f"_{n}"
        max_base = max(0, 31 - len(suffix))
        name = (safe[:max_base] + suffix) if max_base else f"Sheet{n}"[:31]
        n += 1
    used.add(name)
    return name


st.title("📑 Audit Report Center + MIS Audit Report")
st.caption("Centralized reports | CFO-ready MIS | LLM synthesis")

tab1, tab2 = st.tabs(["Report Center", "MIS Audit Report"])

with tab1:
    init_audit_db()
    findings = load_findings()
    if findings.empty:
        st.info("No findings yet. Run detection on any page and confirm findings to see them here.")
    else:
        st.subheader("Centralized Findings Timeline")
        
        # Handle missing/null finding_date gracefully
        if "finding_date" not in findings.columns:
            st.warning("finding_date column not found in audit_findings table.")
        else:
            # Filter out rows with null/empty finding_date
            valid_findings = findings[findings["finding_date"].notna() & (findings["finding_date"] != "")]
            
            if valid_findings.empty:
                st.info("No findings with valid dates found.")
            else:
                timeline = valid_findings.groupby(["area","finding_date"]).size().reset_index(name="count")
                timeline = timeline.sort_values("finding_date", ascending=False)
                st.dataframe(timeline, use_container_width=True, hide_index=True)
                
                # Show summary metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Confirmed Findings", len(valid_findings))
                col2.metric("Unique Areas", valid_findings["area"].nunique())
                col3.metric("Date Range", f"{valid_findings['finding_date'].min()} to {valid_findings['finding_date'].max()}" if len(valid_findings) > 0 else "N/A")

        if st.button("🤖 Synthesize Combined Executive Summary"):
            with st.spinner("LLM drafting..."):
                ctx = findings.head(50).to_string()
                chain = get_free_form_chain()
                response = chain.invoke({"context": ctx, "question": "Draft a combined executive summary for the audit committee."})
                st.markdown(response.content)

        # Excel download
        buf = BytesIO()
        used_sheet_names: set[str] = set()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for area in findings["area"].unique():
                sheet = _unique_excel_sheet_name(area, used_sheet_names)
                if pd.isna(area):
                    rows = findings[findings["area"].isna()]
                else:
                    rows = findings[findings["area"] == area]
                rows.to_excel(writer, sheet_name=sheet, index=False)
        st.download_button("📥 Download Excel Workbook", buf.getvalue(), "audit_reports.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab2:
    st.subheader("MIS Audit Report (CFO-Ready)")
    period = st.selectbox("Period", ["Q1","Q2","Q3","Q4","H1","H2","Annual"])
    if st.button("Generate MIS Report"):
        findings = load_findings(risk_bands=["HIGH","CRITICAL"])
        if findings.empty:
            st.info("No HIGH/CRITICAL findings for selected period.")
        else:
            with st.spinner("LLM drafting 6-section MIS report..."):
                ctx = findings.to_string()
                prompt = f"""Draft a CFO-ready MIS Audit Report for period {period}.
Sections:
1. Executive Summary (3-4 lines)
2. Risk Summary Table
3. Compliance Gap Summary (GST/TDS/PF/ESI)
4. Top 10 Critical Observations
5. Trend Analysis
6. Recommendations"""
                chain = get_free_form_chain()
                response = chain.invoke({"context": ctx, "question": prompt})
                st.markdown(response.content)

                # PDF
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=letter)
                y = letter[1]-50
                c.drawString(50,y,"MIS Audit Report"); y-=30
                for line in response.content.split("\n")[:80]:
                    if y<50: c.showPage(); y=letter[1]-50
                    c.drawString(50,y,line[:90]); y-=15
                c.save()
                st.download_button("📥 Download MIS PDF", buf.getvalue(), f"MIS_{period}.pdf", "application/pdf")
