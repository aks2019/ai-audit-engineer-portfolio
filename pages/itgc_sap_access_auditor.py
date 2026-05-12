import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import secrets

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "itgc"
MODULE_NAME = "Itgc Sap Access Auditor"

st.title("🔐 IT General Controls & SAP Authorization Audit")
render_engagement_selector(PAGE_KEY)
st.caption("Companies Act Section 143(3)(i) | SoD Matrix | SAP: SU01 / SUIM / SM20")

SOD_CONFLICTS = [
    {"a": "FK01", "b": "F110", "risk": "CRITICAL", "desc": "Vendor Create + Payment Run", "ref": "COSO Principle 10"},
    {"a": "ME21N", "b": "MIGO", "risk": "CRITICAL", "desc": "PO Create + GRN Approval", "ref": "Purchasing A.22"},
    {"a": "PC00", "b": "PA30", "risk": "CRITICAL", "desc": "Payroll Run + HR Master", "ref": "Payroll Mgmt 15"},
    {"a": "FD01", "b": "VF11", "risk": "HIGH", "desc": "Customer Create + Invoice Cancel"},
    {"a": "FB50", "b": "FBV0", "risk": "HIGH", "desc": "Journal Entry + Journal Approval"},
    {"a": "FS00", "b": "FB50", "risk": "HIGH", "desc": "GL Account Create + Journal Post"},
]

uploaded = st.file_uploader("Upload SUIM User Access Dump (CSV/Excel)", type=["csv", "xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} access records")

    with st.expander("🔧 Column Mapping"):
        user_col = st.selectbox("User ID", df.columns, key=f"{PAGE_KEY}_user")
        tcode_col = st.selectbox("T-Code", df.columns, key=f"{PAGE_KEY}_tcode")
        role_col = st.selectbox("Role (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_role")
        last_login_col = st.selectbox("Last Login (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_ll")
        status_col = st.selectbox("Status (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_st")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str({"user_col": user_col, "tcode_col": tcode_col, "role_col": role_col, "last_login_col": last_login_col, "status_col": status_col}).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={user_col: "user_id", tcode_col: "tcode"})
    period_str = datetime.utcnow().strftime("%Y-%m")
    privileged = pd.DataFrame()
    inactive = pd.DataFrame()

    conflicts = []
    for c in SOD_CONFLICTS:
        a_users = set(df[df["tcode"] == c["a"]]["user_id"])
        b_users = set(df[df["tcode"] == c["b"]]["user_id"])
        for user in a_users & b_users:
            conflicts.append({**c, "user_id": user})
    conf_df = pd.DataFrame(conflicts)

    st.subheader("🚨 Exception table — Segregation of Duties (SoD) conflicts")
    if not conf_df.empty:
        st.error(f"**{len(conf_df)}** SoD conflict(s) — user holds both conflicting T-codes.")
        st.dataframe(conf_df, use_container_width=True)
    else:
        st.success("No SoD conflicts detected for the built-in matrix.")

    if role_col != "None":
        privileged = df[df[role_col].isin(["SAP_ALL", "SAP_NEW"])].copy()
        st.subheader("🚨 Exception table — privileged SAP roles")
        if not privileged.empty:
            st.warning(f"**{len(privileged)}** assignment(s) with SAP_ALL / SAP_NEW.")
            st.dataframe(privileged.head(200), use_container_width=True)
        else:
            st.success("No SAP_ALL / SAP_NEW assignments in this extract.")

    if last_login_col != "None" and status_col != "None":
        df["last_login_dt"] = pd.to_datetime(df[last_login_col], errors="coerce")
        df["days_since_login"] = (datetime.today() - df["last_login_dt"]).dt.days
        inactive = df[(df["days_since_login"] > 90) & (df[status_col].astype(str) == "Active")].copy()
        st.subheader("🚨 Exception table — inactive IDs still Active")
        if not inactive.empty:
            st.warning(f"**{len(inactive)}** active account(s) with last login **>90** days.")
            st.dataframe(inactive.head(200), use_container_width=True)
        else:
            st.success("No inactive-for-90-days active users.")

    generic = df[df["user_id"].astype(str).str.upper().isin(["ADMIN", "TEST", "TEMP", "BACKUP"])].copy()
    st.subheader("🚨 Exception table — generic / non-personal user IDs")
    if not generic.empty:
        st.error(f"**{len(generic)}** generic user ID row(s) — immediate review.")
        st.dataframe(generic.head(200), use_container_width=True)
    else:
        st.success("No ADMIN/TEST/TEMP/BACKUP style IDs in this extract.")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "ITGC / SAP Access"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["user_id"].map(lambda x: str(x).strip() if pd.notna(x) else "")
        out["amount_at_risk"] = 0.0
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]]
        )

    if not conf_df.empty:
        sod_stage = conf_df.head(500).copy()
        rb = sod_stage["risk"].fillna("HIGH").astype(str).str.upper()
        sod_stage["risk_band"] = rb.where(rb.isin(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), other="HIGH")

        def _f_sod(r):
            return (
                f"SoD conflict — user **{r.get('user_id','')}** has **{r.get('a','')}** + **{r.get('b','')}**: "
                f"{r.get('desc','')} ({r.get('ref','')})"
            )

        out_sod = sod_stage.copy()
        out_sod["area"] = "ITGC / SAP Access"
        out_sod["checklist_ref"] = "COSO Principle 10 / Companies Act 143(3)(i)"
        out_sod["vendor_name"] = out_sod["user_id"].map(lambda x: str(x).strip() if pd.notna(x) else "")
        out_sod["amount_at_risk"] = 0.0
        out_sod["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out_sod["period"] = period_str
        out_sod["source_row_ref"] = [f"{PAGE_KEY}-sod-{secrets.token_hex(8)}" for _ in range(len(out_sod))]
        out_sod["finding"] = out_sod.apply(_f_sod, axis=1)
        frames.append(
            out_sod[
                ["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]
            ]
        )

    if not privileged.empty:

        def _f_priv(r):
            return f"Privileged role assignment — user **{r.get('user_id','')}**, review role row for SAP_ALL/SAP_NEW exposure"

        _append_staging(privileged, checklist_ref="COSO Principle 10 / SAP Authorizations", risk_band="CRITICAL", finding_fn=_f_priv, kind="priv")

    if not inactive.empty:

        def _f_inact(r):
            d = int(r.get("days_since_login") or 0)
            return f"Dormant active user — **{r.get('user_id','')}** last login **{d}** days ago (>90) while status Active"

        _append_staging(inactive, checklist_ref="COSO Principle 10 / User Lifecycle", risk_band="MEDIUM", finding_fn=_f_inact, kind="inact")

    if not generic.empty:

        def _f_gen(r):
            return f"Generic / shared user ID — **{r.get('user_id','')}** flagged for remediation (ADMIN/TEST/TEMP/BACKUP pattern)"

        _append_staging(generic, checklist_ref="COSO Principle 10", risk_band="CRITICAL", finding_fn=_f_gen, kind="generic")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [conf_df, privileged, inactive, generic] if x is not None and not x.empty]
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
        st.info("No ITGC exceptions to stage from this extract.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("itgc", flagged_df=flagged_rag_df, module_name="ITGC SAP Access Auditor")
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
                "vendor_name": st.column_config.TextColumn("User ID", disabled=True),
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
            "draft_exceptions_itgc_sap_access.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
