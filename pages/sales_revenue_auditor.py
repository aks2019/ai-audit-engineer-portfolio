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

PAGE_KEY = "sales"
MODULE_NAME = "Sales Revenue Auditor"

st.title("📈 Sales & Revenue Integrity Auditor")
render_engagement_selector(PAGE_KEY)
st.caption("SAP HO — CSD, Export, CPD | Ind AS 115 | SAP: VF05 / VA05 / VKM3")

uploaded = st.file_uploader("Upload Sales Register (CSV/Excel)", type=["csv", "xlsx"])

cn_high = pd.DataFrame()
early = pd.DataFrame()

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} invoices")

    with st.expander("🔧 Column Mapping"):
        inv_col = st.selectbox("Invoice No", df.columns, key=f"{PAGE_KEY}_inv")
        amt_col = st.selectbox("Amount", df.columns, key=f"{PAGE_KEY}_amt")
        inv_date_col = st.selectbox("Invoice Date", df.columns, key=f"{PAGE_KEY}_idate")
        disp_col = st.selectbox("Dispatch Date", ["None"] + list(df.columns), key=f"{PAGE_KEY}_disp")
        cn_col = st.selectbox("Credit Note No (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_cn")
        cn_date_col = st.selectbox("Credit Note Date (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_cnd")
        cust_col = st.selectbox("Customer Name", ["None"] + list(df.columns), key=f"{PAGE_KEY}_cust")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "inv_col": inv_col,
                "amt_col": amt_col,
                "inv_date_col": inv_date_col,
                "disp_col": disp_col,
                "cn_col": cn_col,
                "cn_date_col": cn_date_col,
                "cust_col": cust_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={inv_col: "invoice_no", amt_col: "amount", inv_date_col: "invoice_date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    if cust_col != "None":
        df = df.rename(columns={cust_col: "customer_name"})
    else:
        df["customer_name"] = ""

    period_str = datetime.utcnow().strftime("%Y-%m")

    if cn_date_col != "None":
        df["cn_date"] = pd.to_datetime(df[cn_date_col], errors="coerce")
        df["month_end_3d"] = df["cn_date"].notna() & (df["cn_date"].dt.day >= 28)
        q80 = df["amount"].quantile(0.80)
        cn_high = df[df["month_end_3d"] & (df["amount"] > q80)].copy()
        st.subheader("🚨 Exception table — large credit-note pattern near period-end (revenue understatement risk)")
        if not cn_high.empty:
            st.warning(f"**{len(cn_high)}** invoice row(s) with credit-note date in last **3 days** of month and amount above **80th** percentile.")
            st.dataframe(cn_high.head(200), use_container_width=True)
        else:
            st.success("No period-end large credit-note pattern detected (or credit-note dates not populated).")

    if disp_col != "None":
        df["dispatch_date"] = pd.to_datetime(df[disp_col], errors="coerce")
        df["gap_days"] = (df["invoice_date"] - df["dispatch_date"]).dt.days
        early = df[df["gap_days"] < -1].copy()
        st.subheader("🚨 Exception table — invoice dated before dispatch (Ind AS 115 cut-off)")
        if not early.empty:
            st.error(f"**{len(early)}** row(s) — invoice date **before** dispatch date.")
            st.dataframe(early[["invoice_no", "invoice_date", "dispatch_date", "gap_days", "amount"]].head(200), use_container_width=True)
        else:
            st.success("No invoice-before-dispatch dating exceptions.")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "Sales & Revenue"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["customer_name"].fillna("").astype(str).str.strip()
        out["vendor_name"] = out["vendor_name"].replace({"nan": ""})
        out["amount_at_risk"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0).abs().astype(float)
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]]
        )

    if not cn_high.empty:

        def _f_cn(r):
            return (
                f"Period-end credit-note risk — invoice **{r.get('invoice_no','')}**, "
                f"₹{float(r.get('amount',0)):,.0f}, CN date **{r.get('cn_date','')}** (SAP HO / revenue completeness)."
            )

        _append_staging(cn_high, checklist_ref="SAP HO Sales / Revenue completeness", risk_band="HIGH", finding_fn=_f_cn, kind="cn-end")

    if not early.empty:

        def _f_early(r):
            return (
                f"Ind AS 115 timing — invoice **{r.get('invoice_no','')}** dated **{r.get('invoice_date','')}** "
                f"before dispatch **{r.get('dispatch_date','')}** (gap **{int(r.get('gap_days') or 0)}** days)."
            )

        _append_staging(early, checklist_ref="Ind AS 115 — Performance obligations / cut-off", risk_band="HIGH", finding_fn=_f_early, kind="115")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [cn_high, early] if x is not None and not x.empty]
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
        st.info("No sales/revenue exceptions to stage.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("sales", flagged_df=flagged_rag_df, module_name=MODULE_NAME)
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
                "vendor_name": st.column_config.TextColumn("Customer", disabled=True),
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
            "draft_exceptions_sales_revenue_auditor.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
