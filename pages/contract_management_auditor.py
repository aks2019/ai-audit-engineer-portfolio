import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import get_industry_profile
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "cnt"

st.title("📜 Contract & AMC Management Auditor")
st.caption("Purchasing A.1–A.8 | Contract Labour Act 1970 | SAP: ME33K / ME2K")
render_engagement_selector(PAGE_KEY)

uploaded = st.file_uploader("Upload Contract Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} contracts")

    with st.expander("🔧 Column Mapping"):
        contract_col = st.selectbox("Contract No", df.columns)
        vendor_col = st.selectbox("Vendor", df.columns)
        start_col = st.selectbox("Start Date", df.columns)
        end_col = st.selectbox("End Date", df.columns)
        value_col = st.selectbox("Contract Value", df.columns)
        last_pay_col = st.selectbox("Last Payment Date", ["None"]+list(df.columns))
        ld_rate_col = st.selectbox("LD Rate % (optional)", ["None"]+list(df.columns))
        ld_rec_col = st.selectbox("LD Recovered (optional)", ["None"]+list(df.columns))

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "contract_col": contract_col,
                "vendor_col": vendor_col,
                "start_col": start_col,
                "end_col": end_col,
                "value_col": value_col,
                "last_pay_col": last_pay_col,
                "ld_rate_col": ld_rate_col,
                "ld_rec_col": ld_rec_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    current_analysis_token = f"{file_sig}:{mapping_sig}"
    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_detection_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = current_analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != current_analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={contract_col:"contract_no", vendor_col:"vendor_name", start_col:"start_date",
                            end_col:"end_date", value_col:"contract_value"})
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    df["contract_value"] = pd.to_numeric(df["contract_value"], errors="coerce").fillna(0)

    today = pd.Timestamp.today()
    df["days_to_expiry"] = (df["end_date"] - today).dt.days

    # Expiring
    expiring = df[df["days_to_expiry"].between(0, 90)]
    st.metric("Contracts Expiring in 90 Days", len(expiring))
    if not expiring.empty:
        st.dataframe(expiring[["contract_no","vendor_name","end_date","days_to_expiry"]], use_container_width=True)

    # Post-expiry payment
    post = pd.DataFrame()
    if last_pay_col != "None":
        df["last_payment_date"] = pd.to_datetime(df[last_pay_col], errors="coerce")
        post = df[df["last_payment_date"] > df["end_date"]]
        if not post.empty:
            st.subheader("🚨 Payment After Contract Expiry Exceptions")
            st.error(f"Payment after expiry: {len(post)} contracts — unauthorized continuation (Purchasing A.4)")
            st.dataframe(post[["contract_no","vendor_name","end_date","last_payment_date"]], use_container_width=True)

    # LD non-recovery
    ld_short = pd.DataFrame()
    if ld_rate_col != "None" and ld_rec_col != "None":
        df["ld_rate_pct"] = pd.to_numeric(df[ld_rate_col], errors="coerce").fillna(0)
        df["ld_recovered"] = pd.to_numeric(df[ld_rec_col], errors="coerce").fillna(0)
        # Simplified: assume all contracts have some delay for demo
        df["ld_due"] = df["contract_value"] * df["ld_rate_pct"] / 100
        ld_short = df[df["ld_recovered"] < df["ld_due"] * 0.9]
        if not ld_short.empty:
            st.subheader("🚨 LD Shortfall Exceptions")
            st.warning(f"LD shortfall: {len(ld_short)} contracts (Purchasing A.7)")
            st.dataframe(ld_short[["contract_no","vendor_name","ld_due","ld_recovered"]].head(20), use_container_width=True)

    # Concentration
    profile = get_industry_profile("manufacturing_fmcg")
    conc_thresh = profile.get("thresholds",{}).get("amc_vendor_concentration_pct",40)
    total = df["contract_value"].sum()
    top_vendor = df.groupby("vendor_name")["contract_value"].sum().nlargest(1)
    if not top_vendor.empty:
        pct = top_vendor.iloc[0] / total * 100
        st.metric("Top Vendor Concentration", f"{pct:.1f}%")
        if pct > conc_thresh:
            st.warning(f"Vendor concentration >{conc_thresh}% — diversification review needed")

    # Stage only true detected exceptions for maker-checker flow
    init_audit_db()
    run_id = file_sig
    staged_rows = []

    if not post.empty:
        post_rows = post.copy()
        post_rows["area"] = "Contract Management"
        post_rows["checklist_ref"] = "Purchasing A.4"
        post_rows["finding"] = post_rows.apply(
            lambda r: (
                f"Payment after contract expiry for contract {r['contract_no']} "
                f"(vendor: {r['vendor_name']})"
            ),
            axis=1,
        )
        post_rows["amount_at_risk"] = post_rows["contract_value"]
        post_rows["risk_band"] = "HIGH"
        post_rows["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        staged_rows.append(
            post_rows[
                ["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date"]
            ]
        )

    if not ld_short.empty:
        ld_rows = ld_short.copy()
        ld_rows["area"] = "Contract Management"
        ld_rows["checklist_ref"] = "Purchasing A.7"
        ld_rows["finding"] = ld_rows.apply(
            lambda r: (
                f"LD shortfall on contract {r['contract_no']} "
                f"(vendor: {r['vendor_name']}, due: ₹{r['ld_due']:,.0f}, recovered: ₹{r['ld_recovered']:,.0f})"
            ),
            axis=1,
        )
        ld_rows["amount_at_risk"] = (ld_rows["ld_due"] - ld_rows["ld_recovered"]).clip(lower=0)
        ld_rows["risk_band"] = "MEDIUM"
        ld_rows["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        staged_rows.append(
            ld_rows[
                ["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date"]
            ]
        )

    all_flagged = pd.concat(staged_rows, ignore_index=True) if staged_rows else pd.DataFrame()
    if not all_flagged.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        staged = stage_findings(
            all_flagged,
            module_name="Contract Management Auditor",
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
    elif not all_flagged.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No actionable contract exceptions detected for staging.")

    # Keep BaseAuditCheck usage for compatibility logging (non-authoritative)
    class _ContractCheck(BaseAuditCheck):
        name = "Contract Management"
        checklist_ref = "Purchasing A.1–A.8"
        sap_tcode_standard_alt = "ME33K / ME2K"
        def detect(self, df: pd.DataFrame) -> pd.DataFrame:
            return df
    checker = _ContractCheck()
    if not all_flagged.empty:
        checker.log_to_db(all_flagged.copy(), area="Contracts", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
        st.caption("📝 Findings logged")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = df if 'df' in locals() and df is not None and not df.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "cnt",
            flagged_df=flagged_rag_df,
            module_name="Contract Management Auditor"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



current_run_id = st.session_state.get(f"{PAGE_KEY}_draft_run_id")
# --- Draft Review ---
if current_run_id:
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption("Use the Select column in the table to confirm/discard. No separate selector is required.")

    engagement_id = get_active_engagement_id(PAGE_KEY)
    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name="Contract Management Auditor",
        status="Draft",
        engagement_id=engagement_id,
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
                "vendor_name": st.column_config.TextColumn("Vendor", disabled=True),
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
            "draft_exceptions_contract_management.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
