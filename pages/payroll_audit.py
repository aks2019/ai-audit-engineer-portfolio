import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import secrets
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.compliance_loader import get_pf_esi_rates
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "pay"
MODULE_NAME = "Payroll Audit"

st.title("👥 Payroll & HR Audit")
render_engagement_selector(PAGE_KEY)
st.caption("Payroll Mgmt 1–21 | SAP: PA30 / PC00_M99_CALC / S_AHR_61016362")

uploaded = st.file_uploader("Upload Payroll Register (CSV/Excel)", type=["csv", "xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} employees")

    with st.expander("🔧 Column Mapping"):
        emp_col = st.selectbox("Employee ID", df.columns, key=f"{PAGE_KEY}_emp")
        pan_col = st.selectbox("PAN", df.columns, key=f"{PAGE_KEY}_pan")
        bank_col = st.selectbox("Bank Account", df.columns, key=f"{PAGE_KEY}_bank")
        basic_col = st.selectbox("Basic + DA", df.columns, key=f"{PAGE_KEY}_basic")
        pf_col = st.selectbox("PF Deducted", df.columns, key=f"{PAGE_KEY}_pf")
        esi_col = st.selectbox("ESI Deducted", df.columns, key=f"{PAGE_KEY}_esi")
        gross_col = st.selectbox("Gross Wages", df.columns, key=f"{PAGE_KEY}_gross")
        status_col = st.selectbox("Status", ["None"] + list(df.columns), key=f"{PAGE_KEY}_st")
        last_att_col = st.selectbox("Last Attendance Date", ["None"] + list(df.columns), key=f"{PAGE_KEY}_att")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "emp_col": emp_col,
                "pan_col": pan_col,
                "bank_col": bank_col,
                "basic_col": basic_col,
                "pf_col": pf_col,
                "esi_col": esi_col,
                "gross_col": gross_col,
                "status_col": status_col,
                "last_att_col": last_att_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(
        columns={
            emp_col: "employee_id",
            pan_col: "pan",
            bank_col: "bank_account",
            basic_col: "basic_da",
            pf_col: "pf_deducted",
            esi_col: "esi_deducted",
            gross_col: "gross_wages",
        }
    )
    for c in ["basic_da", "pf_deducted", "esi_deducted", "gross_wages"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    period_str = datetime.utcnow().strftime("%Y-%m")
    anom = pd.DataFrame()

    dup_pan = df[df.duplicated("pan", keep=False)].copy()
    dup_bank = df[df.duplicated("bank_account", keep=False)].copy()
    if status_col != "None" and last_att_col != "None":
        df["days_absent"] = (pd.Timestamp.today() - pd.to_datetime(df[last_att_col], errors="coerce")).dt.days
        absent_active = df[(df[status_col].astype(str) == "Active") & (df["days_absent"] > 90)].copy()
    else:
        absent_active = pd.DataFrame()

    rates = get_pf_esi_rates()
    df["pf_expected"] = df["basic_da"].clip(upper=rates["pf_wage_ceiling"]) * rates["pf_employee_rate"] / 100
    df["pf_variance"] = (df["pf_deducted"] - df["pf_expected"]).abs()
    df["esi_applicable"] = df["gross_wages"] <= rates["esi_wage_ceiling"]
    df["esi_expected"] = 0.0
    df.loc[df["esi_applicable"], "esi_expected"] = df.loc[df["esi_applicable"], "gross_wages"] * rates["esi_employee_rate"] / 100
    df["esi_variance"] = (df["esi_deducted"] - df["esi_expected"]).abs()
    pf_esi_flag = df[(df["pf_variance"] > 1) | (df["esi_variance"] > 1)].copy()

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) >= 2 and len(df) >= 10:
        X = df[num_cols].fillna(0)
        iso = IsolationForest(contamination=0.05, random_state=42)
        df["anomaly"] = iso.fit_predict(X)
        anom = df[df["anomaly"] == -1].copy()

    st.subheader("🚨 Exception table — duplicate PAN (ghost employee indicators — Payroll 7)")
    if not dup_pan.empty:
        st.warning(f"**{len(dup_pan)}** row(s) with duplicate PAN.")
        st.dataframe(dup_pan.head(200), use_container_width=True)
    else:
        st.success("No duplicate PAN patterns.")

    st.subheader("🚨 Exception table — duplicate bank account (Payroll 7)")
    if not dup_bank.empty:
        st.warning(f"**{len(dup_bank)}** row(s) with duplicate bank account.")
        st.dataframe(dup_bank.head(200), use_container_width=True)
    else:
        st.success("No duplicate bank account patterns.")

    st.subheader("🚨 Exception table — Active but no attendance >90 days")
    if not absent_active.empty:
        st.warning(f"**{len(absent_active)}** active employee(s) with attendance gap >90 days.")
        st.dataframe(absent_active.head(200), use_container_width=True)
    else:
        st.success("No active-with-long-absence flags (or attendance column not mapped).")

    st.subheader("🚨 Exception table — PF / ESI deduction variance (Payroll 14 / F&A C.10)")
    if not pf_esi_flag.empty:
        st.warning(f"**{len(pf_esi_flag)}** employee(s) with PF or ESI variance > ₹1.")
        st.dataframe(
            pf_esi_flag[["employee_id", "basic_da", "pf_deducted", "pf_expected", "esi_deducted", "esi_expected"]].head(200),
            use_container_width=True,
        )
    else:
        st.success("No material PF/ESI variance vs configured rates.")

    st.subheader("🚨 Exception table — ML payroll outliers (IsolationForest)")
    if not anom.empty:
        st.warning(f"**{len(anom)}** employee(s) flagged as statistical outliers.")
        st.dataframe(anom.head(200), use_container_width=True)
    else:
        if len(num_cols) >= 2 and len(df) >= 10:
            st.success("No ML outliers.")
        else:
            st.info("ML screening skipped (needs ≥10 rows and ≥2 numeric columns).")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "Payroll / HR"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["employee_id"].map(lambda x: str(x).strip() if pd.notna(x) else "")
        gv = pd.to_numeric(out.get("gross_wages", 0), errors="coerce").fillna(0)
        out["amount_at_risk"] = gv.abs().astype(float)
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]]
        )

    if not dup_pan.empty:

        def _f_dup_pan(_r):
            return f"Duplicate PAN — possible ghost / duplicate employment (Payroll 7), employee **{_r.get('employee_id','')}**, PAN {_r.get('pan','')}"

        _append_staging(dup_pan, checklist_ref="Payroll Mgmt 7", risk_band="HIGH", finding_fn=_f_dup_pan, kind="dup-pan")

    if not dup_bank.empty:

        def _f_dup_bank(_r):
            return f"Duplicate bank account — shared payout account risk (Payroll 7), employee **{_r.get('employee_id','')}**"

        _append_staging(dup_bank, checklist_ref="Payroll Mgmt 7", risk_band="HIGH", finding_fn=_f_dup_bank, kind="dup-bank")

    if not absent_active.empty:

        def _f_abs(_r):
            d = int(_r.get("days_absent") or 0)
            return f"Active roster with **{d}** days since last attendance — review ghost headcount, employee **{_r.get('employee_id','')}**"

        _append_staging(absent_active, checklist_ref="Payroll Mgmt 15 / HR master", risk_band="MEDIUM", finding_fn=_f_abs, kind="absent")

    if not pf_esi_flag.empty:

        def _f_pe(_r):
            return (
                f"PF/ESI mismatch — employee **{_r.get('employee_id','')}** "
                f"(PF deducted ₹{float(_r.get('pf_deducted',0)):,.0f} vs expected ₹{float(_r.get('pf_expected',0)):,.0f}; "
                f"ESI deducted ₹{float(_r.get('esi_deducted',0)):,.0f} vs expected ₹{float(_r.get('esi_expected',0)):,.0f})"
            )

        _append_staging(pf_esi_flag, checklist_ref="Payroll Mgmt 14 / F&A C.10", risk_band="MEDIUM", finding_fn=_f_pe, kind="pfesi")

    if not anom.empty:

        def _f_ml(_r):
            return f"ML outlier payroll profile — employee **{_r.get('employee_id','')}**, gross ₹{float(_r.get('gross_wages',0)):,.0f}"

        _append_staging(anom, checklist_ref="Payroll Mgmt 1–21 (analytics)", risk_band="HIGH", finding_fn=_f_ml, kind="ml")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [dup_pan, dup_bank, absent_active, pf_esi_flag, anom] if x is not None and not x.empty]
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
            st.warning(f"**{len(staging_df) - staged}** row(s) skipped — duplicate draft/confirmed finding (dedupe).")
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No actionable payroll exceptions to stage.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("pay", flagged_df=flagged_rag_df, module_name=MODULE_NAME)
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
                "vendor_name": st.column_config.TextColumn("Employee ID", disabled=True),
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
            "draft_exceptions_payroll_audit.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
