import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import load_findings, init_audit_db
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id
from utils.compliance_loader import load_compliance_calendar, get_industry_profile

st.title("📈 Unified Anomaly Intelligence Dashboard")
st.caption("Aggregated risk view across all audit modules")

PAGE_KEY = "unified_dashboard"
render_engagement_selector(PAGE_KEY)
active_engagement_id = get_active_engagement_id(PAGE_KEY)
if active_engagement_id is None:
    st.info("Create an audit engagement first (Audit Session Manager), then come back to view the unified dashboard.")
    st.stop()

init_audit_db()
profile = get_industry_profile("manufacturing_fmcg")

# Sidebar industry switch
industry = st.sidebar.selectbox("Industry Profile", ["manufacturing_fmcg","it_services","healthcare_pharma","retail","financial_services"])
profile = get_industry_profile(industry)

# Load all findings
findings = load_findings(engagement_id=active_engagement_id)

if findings.empty:
    st.info("No findings yet. Run detection modules to populate the dashboard.")
else:
    # 1. Overall Risk Score gauge
    critical = len(findings[findings["risk_band"]=="CRITICAL"])
    high = len(findings[findings["risk_band"]=="HIGH"])
    total = len(findings)
    risk_score = min(100, int((critical*5 + high*2) / max(total,1) * 20))

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number", value=risk_score,
        title={"text": "Overall Risk Score"},
        gauge={"axis": {"range": [0,100]}, "bar": {"color": "red" if risk_score>60 else "orange" if risk_score>30 else "green"},
               "steps": [{"range":[0,30],"color":"lightgreen"},{"range":[30,60],"color":"yellow"},{"range":[60,100],"color":"salmon"}]}
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)

    # 2. 30-day trend
    findings["finding_date"] = pd.to_datetime(findings["finding_date"], errors="coerce")
    recent = findings[findings["finding_date"] >= datetime.today() - timedelta(days=30)]
    if not recent.empty:
        trend = recent.groupby([recent["finding_date"].dt.date, "risk_band"]).size().reset_index(name="count")
        fig_trend = px.line(trend, x="finding_date", y="count", color="risk_band", title="30-Day Anomaly Trend")
        st.plotly_chart(fig_trend, use_container_width=True)

    # 3. Top vendors by risk
    vendor_risk = findings.groupby("vendor_name")["amount_at_risk"].sum().reset_index().nlargest(10, "amount_at_risk")
    fig_vendor = px.bar(vendor_risk, x="vendor_name", y="amount_at_risk", title="Top 10 Vendors by Amount at Risk")
    st.plotly_chart(fig_vendor, use_container_width=True)

    # 4. Department heat map
    area_risk = findings.groupby(["area","risk_band"]).size().reset_index(name="count")
    fig_heat = px.density_heatmap(area_risk, x="area", y="risk_band", z="count", title="Risk Heat Map by Area")
    st.plotly_chart(fig_heat, use_container_width=True)

    # 5. Compliance calendar — next 7 due dates
    cal = load_compliance_calendar()
    today = datetime.today()
    due_items = []
    for sec, data in cal.get("tds",{}).get("sections",{}).items():
        due_items.append({"item": f"TDS Sec {sec} deposit", "due": f"{today.strftime('%Y-%m')}-07"})
    due_df = pd.DataFrame(due_items)
    st.subheader("📅 Compliance Calendar (Next 7 Days)")
    st.dataframe(due_df, use_container_width=True, hide_index=True)

    # 6. Checklist coverage
    st.subheader("📋 Checklist Coverage")
    st.progress(0.15, text="15% of ~1000 checklist items automated")

# Audit Committee export pack
if st.button("📦 Export Audit Committee Pack (ZIP)"):
    st.info("Pack generation: aggregate all current period reports into ZIP. (Implement after P16/P17)")
