import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_industry_profile
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "inv"

st.title("📦 Inventory Valuation & Slow-Moving Stock Detector")
render_engagement_selector(PAGE_KEY)
st.caption("Inventory Mgmt A.6–A.11 | SAP: MB52 + MB5M / MC46")

uploaded = st.file_uploader("Upload Inventory Extract (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} materials")

    with st.expander("🔧 Column Mapping"):
        mat_col = st.selectbox("Material Code", df.columns)
        qty_col = st.selectbox("Unrestricted Qty", df.columns)
        val_col = st.selectbox("Value", df.columns)
        move_col = st.selectbox("Last Movement Date", ["None"]+list(df.columns))
        expiry_col = st.selectbox("Shelf Life Expiry", ["None"]+list(df.columns))
        abc_col = st.selectbox("ABC Class (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={mat_col:"material_code", qty_col:"unrestricted_qty", val_col:"value"})
    profile = get_industry_profile("manufacturing_fmcg")
    slow_thresh = profile.get("thresholds",{}).get("slow_moving_inventory_days",90)

    # Slow-moving
    if move_col != "None":
        df["last_movement_date"] = pd.to_datetime(df[move_col], errors="coerce")
        df["days_since_movement"] = (datetime.today() - df["last_movement_date"]).dt.days
        slow = df[df["days_since_movement"] > slow_thresh]
        st.metric(f"Slow-Moving >{slow_thresh} days", len(slow))
        if not slow.empty:
            st.dataframe(slow[["material_code","days_since_movement","value"]].nlargest(20,"value"), use_container_width=True)

    # Expiry
    if expiry_col != "None":
        df["shelf_life_expiry"] = pd.to_datetime(df[expiry_col], errors="coerce")
        exp = df[df["shelf_life_expiry"] < datetime.today() + pd.Timedelta(days=180)]
        st.metric("Expiring within 180 days", len(exp))
        if not exp.empty:
            st.dataframe(exp[["material_code","shelf_life_expiry","value"]], use_container_width=True)

    # K-Means clustering
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) >= 2 and len(df) >= 4:
        X = df[num_cols].fillna(0)
        km = KMeans(n_clusters=4, random_state=42, n_init="auto")
        df["cluster"] = km.fit_predict(X)
        labels = {0:"Fast",1:"Normal",2:"Slow",3:"Obsolete"}
        df["cluster_label"] = df["cluster"].map(labels)
        fig = px.scatter(df, x=num_cols[0], y=num_cols[1], color="cluster_label",
                         title="Inventory Clustering (Fast/Normal/Slow/Obsolete)")
        st.plotly_chart(fig, use_container_width=True)

    # Log
    init_audit_db()
    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    class _InvCheck(BaseAuditCheck):
        name = "Inventory Anomaly"
        checklist_ref = "Inventory Mgmt A.6–A.11"
        sap_tcode_standard_alt = "MB52 / MB5M / MC46"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _InvCheck()
    log_df = df.head(100).copy()
    log_df["vendor_name"] = log_df["material_code"]
    log_df["flag_reason"] = f"Slow-moving or expiry risk"
    log_df["risk_band"] = "MEDIUM"
    if not log_df.empty:
        checker.log_to_db(log_df, area="Inventory", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        # ── Stage Findings for Draft Review ──
        from utils.audit_db import stage_findings as _stage_findings
        _staged = _stage_findings(
            log_df,
            module_name="Inventory Anomaly",
            run_id=run_id,
            period=datetime.utcnow().strftime("%Y-%m"),
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.info(f"📋 {_staged} exception(s) staged for your review.")
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.caption(f"📝 Findings logged")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = slow if 'slow' in locals() and slow is not None and not slow.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "inv",
            flagged_df=flagged_rag_df,
            module_name="Inventory Anomaly"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("inv", "Inventory Anomaly")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
