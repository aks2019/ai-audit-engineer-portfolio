import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import load_findings, compute_risk_score, init_audit_db
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

st.title("⚠️ Audit Risk Register & Priority Mapping")
st.caption("5×5 Risk Matrix | SQLite aggregation | Quarterly priority plan")

PAGE_KEY = "risk_register"
render_engagement_selector(PAGE_KEY)
active_engagement_id = get_active_engagement_id(PAGE_KEY)
if active_engagement_id is None:
    st.info("Create an audit engagement first (Audit Session Manager), then come back to view the risk register.")
    st.stop()

init_audit_db()
findings = load_findings(engagement_id=active_engagement_id)

if findings.empty:
    st.info("No findings in audit.db yet. Run detection modules to populate.")
else:
    # Compute risk scores
    area_counts = findings.groupby("area").size().to_dict()
    findings["recurrence"] = findings["area"].map(area_counts)
    findings[["risk_score","risk_band_calc"]] = findings.apply(
        lambda r: pd.Series(compute_risk_score(r["amount_at_risk"], r["recurrence"])), axis=1
    )

    # 5×5 Heat Map
    st.subheader("5×5 Risk Heat Map")
    heat = findings.groupby(["area","risk_band_calc"]).size().reset_index(name="count")
    fig = px.density_heatmap(heat, x="area", y="risk_band_calc", z="count",
                              color_continuous_scale="Reds", title="Risk by Area & Band")
    st.plotly_chart(fig, use_container_width=True)

    # Ranked table
    st.subheader("Risk-Ranked Findings")
    st.dataframe(findings.sort_values("risk_score", ascending=False)[["area","checklist_ref","finding","amount_at_risk","risk_band_calc","status"]],
                 use_container_width=True, hide_index=True)

    # Quarterly priority
    st.subheader("Quarterly Priority Plan")
    plan = findings.groupby("risk_band_calc")["area"].apply(lambda x: ", ".join(x.unique())).reset_index()
    plan["quarter"] = plan["risk_band_calc"].map({"CRITICAL":"Q1","HIGH":"Q2","MEDIUM":"Q3","LOW":"Q4"})
    st.dataframe(plan, use_container_width=True, hide_index=True)

    # Download
    csv = findings.to_csv(index=False).encode()
    st.download_button("📥 Download Risk Register CSV", csv, "risk_register.csv", "text/csv")
