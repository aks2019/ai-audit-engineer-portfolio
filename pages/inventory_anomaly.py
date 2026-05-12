import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import secrets
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.compliance_loader import get_industry_profile
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "inv"
MODULE_NAME = "Inventory Anomaly"

st.title("📦 Inventory Valuation & Slow-Moving Stock Detector")
render_engagement_selector(PAGE_KEY)
st.caption("Inventory Mgmt A.6–A.11 | SAP: MB52 + MB5M / MC46")

uploaded = st.file_uploader("Upload Inventory Extract (CSV/Excel)", type=["csv", "xlsx"])

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} materials")

    with st.expander("🔧 Column Mapping"):
        mat_col = st.selectbox("Material Code", df.columns, key=f"{PAGE_KEY}_mat")
        qty_col = st.selectbox("Unrestricted Qty", df.columns, key=f"{PAGE_KEY}_qty")
        val_col = st.selectbox("Value", df.columns, key=f"{PAGE_KEY}_val")
        move_col = st.selectbox("Last Movement Date", ["None"] + list(df.columns), key=f"{PAGE_KEY}_move")
        expiry_col = st.selectbox("Shelf Life Expiry", ["None"] + list(df.columns), key=f"{PAGE_KEY}_exp")
        abc_col = st.selectbox("ABC Class (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_abc")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str({"mat_col": mat_col, "qty_col": qty_col, "val_col": val_col, "move_col": move_col, "expiry_col": expiry_col, "abc_col": abc_col}).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={mat_col: "material_code", qty_col: "unrestricted_qty", val_col: "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    slow = pd.DataFrame()
    near_expiry = pd.DataFrame()
    iso_outliers = pd.DataFrame()
    profile = get_industry_profile("manufacturing_fmcg")
    slow_thresh = profile.get("thresholds", {}).get("slow_moving_inventory_days", 90)
    period_str = datetime.utcnow().strftime("%Y-%m")

    if move_col != "None":
        df["last_movement_date"] = pd.to_datetime(df[move_col], errors="coerce")
        df["days_since_movement"] = (datetime.today() - df["last_movement_date"]).dt.days
        slow = df[df["days_since_movement"] > slow_thresh].copy()
        st.subheader("🚨 Exception table — slow-moving inventory (Inventory Mgmt A.6–A.11)")
        st.caption(f"Materials with no movement longer than **{slow_thresh}** days.")
        st.metric(f"Slow-moving >{slow_thresh} days", len(slow))
        if not slow.empty:
            st.dataframe(
                slow[["material_code", "days_since_movement", "value"]].nlargest(200, "value"),
                use_container_width=True,
            )
        else:
            st.success("No slow-moving materials above the threshold.")

    if expiry_col != "None":
        df["shelf_life_expiry"] = pd.to_datetime(df[expiry_col], errors="coerce")
        near_expiry = df[df["shelf_life_expiry"] < datetime.today() + pd.Timedelta(days=180)].copy()
        st.subheader("🚨 Exception table — near-expiry / shelf-life risk (Inventory Mgmt A.8–A.10)")
        st.caption("Materials with expiry within **180** days from today.")
        st.metric("Expiring within 180 days", len(near_expiry))
        if not near_expiry.empty:
            st.dataframe(
                near_expiry[["material_code", "shelf_life_expiry", "value"]].head(200),
                use_container_width=True,
            )
        else:
            st.success("No near-expiry exposure in this window.")

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) >= 2 and len(df) >= 4:
        X = df[num_cols].fillna(0)
        km = KMeans(n_clusters=4, random_state=42, n_init="auto")
        df["cluster"] = km.fit_predict(X)
        labels = {0: "Fast", 1: "Normal", 2: "Slow", 3: "Obsolete"}
        df["cluster_label"] = df["cluster"].map(labels)
        st.subheader("📊 Inventory velocity clusters (K-Means)")
        fig = px.scatter(
            df,
            x=num_cols[0],
            y=num_cols[1],
            color="cluster_label",
            title="Inventory Clustering (Fast / Normal / Slow / Obsolete)",
        )
        st.plotly_chart(fig, use_container_width=True)

    if len(num_cols) >= 2 and len(df) >= 10:
        Xn = df[num_cols].fillna(0)
        iso = IsolationForest(contamination=0.05, random_state=42)
        df["iso_pred"] = iso.fit_predict(Xn)
        iso_outliers = df[df["iso_pred"] == -1].copy()
        st.subheader("🚨 Exception table — ML inventory outliers (IsolationForest)")
        if not iso_outliers.empty:
            st.warning(f"**{len(iso_outliers)}** line(s) flagged as multivariate outliers.")
            st.dataframe(iso_outliers.head(200), use_container_width=True)
        else:
            st.success("No ML outliers in this run.")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "Inventory"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["material_code"].map(lambda x: str(x).strip() if pd.notna(x) else "")
        out["amount_at_risk"] = pd.to_numeric(out.get("value", 0), errors="coerce").fillna(0).abs().astype(float)
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[
                ["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]
            ]
        )

    if not slow.empty:

        def _f_slow(r):
            d = int(r.get("days_since_movement") or 0)
            return f"Slow-moving stock — material {r.get('material_code','')} inactive **{d}** days (> {slow_thresh}d), value ₹{float(r.get('value', 0)):,.0f}"

        _append_staging(slow, checklist_ref="Inventory Mgmt A.6–A.11", risk_band="HIGH", finding_fn=_f_slow, kind="slow")

    if not near_expiry.empty:

        def _f_exp(r):
            exp = r.get("shelf_life_expiry")
            return f"Near-expiry / shelf-life risk — material {r.get('material_code','')} expires **{exp}**, value ₹{float(r.get('value', 0)):,.0f}"

        _append_staging(near_expiry, checklist_ref="Inventory Mgmt A.8–A.10", risk_band="MEDIUM", finding_fn=_f_exp, kind="exp")

    if not iso_outliers.empty:

        def _f_iso(r):
            return (
                f"ML outlier inventory line — material {r.get('material_code','')} "
                f"qty/value profile vs population, value ₹{float(r.get('value', 0)):,.0f}"
            )

        _append_staging(iso_outliers, checklist_ref="Inventory Mgmt A.6–A.11 / analytics", risk_band="HIGH", finding_fn=_f_iso, kind="iso")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [slow, near_expiry, iso_outliers] if x is not None and not x.empty]
    if rag_parts:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.concat(rag_parts, ignore_index=True).drop_duplicates()
    else:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.DataFrame()

    if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        staged = stage_findings(
            staging_df,
            module_name=MODULE_NAME,
            run_id=run_id,
            period=period_str,
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.info(
            f"📋 **{staged} exception(s) staged for your review** (of **{len(staging_df)}** detected). "
            "Nothing has been added to the official audit trail until you confirm below. "
            "**Audit Report Centre / Audit Committee Pack** only include findings after you confirm them."
        )
        if staged < len(staging_df):
            st.warning(
                f"**{len(staging_df) - staged}** row(s) skipped — identical draft/confirmed finding exists for this engagement (dedupe)."
            )
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No actionable inventory exceptions detected for staging on this extract.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("inv", flagged_df=flagged_rag_df, module_name=MODULE_NAME)
    elif uploaded:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")

current_run_id = st.session_state.get(f"{PAGE_KEY}_draft_run_id")
if current_run_id:
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption("Use the Select column in the table to confirm/discard. No separate selector is required.")

    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name=MODULE_NAME,
        status="Draft",
        engagement_id=get_active_engagement_id(PAGE_KEY),
    )
    if drafts.empty:
        st.info("No draft exceptions pending for the current run.")
    else:
        select_all = st.checkbox("Select all draft exceptions", value=False, key=f"{PAGE_KEY}_select_all_drafts")
        st.caption(f"**{len(drafts)} draft exception(s)** pending review.")
        review_df = drafts[["id", "area", "vendor_name", "finding", "amount_at_risk", "risk_band"]].copy()
        review_df.insert(0, "select", select_all)

        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "area": st.column_config.TextColumn("Area", disabled=True),
                "vendor_name": st.column_config.TextColumn("Material / Subject", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn("Risk Band", options=["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
            },
            key=f"{PAGE_KEY}_draft_editor_inline_select",
        )

        selected_ids = edited.loc[edited["select"] == True, "id"].astype(int).tolist()
        confirmed_by = st.text_input("Confirmed / Reviewed by (auditor name)", value="Auditor", key=f"{PAGE_KEY}_confirmed_by")

        c_confirm, c_discard = st.columns(2)
        with c_confirm:
            if st.button(
                "Confirm Selected to Official Audit Trail",
                type="primary",
                use_container_width=True,
                key=f"{PAGE_KEY}_confirm_btn",
            ):
                if not selected_ids:
                    st.warning("Select at least one exception in the table.")
                else:
                    edited_vals = {
                        int(row["id"]): {
                            "finding": row.get("finding", ""),
                            "amount_at_risk": row.get("amount_at_risk", 0),
                            "risk_band": row.get("risk_band", "MEDIUM"),
                        }
                        for _, row in edited.iterrows()
                    }
                    n = confirm_draft_findings(
                        selected_ids,
                        confirmed_by=confirmed_by.strip() or "Auditor",
                        edited_values=edited_vals,
                    )
                    st.success(f"**{n} finding(s) confirmed** and added to the official audit trail.")
                    st.rerun()

        with c_discard:
            discard_reason = st.text_input("Discard reason (optional)", key=f"{PAGE_KEY}_discard_reason")
            if st.button("Discard Selected (False Positives)", use_container_width=True, key=f"{PAGE_KEY}_discard_btn"):
                if not selected_ids:
                    st.warning("Select at least one exception in the table.")
                else:
                    n = discard_draft_findings(
                        selected_ids,
                        discarded_by=confirmed_by.strip() or "Auditor",
                        reason=discard_reason or "False positive — auditor review",
                    )
                    st.info(f"**{n} exception(s) discarded.** They will not appear in reports.")
                    st.rerun()

        csv_draft = drafts.to_csv(index=False).encode()
        st.download_button(
            "Export Draft Exceptions as CSV",
            csv_draft,
            "draft_exceptions_inventory_anomaly.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
