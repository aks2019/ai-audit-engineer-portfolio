import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db, load_findings, record_kpi, get_kpis

st.title("📊 Audit KPI Dashboard")
st.caption("Efficiency metrics | Auditor productivity | Cost per hour | Closure trends")

init_audit_db()
findings = load_findings()

if findings.empty:
    st.info("No findings yet. Run detection modules to populate KPIs.")
else:
    # Auto-compute and store KPIs for current period
    period = datetime.utcnow().strftime("%Y-%m")
    total = len(findings)
    open_count = len(findings[findings["status"] == "Open"])
    closed_count = len(findings[findings["status"].isin(["Closed","Verified"])])
    avg_days = findings["days_to_close"].mean() if "days_to_close" in findings.columns else 0
    critical = len(findings[findings["risk_band"] == "CRITICAL"])

    record_kpi("total_findings", total, period)
    record_kpi("open_findings", open_count, period)
    record_kpi("closed_findings", closed_count, period)
    record_kpi("avg_days_to_close", avg_days, period)
    record_kpi("critical_findings", critical, period)

    # Display KPI cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Findings", total)
    c2.metric("Open", open_count)
    c3.metric("Closed", closed_count)
    c4.metric("Avg Days to Close", f"{avg_days:.1f}")
    c5.metric("Critical", critical)

    # Trend over periods
    kpi_df = get_kpis()
    if not kpi_df.empty:
        st.subheader("📈 KPI Trends")
        trend = kpi_df[kpi_df["metric_name"].isin(["total_findings","closed_findings","critical_findings"])]
        fig = px.line(trend, x="recorded_at", y="metric_value", color="metric_name",
                      title="Audit KPI Trends Over Time")
        st.plotly_chart(fig, use_container_width=True)

    # Closure rate by area
    st.subheader("✅ Closure Rate by Area")
    closure = findings.groupby("area").agg(
        total=("id","count"),
        closed=("status", lambda x: (x.isin(["Closed","Verified"])).sum())
    ).reset_index()
    closure["closure_rate"] = closure["closed"] / closure["total"] * 100
    fig2 = px.bar(closure, x="area", y="closure_rate", title="Closure Rate % by Area", color="closure_rate")
    st.plotly_chart(fig2, use_container_width=True)

    # Findings per month
    if "finding_date" in findings.columns:
        findings["finding_date"] = pd.to_datetime(findings["finding_date"], errors="coerce")
        monthly = findings.groupby(findings["finding_date"].dt.to_period("M")).size().reset_index(name="count")
        monthly["finding_date"] = monthly["finding_date"].astype(str)
        fig3 = px.bar(monthly, x="finding_date", y="count", title="Findings per Month")
        st.plotly_chart(fig3, use_container_width=True)
