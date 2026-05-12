import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import secrets

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    save_sampling_run,
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "sample"
MODULE_NAME = "Statistical Sampling"

st.title("📐 Statistical Sampling Engine")
render_engagement_selector(PAGE_KEY)
st.caption("Monetary Unit Sampling (MUS) | Random Sampling | Cell Sampling | Confidence-based")

uploaded = st.file_uploader("Upload Population Data (CSV/Excel)", type=["csv", "xlsx"])

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Population: {len(df):,} rows")

    with st.expander("🔧 Column Mapping"):
        id_col = st.selectbox("Unique ID", df.columns, key=f"{PAGE_KEY}_id")
        amt_col = st.selectbox("Monetary Amount", df.columns, key=f"{PAGE_KEY}_amt")
        stratify_col = st.selectbox("Stratify By (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_str")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(str({"id_col": id_col, "amt_col": amt_col, "stratify_col": stratify_col}).encode("utf-8")).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection** to configure sampling and stage results.")
        st.stop()

    df = df.rename(columns={id_col: "_id", amt_col: "_amount"})
    df["_amount"] = pd.to_numeric(df["_amount"], errors="coerce").fillna(0)
    total_value = float(df["_amount"].sum())

    st.metric("Total Population Value", f"₹{total_value:,.0f}")

    method = st.selectbox(
        "Sampling Method",
        ["Monetary Unit Sampling (MUS)", "Simple Random", "Cell Sampling", "Stratified Random"],
        key=f"{PAGE_KEY}_method",
    )
    confidence = st.slider("Confidence Level", 0.80, 0.99, 0.95, key=f"{PAGE_KEY}_conf")
    materiality = st.number_input("Materiality Threshold (₹)", min_value=1000, value=500000, step=10000, key=f"{PAGE_KEY}_mat")
    expected_error = st.slider("Expected Error Rate", 0.0, 0.10, 0.02, key=f"{PAGE_KEY}_exp")

    z = {0.80: 1.28, 0.90: 1.645, 0.95: 1.96, 0.99: 2.576}[confidence]
    sample_size = int(min(len(df), max(30, (z**2 * total_value * expected_error * (1 - expected_error)) / (materiality**2))))
    st.metric("Calculated Sample Size", sample_size)

    period_str = datetime.utcnow().strftime("%Y-%m")

    if st.button("🎯 Draw Sample & Stage for Review", type="primary", key=f"{PAGE_KEY}_draw_btn"):
        np.random.seed(42)
        sample = None
        if method == "Monetary Unit Sampling (MUS)":
            if total_value <= 0:
                st.error("Total population value must be positive for MUS.")
            else:
                probs = df["_amount"] / total_value
                probs = probs.fillna(0)
                ssum = probs.sum()
                if ssum <= 0:
                    st.error("Cannot compute MUS weights — check amounts.")
                else:
                    probs = probs / ssum
                    n_draw = min(max(sample_size, 1), len(df) * 10)
                    selected = np.random.choice(df.index, size=n_draw, p=probs, replace=True)
                    sample = df.loc[selected].drop_duplicates("_id").copy()
                    sample = sample.head(sample_size)
        elif method == "Simple Random":
            sample = df.sample(n=min(sample_size, len(df)), random_state=42).copy()
        elif method == "Cell Sampling":
            df_cs = df.copy()
            df_cs["_cell"] = pd.qcut(df_cs["_amount"], q=5, labels=False, duplicates="drop")
            k = max(1, sample_size // 5)
            sample = df_cs.groupby("_cell", group_keys=False).apply(lambda x: x.sample(n=min(len(x), k), random_state=42)).reset_index(drop=True)
        elif method == "Stratified Random" and stratify_col != "None":
            n_groups = max(1, df[stratify_col].nunique())
            sample = (
                df.groupby(stratify_col, group_keys=False)
                .apply(lambda x: x.sample(n=max(1, min(len(x), sample_size // n_groups)), random_state=42))
                .reset_index(drop=True)
            )
        else:
            sample = df.sample(n=min(sample_size, len(df)), random_state=42).copy()

        if sample is not None and not sample.empty:
            st.session_state[f"{PAGE_KEY}_sample_df"] = sample
            st.session_state[f"{PAGE_KEY}_last_method"] = method
            st.session_state[f"{PAGE_KEY}_last_confidence"] = confidence
            st.session_state[f"{PAGE_KEY}_last_materiality"] = materiality

            init_audit_db()
            save_sampling_run(
                run_name=f"{method}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}",
                population_size=len(df),
                sample_size=len(sample),
                method=method,
                confidence_level=confidence,
                materiality_threshold=materiality,
                engagement_id=get_active_engagement_id(PAGE_KEY),
            )

            param_sig = hashlib.sha256(
                str({"method": method, "confidence": confidence, "materiality": materiality, "sample_size_plan": sample_size}).encode("utf-8")
            ).hexdigest()[:12]
            run_id = f"{analysis_token}:{param_sig}:v2"

            st.subheader("🚨 Exception table — sampled items (draft staging for auditor review)")
            st.caption(
                "Each sampled population item is staged as a **draft** line for maker–checker confirmation "
                "(documentation trail for ISA / SA sampling)."
            )
            st.success(f"Sample drawn: **{len(sample)}** items | Sample value: **₹{sample['_amount'].sum():,.0f}**")
            st.dataframe(sample, use_container_width=True)

            csv = sample.to_csv(index=False).encode()
            st.download_button("📥 Download Sample CSV", csv, "audit_sample.csv", "text/csv", key=f"{PAGE_KEY}_dl_sample")

            cap = sample.head(500).copy()
            cap["area"] = "Statistical Sampling"
            cap["checklist_ref"] = "ISA / SA — Sampling documentation"
            cap["vendor_name"] = cap["_id"].map(lambda x: str(x).strip() if pd.notna(x) else "")
            cap["amount_at_risk"] = pd.to_numeric(cap["_amount"], errors="coerce").fillna(0).abs().astype(float)
            cap["risk_band"] = "MEDIUM"
            cap["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            cap["period"] = period_str
            cap["source_row_ref"] = [f"{PAGE_KEY}-mus-{secrets.token_hex(8)}" for _ in range(len(cap))]

            def _line(r):
                return (
                    f"Sampled item for substantive testing — ID **{r.get('_id','')}**, "
                    f"amount **₹{float(r.get('_amount',0)):,.0f}** | Method: **{method}**, confidence **{confidence:.0%}**, "
                    f"materiality **₹{materiality:,.0f}**."
                )

            cap["finding"] = cap.apply(_line, axis=1)

            staging_df = cap[
                ["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]
            ]

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
                f"📋 **{staged} exception(s) staged for your review** (of **{len(staging_df)}** sampled lines). "
                "Nothing has been added to the official audit trail until you confirm below. "
                "**Audit Report Centre / Audit Committee Pack** only include findings after you confirm them."
            )
            if staged < len(staging_df):
                st.warning(f"**{len(staging_df) - staged}** row(s) skipped — duplicate draft/confirmed finding (dedupe).")

try:
    sample_df = st.session_state.get(f"{PAGE_KEY}_sample_df")
    if sample_df is not None and not sample_df.empty:
        render_rag_report_section(PAGE_KEY, flagged_df=sample_df, module_name=MODULE_NAME)
    elif uploaded:
        st.caption("ℹ️ Draw a sample after **Run Detection** to enable RAG audit report.")
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
        st.info("No draft exceptions pending for the current sample run.")
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
                "vendor_name": st.column_config.TextColumn("Population ID", disabled=True),
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
            "draft_exceptions_statistical_sampling.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
