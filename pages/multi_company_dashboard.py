import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db, load_findings, record_kpi

st.title("🏢 Multi-Company & Multi-Location Dashboard")
st.caption("Group-level consolidated view | Subsidiary / Plant filtering")

init_audit_db()
findings = load_findings()

if findings.empty:
    st.info("No findings yet. Run detection modules with company_code populated.")
else:
    # Company selector
    companies = findings["company_code"].dropna().unique().tolist()
    plants = findings["plant_code"].dropna().unique().tolist()

    selected_companies = st.multiselect("Company Code", companies, default=companies)
    selected_plants = st.multiselect("Plant Code", plants, default=plants)

    filtered = findings[
        findings["company_code"].isin(selected_companies) &
        findings["plant_code"].isin(selected_plants)
    ]

    st.metric("Filtered Findings", len(filtered))

    # Group-level summary
    summary = filtered.groupby(["company_code","risk_band"]).size().reset_index(name="count")
    fig = px.bar(summary, x="company_code", y="count", color="risk_band",
                 title="Findings by Company & Risk Band", barmode="group")
    st.plotly_chart(fig, use_container_width=True)

    # Plant-level heat map
    if not filtered.empty and "plant_code" in filtered.columns:
        plant_summary = filtered.groupby(["plant_code","area"]).size().reset_index(name="count")
        fig2 = px.density_heatmap(plant_summary, x="plant_code", y="area", z="count",
                                  title="Plant vs Audit Area Heat Map")
        st.plotly_chart(fig2, use_container_width=True)

    # Amount at risk by company
    amt_summary = filtered.groupby("company_code")["amount_at_risk"].sum().reset_index()
    fig3 = px.pie(amt_summary, names="company_code", values="amount_at_risk",
                  title="Amount at Risk Distribution by Company")
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(filtered, use_container_width=True, hide_index=True)
