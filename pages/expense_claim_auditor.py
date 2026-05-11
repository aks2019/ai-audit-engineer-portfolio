import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
from sklearn.ensemble import IsolationForest
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
from utils.compliance_loader import get_expense_policy
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "exp"

st.title("✈️ Expense & Travel Claim Auditor")
render_engagement_selector(PAGE_KEY)
st.caption("Payroll Mgmt 7a,14,15,21 | SAP: PC00_M99_CALC / PA30")

uploaded = st.file_uploader("Upload Expense Register (CSV/Excel)", type=["csv", "xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} claims")

    with st.expander("🔧 Column Mapping"):
        emp_col = st.selectbox("Employee ID", df.columns)
        grade_col = st.selectbox("Grade", ["None"] + list(df.columns))
        amt_col = st.selectbox("Claim Amount", df.columns)
        type_col = st.selectbox("Claim Type", ["None"] + list(df.columns))
        app_col = st.selectbox("Approver (optional)", ["None"] + list(df.columns))
        doc_col = st.selectbox("Docs Attached (optional)", ["None"] + list(df.columns))

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "emp_col": emp_col,
                "grade_col": grade_col,
                "amt_col": amt_col,
                "type_col": type_col,
                "app_col": app_col,
                "doc_col": doc_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=PAGE_KEY + "_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={emp_col: "employee_id", amt_col: "amount"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    policy = get_expense_policy()
    limits = policy.get("grade_daily_limits", {})

    period_str = datetime.utcnow().strftime("%Y-%m")

    # --- Rule results (always after Run Detection gate) ---
    over = pd.DataFrame()
    if grade_col != "None":
        df["daily_limit"] = df[grade_col].map(limits).fillna(2000)
        over = df[df["amount"] > df["daily_limit"]].copy()
        st.subheader("🚨 Over-limit claims (Payroll Mgmt 7a)")
        if not over.empty:
            st.warning(f"Over-limit claims: {len(over)} (Payroll Mgmt 7a)")
            st.dataframe(over.head(200), use_container_width=True)
        else:
            st.success("No over-limit claims for the mapped grade limits.")

    self_app = pd.DataFrame()
    if app_col != "None":
        self_app = df[df["employee_id"] == df[app_col]].copy()
        st.subheader("🚨 Self-approved claims — SOD (Payroll Mgmt 15)")
        if not self_app.empty:
            st.error(f"Self-approved claims: {len(self_app)} — SOD violation (Payroll 15)")
            st.dataframe(self_app.head(200), use_container_width=True)
        else:
            st.success("No self-approved claims detected.")

    high_no_doc = pd.DataFrame()
    if doc_col != "None":
        no_doc = df[df[doc_col] == 0]
        max_no_doc = policy.get("max_claim_without_docs", 500)
        high_no_doc = no_doc[no_doc["amount"] > max_no_doc].copy()
        st.subheader("🚨 High-value claims without documentation (Payroll Mgmt 14)")
        if not high_no_doc.empty:
            st.warning(f"Claims >₹{max_no_doc} without docs: {len(high_no_doc)}")
            st.dataframe(high_no_doc.head(200), use_container_width=True)
        else:
            st.success(f"No claims above ₹{max_no_doc} without supporting docs.")

    # IsolationForest
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    anom = pd.DataFrame()
    if len(num_cols) >= 2 and len(df) >= 10:
        X = df[num_cols].fillna(0)
        iso = IsolationForest(contamination=0.05, random_state=42)
        df["anomaly"] = iso.fit_predict(X)
        anom = df[df["anomaly"] == -1].copy()
        st.subheader("🚨 ML anomaly screening (IsolationForest)")
        if not anom.empty:
            st.dataframe(anom.head(200), use_container_width=True)
        else:
            st.success("No ML-flagged outliers in this run.")
    st.session_state[f"{PAGE_KEY}_anom_df"] = anom

    def _row_sig(row: pd.Series) -> str:
        try:
            raw = json.dumps(row.to_dict(), default=str, sort_keys=True)
        except Exception:
            raw = str(row.to_dict())
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]

    init_audit_db()
    run_id = f"{analysis_token}:v3"

    frames = []
    # Mutable counter — nonlocal cannot be used here (_append_staging is not nested in a def scope).
    _seq_counter = [0]

    def _append_staging(tmp: pd.DataFrame, checklist_ref: str, risk_band: str, finding_fn):
        if tmp.empty:
            return
        out = tmp.copy()
        out["area"] = "Expense Claims"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["employee_id"].astype(str).replace({"nan": ""})
        out["amount_at_risk"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0).abs().astype(float)
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        refs = []
        for _ in range(len(out)):
            refs.append(f"{PAGE_KEY}-{run_id}-{_seq_counter[0]}")
            _seq_counter[0] += 1
        out["source_row_ref"] = refs
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[
                [
                    "area",
                    "checklist_ref",
                    "finding",
                    "amount_at_risk",
                    "vendor_name",
                    "risk_band",
                    "finding_date",
                    "period",
                    "source_row_ref",
                ]
            ]
        )

    if not over.empty:

        def _f_over(r):
            lim = r.get("daily_limit", 0)
            return (
                f"Over-limit claim ₹{float(r.get('amount', 0)):,.0f} (limit: ₹{float(lim):,.0f}) "
                f"— employee {r.get('employee_id', '')} (ref: {_row_sig(r)})"
            )

        _append_staging(over, "Payroll Mgmt 7a", "HIGH", _f_over)

    if not self_app.empty:

        def _f_self(r):
            return (
                f"Self-approved claim — employee {r.get('employee_id', '')} approved their own claim "
                f"(ref: {_row_sig(r)})"
            )

        _append_staging(self_app, "Payroll Mgmt 15", "CRITICAL", _f_self)

    if not high_no_doc.empty:
        max_nd = policy.get("max_claim_without_docs", 500)

        def _f_nd(r):
            return (
                f"Claim without docs above threshold — ₹{float(r.get('amount', 0)):,.0f} "
                f"(threshold ₹{max_nd}) — employee {r.get('employee_id', '')} (ref: {_row_sig(r)})"
            )

        _append_staging(high_no_doc, "Payroll Mgmt 14", "MEDIUM", _f_nd)

    if not anom.empty:

        def _f_ml(r):
            return (
                f"ML outlier expense claim — employee {r.get('employee_id', '')} "
                f"amount ₹{float(r.get('amount', 0)):,.0f} (ref: {_row_sig(r)})"
            )

        _append_staging(anom, "ML Outlier", "HIGH", _f_ml)

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # RAG: union of raw exception rows for context
    rag_parts = [x for x in [over, self_app, high_no_doc, anom] if x is not None and not x.empty]
    if rag_parts:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.concat(rag_parts, ignore_index=True).drop_duplicates()
    else:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.DataFrame()

    if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        staged = stage_findings(
            staging_df,
            module_name="Expense Claim Auditor",
            run_id=run_id,
            period=period_str,
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.info(
            f"📋 **{staged} exception(s) staged for your review.** "
            "Nothing has been added to the official audit trail until you confirm below. "
            "**Audit Report Centre / Audit Committee Pack** only include findings after you confirm them."
        )
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No actionable expense exceptions detected for staging.")

# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section

    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section(
            "exp",
            flagged_df=flagged_rag_df,
            module_name="Expense Claim Auditor",
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report. Run detection after upload.")
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
        module_name="Expense Claim Auditor",
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
                "vendor_name": st.column_config.TextColumn("Employee", disabled=True),
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
            "draft_exceptions_expense_claims.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
