import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
from sklearn.ensemble import IsolationForest
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db
from utils.audit_db import (
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.base_audit_check import BaseAuditCheck
from utils.compliance_loader import load_compliance_calendar
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "brs"

st.title("🏦 BRS Anomaly & Auto-Matching Agent")
render_engagement_selector(PAGE_KEY)
st.caption("Bank Reconciliation + Treasury Checklist A.2, A.3, A.10, A.13, A.14e, A.20 | SAP: FF67 + FBL3N")

bank_file = st.file_uploader("Upload Bank Statement (CSV/Excel)", type=["csv","xlsx"], key="bank")
gl_file   = st.file_uploader("Upload GL Extract (CSV/Excel)", type=["csv","xlsx"], key="gl")

if bank_file and gl_file:
    bdf = pd.read_csv(bank_file) if bank_file.name.endswith(".csv") else pd.read_excel(bank_file)
    gdf = pd.read_excel(gl_file) if gl_file.name.endswith(".xlsx") else pd.read_csv(gl_file)
    st.success(f"Loaded Bank: {len(bdf):,} rows | GL: {len(gdf):,} rows")

    with st.expander("🔧 Column Mapping"):
        b_amount = st.selectbox("Bank Amount", bdf.columns, key="b_amt")
        b_date   = st.selectbox("Bank Date", bdf.columns, key="b_dt")
        b_narr   = st.selectbox("Bank Narration (optional)", ["None"]+list(bdf.columns), key="b_narr")
        g_amount = st.selectbox("GL Amount", gdf.columns, key="g_amt")
        g_date   = st.selectbox("GL Date", gdf.columns, key="g_dt")
        g_narr   = st.selectbox("GL Narration (optional)", ["None"]+list(gdf.columns), key="g_narr")

    analysis_token = hashlib.sha256(
        (
            bank_file.getvalue()
            + gl_file.getvalue()
            + str(
                {
                    "b_amount": b_amount,
                    "b_date": b_date,
                    "b_narr": b_narr,
                    "g_amount": g_amount,
                    "g_date": g_date,
                    "g_narr": g_narr,
                }
            ).encode("utf-8")
        )
    ).hexdigest()[:16]
    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_detection_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    bdf = bdf.rename(columns={b_amount:"amount", b_date:"date"})
    gdf = gdf.rename(columns={g_amount:"amount", g_date:"date"})
    bdf["amount"] = pd.to_numeric(bdf["amount"], errors="coerce").fillna(0)
    gdf["amount"] = pd.to_numeric(gdf["amount"], errors="coerce").fillna(0)
    bdf["date"] = pd.to_datetime(bdf["date"], errors="coerce")
    gdf["date"] = pd.to_datetime(gdf["date"], errors="coerce")

    with st.spinner("Auto-matching bank vs GL..."):
        matched = []
        unmatched_bank = []
        for _, brow in bdf.iterrows():
            hits = gdf[
                (gdf["amount"].abs() - abs(brow["amount"])).abs() <= 0.01
            ].copy()
            if not hits.empty:
                hits["day_diff"] = (hits["date"] - brow["date"]).dt.days.abs()
                best = hits.sort_values("day_diff").head(1)
                if not best.empty and best.iloc[0]["day_diff"] <= 3:
                    matched.append({"bank_amt": brow["amount"], "gl_amt": best.iloc[0]["amount"],
                                    "bank_date": brow["date"], "gl_date": best.iloc[0]["date"],
                                    "days_diff": best.iloc[0]["day_diff"]})
                    gdf = gdf.drop(best.index)
                    continue
            unmatched_bank.append(brow)
        unmatched_bank = pd.DataFrame(unmatched_bank)

    st.metric("Auto-Matched", len(matched))
    st.metric("Unmatched Bank Items", len(unmatched_bank))

    if not unmatched_bank.empty:
        st.subheader("⚠️ Unmatched Bank Items")
        st.dataframe(unmatched_bank, use_container_width=True)

        # Rules
        rules = []
        if not unmatched_bank.empty:
            cal = load_compliance_calendar()
            # Stale cheques >6 months
            unmatched_bank["age_days"] = (datetime.today() - unmatched_bank["date"]).dt.days
            stale = unmatched_bank[unmatched_bank["age_days"] > 180]
            if not stale.empty:
                rules.append(f"Stale cheques >6 months: {len(stale)} (Treasury A.13)")
            # Cash not deposited same day (A.20) — simplistic: amount > 50k and age > 0
            cash_delay = unmatched_bank[(unmatched_bank["amount"].abs() > 50000) & (unmatched_bank["age_days"] > 0)]
            if not cash_delay.empty:
                rules.append(f"Cash not deposited same day: {len(cash_delay)} (Treasury A.20)")
        for r in rules:
            st.warning(r)

        # IsolationForest on unmatched
        if len(unmatched_bank) >= 10:
            X = unmatched_bank[["amount"]].copy().fillna(0)
            iso = IsolationForest(contamination=0.05, random_state=42)
            unmatched_bank["anomaly_score"] = iso.fit_predict(X)
            high_risk = unmatched_bank[unmatched_bank["anomaly_score"] == -1]
            if not high_risk.empty:
                st.subheader("🚨 High-Risk Unmatched Items (IsolationForest)")
                st.dataframe(high_risk, use_container_width=True)

        # ── Stage Findings for Draft Review (NOT auto-logged) ──
        init_audit_db()
        run_id = hashlib.sha256(bank_file.getvalue() + gl_file.getvalue()).hexdigest()[:12]
        
        # Prepare findings DataFrame with required columns for staging
        staging_df = unmatched_bank.head(100).copy()
        staging_df["area"] = "Bank Reconciliation"
        staging_df["checklist_ref"] = "Treasury A.2/A.3"
        staging_df["finding"] = staging_df.apply(
            lambda r: f"Unmatched bank item: ₹{abs(r.get('amount', 0)):,.0f} on {r.get('date', 'Unknown date')}", 
            axis=1
        )
        staging_df["amount_at_risk"] = staging_df["amount"].abs()
        staging_df["risk_band"] = "HIGH"
        staging_df["vendor_name"] = staging_df.get("vendor_name", "")
        staging_df["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        
        if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
            _staged = stage_findings(
                staging_df,
                module_name="Brs Reconciliation",
                run_id=run_id,
                period=datetime.utcnow().strftime("%Y-%m"),
                source_file_name=getattr(bank_file, "name", "manual"),
                engagement_id=get_active_engagement_id(PAGE_KEY),
            )
            st.info(f"📋 **{_staged} exception(s) staged for your review.** Nothing has been added to the official audit trail yet.")
            st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        elif not staging_df.empty:
            st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = unmatched_bank if 'unmatched_bank' in locals() and unmatched_bank is not None and not unmatched_bank.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "brs",
            flagged_df=flagged_rag_df,
            module_name="Brs Reconciliation"
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
        module_name="Brs Reconciliation",
        status="Draft",
        engagement_id=get_active_engagement_id(PAGE_KEY),
    )

    if drafts.empty:
        st.info("No draft exceptions pending for the current run.")
    else:
        default_select_all = st.checkbox(
            "Select all draft exceptions",
            value=False,
            key=f"{PAGE_KEY}_select_all_drafts",
        )
        st.caption(f"**{len(drafts)} draft exception(s)** pending review.")

        review_df = drafts[["id", "area", "finding", "amount_at_risk", "risk_band", "vendor_name"]].copy()
        review_df.insert(0, "select", default_select_all)

        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "area": st.column_config.TextColumn("Area", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn(
                    "Risk Band",
                    options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                ),
                "vendor_name": st.column_config.TextColumn("Vendor", disabled=True),
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
            "draft_exceptions_brs.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
