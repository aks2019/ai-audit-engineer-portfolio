import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import load_findings, init_audit_db
from utils.rag_engine import _get_llm, get_free_form_chain

st.title("📑 Audit Report Center + MIS Audit Report")
st.caption("Centralized reports | CFO-ready MIS | LLM synthesis")

tab1, tab2 = st.tabs(["Report Center", "MIS Audit Report"])

with tab1:
    init_audit_db()
    findings = load_findings()
    if findings.empty:
        st.info("No findings yet.")
    else:
        st.subheader("Centralized Findings Timeline")
        timeline = findings.groupby(["area","finding_date"]).size().reset_index(name="count")
        st.dataframe(timeline, use_container_width=True, hide_index=True)

        if st.button("🤖 Synthesize Combined Executive Summary"):
            with st.spinner("LLM drafting..."):
                ctx = findings.head(50).to_string()
                chain = get_free_form_chain()
                response = chain.invoke({"context": ctx, "question": "Draft a combined executive summary for the audit committee."})
                st.markdown(response.content)

        # Excel download
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for area in findings["area"].unique():
                findings[findings["area"]==area].to_excel(writer, sheet_name=area[:31], index=False)
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
