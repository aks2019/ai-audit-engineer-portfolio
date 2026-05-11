import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
from sklearn.neural_network import MLPRegressor
import hashlib
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_depreciation_rate, load_compliance_calendar
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "fa"

st.title("🏭 Fixed Asset Addition & Depreciation Auditor")
render_engagement_selector(PAGE_KEY)
st.caption("Fixed Assets A.1–A.13, B.1–B.41 | SAP: AS03 / AFAB")

uploaded = st.file_uploader("Upload Asset Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} assets")

    with st.expander("🔧 Column Mapping"):
        desc_col = st.selectbox("Asset Description", df.columns)
        cost_col = st.selectbox("Acquisition Cost", df.columns)
        acc_dep_col = st.selectbox("Accumulated Depreciation", df.columns)
        rate_col = st.selectbox("Applied Depreciation Rate %", df.columns)
        asset_class_col = st.selectbox("Asset Class", ["None"]+list(df.columns))
        date_col = st.selectbox("Acquisition Date (optional)", ["None"]+list(df.columns))
        approved_col = st.selectbox("Capex Approved (optional)", ["None"]+list(df.columns))

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "desc_col": desc_col,
                "cost_col": cost_col,
                "acc_dep_col": acc_dep_col,
                "rate_col": rate_col,
                "asset_class_col": asset_class_col,
                "date_col": date_col,
                "approved_col": approved_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_detection_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={desc_col:"asset_description", cost_col:"cost", acc_dep_col:"accumulated_depreciation", rate_col:"applied_rate"})
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    df["accumulated_depreciation"] = pd.to_numeric(df["accumulated_depreciation"], errors="coerce").fillna(0)
    df["applied_rate"] = pd.to_numeric(df["applied_rate"], errors="coerce").fillna(0)
    cal = load_compliance_calendar()

    # Revenue vs capital
    rev_keywords = cal.get("fixed_assets",{}).get("revenue_keywords",[])
    df["revenue_flag"] = df["asset_description"].astype(str).str.lower().apply(lambda x: any(k in x for k in rev_keywords))
    rev = df[df["revenue_flag"]]
    if not rev.empty:
        st.warning(f"Revenue-like keyword detected in {len(rev)} assets — capitalisation review needed")
        st.dataframe(rev[["asset_description","cost"]].head(20), use_container_width=True)

    # Depreciation rate variance
    if asset_class_col != "None":
        df["expected_rate"] = df[asset_class_col].apply(lambda c: get_depreciation_rate(str(c)))
        df["rate_variance"] = (df["applied_rate"] - df["expected_rate"]).abs()
        var = df[df["rate_variance"] > 0.5]
        if not var.empty:
            st.warning(f"Depreciation rate variance >0.5%: {len(var)} assets")
            st.dataframe(var[["asset_description",asset_class_col,"applied_rate","expected_rate"]].head(20), use_container_width=True)
    else:
        var = pd.DataFrame()

    # Unapproved capex
    if approved_col != "None":
        thresh = cal.get("fixed_assets",{}).get("capex_approval_threshold",100000)
        unapproved = df[(df[approved_col] != 1) & (df["cost"] > thresh)]
        if not unapproved.empty:
            st.error(f"Unapproved capex >₹{thresh:,}: {len(unapproved)} assets (Fixed Assets B.4)")
    else:
        unapproved = pd.DataFrame()

    # Autoencoder anomaly
    num_cols = ["cost","accumulated_depreciation","applied_rate"]
    num_cols = [c for c in num_cols if c in df.columns]
    if len(num_cols) >= 2 and len(df) >= 10:
        X = df[num_cols].fillna(0)
        ae = MLPRegressor(hidden_layer_sizes=(8,4,8), max_iter=500, random_state=42)
        ae.fit(X, X)
        recon = ae.predict(X)
        mse = np.mean((X - recon)**2, axis=1)
        df["autoencoder_mse"] = mse
        top_ae = df.nlargest(10, "autoencoder_mse")
        st.subheader("🤖 Autoencoder Anomalies")
        st.dataframe(top_ae[["asset_description"]+num_cols+["autoencoder_mse"]], use_container_width=True)
    else:
        top_ae = pd.DataFrame()

    # Stage only true detected exceptions for maker-checker flow
    init_audit_db()
    run_id = f"{analysis_token}:v2"

    def _row_sig(row: pd.Series) -> str:
        try:
            raw = json.dumps(row.to_dict(), default=str, sort_keys=True)
        except Exception:
            raw = str(row.to_dict())
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]

    frames = []

    if not rev.empty:
        tmp = rev.copy()
        tmp["area"] = "Fixed Assets"
        tmp["checklist_ref"] = "Fixed Assets A.1 (capital vs revenue)"
        tmp["vendor_name"] = tmp["asset_description"].astype(str)
        tmp["amount_at_risk"] = tmp["cost"].abs()
        tmp["risk_band"] = "MEDIUM"
        tmp["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        tmp["finding"] = tmp.apply(
            lambda r: f"Revenue-like keyword in asset description — '{r.get('asset_description','')}' cost ₹{r.get('cost',0):,.0f}"
            + f" (ref: {_row_sig(r)})",
            axis=1,
        )
        frames.append(tmp[["area","checklist_ref","finding","amount_at_risk","vendor_name","risk_band","finding_date"]])

    if not var.empty:
        tmp = var.copy()
        tmp["area"] = "Fixed Assets"
        tmp["checklist_ref"] = "Fixed Assets A.7 (rate variance)"
        tmp["vendor_name"] = tmp["asset_description"].astype(str)
        tmp["amount_at_risk"] = tmp["cost"].abs()
        tmp["risk_band"] = "MEDIUM"
        tmp["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        tmp["finding"] = tmp.apply(
            lambda r: f"Depreciation rate variance {r.get('rate_variance',0):.2f}% — applied {r.get('applied_rate',0)} vs expected {r.get('expected_rate',0)}"
            + f" (ref: {_row_sig(r)})",
            axis=1,
        )
        frames.append(tmp[["area","checklist_ref","finding","amount_at_risk","vendor_name","risk_band","finding_date"]])

    if not unapproved.empty:
        tmp = unapproved.copy()
        tmp["area"] = "Fixed Assets"
        tmp["checklist_ref"] = "Fixed Assets B.4 (capex approval)"
        tmp["vendor_name"] = tmp["asset_description"].astype(str)
        tmp["amount_at_risk"] = tmp["cost"].abs()
        tmp["risk_band"] = "HIGH"
        tmp["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        tmp["finding"] = tmp.apply(
            lambda r: f"Unapproved capex above threshold — '{r.get('asset_description','')}' cost ₹{r.get('cost',0):,.0f}"
            + f" (ref: {_row_sig(r)})",
            axis=1,
        )
        frames.append(tmp[["area","checklist_ref","finding","amount_at_risk","vendor_name","risk_band","finding_date"]])

    if not top_ae.empty:
        tmp = top_ae.copy()
        tmp["area"] = "Fixed Assets"
        tmp["checklist_ref"] = "ML Outlier (autoencoder)"
        tmp["vendor_name"] = tmp["asset_description"].astype(str)
        tmp["amount_at_risk"] = tmp["cost"].abs() if "cost" in tmp.columns else 0.0
        tmp["risk_band"] = "HIGH"
        tmp["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        tmp["finding"] = tmp.apply(
            lambda r: f"Autoencoder anomaly (mse={r.get('autoencoder_mse',0):.4f}) — '{r.get('asset_description','')}'"
            + f" (ref: {_row_sig(r)})",
            axis=1,
        )
        frames.append(tmp[["area","checklist_ref","finding","amount_at_risk","vendor_name","risk_band","finding_date"]])

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        staged = stage_findings(
            staging_df,
            module_name="Fixed Asset Auditor",
            run_id=run_id,
            period=datetime.utcnow().strftime("%Y-%m"),
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.info(
            f"📋 **{staged} exception(s) staged for your review.** "
            "Nothing has been added to the official audit trail yet."
        )
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No actionable fixed asset exceptions detected for staging.")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = top_ae if 'top_ae' in locals() and top_ae is not None and not top_ae.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "fa",
            flagged_df=flagged_rag_df,
            module_name="Fixed Asset Auditor"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
current_run_id = st.session_state.get(f"{PAGE_KEY}_draft_run_id")
if current_run_id:
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption("Use the Select column in the table to confirm/discard. No separate selector is required.")

    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name="Fixed Asset Auditor",
        status="Draft",
        engagement_id=get_active_engagement_id(PAGE_KEY),
    )
    if drafts.empty:
        st.info("No draft exceptions pending for the current run.")
    else:
        select_all = st.checkbox(
            "Select all draft exceptions",
            value=False,
            key=f"{PAGE_KEY}_select_all_drafts",
        )
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
                "vendor_name": st.column_config.TextColumn("Asset", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn(
                    "Risk Band",
                    options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                ),
            },
            key=f"{PAGE_KEY}_draft_editor_inline_select",
        )

        selected_ids = edited.loc[edited["select"] == True, "id"].astype(int).tolist()
        confirmed_by = st.text_input(
            "Confirmed / Reviewed by (auditor name)",
            value="Auditor",
            key=f"{PAGE_KEY}_confirmed_by",
        )

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
            discard_reason = st.text_input(
                "Discard reason (optional)",
                key=f"{PAGE_KEY}_discard_reason",
            )
            if st.button(
                "Discard Selected (False Positives)",
                use_container_width=True,
                key=f"{PAGE_KEY}_discard_btn",
            ):
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
            "draft_exceptions_fixed_assets.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
