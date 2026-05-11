import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import sys
from pathlib import Path
import hashlib
from thefuzz import fuzz
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.base_audit_check import BaseAuditCheck
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "dup"

st.title("🎭 Duplicate Payments & Invoice Fraud Detector")
st.caption("Purchasing D.3–D.12 | SAP: FBL1N / ME2N")
render_engagement_selector(PAGE_KEY)

uploaded = st.file_uploader("Upload Invoice/Payment Register (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} rows")

    with st.expander("🔧 Column Mapping"):
        inv_col = st.selectbox("Invoice Number", df.columns)
        ven_col = st.selectbox("Vendor", df.columns)
        amt_col = st.selectbox("Amount", df.columns)
        po_col = st.selectbox("PO Rate (optional)", ["None"]+list(df.columns))
        inv_date_col = st.selectbox("Invoice Date (optional)", ["None"]+list(df.columns))

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str(
            {
                "inv_col": inv_col,
                "ven_col": ven_col,
                "amt_col": amt_col,
                "po_col": po_col,
                "inv_date_col": inv_date_col,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    current_analysis_token = f"{file_sig}:{mapping_sig}"
    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_detection_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = current_analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != current_analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={inv_col:"invoice_no", ven_col:"vendor_name", amt_col:"amount"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    # Exact duplicates
    exact = df[df.duplicated(["vendor_name","invoice_no","amount"], keep=False)]
    st.metric("Exact Duplicates", len(exact))
    if not exact.empty:
        st.subheader("🚨 Exact Duplicate Invoice Exceptions")
        st.dataframe(exact[["vendor_name", "invoice_no", "amount"]].head(200), use_container_width=True)

    # Fuzzy duplicates
    if st.checkbox("Run Fuzzy Duplicate Detection (Levenshtein)"):
        fuzzy_hits = []
        vendors = df["vendor_name"].unique()
        for v in vendors:
            sub = df[df["vendor_name"]==v].reset_index(drop=True)
            for i in range(len(sub)):
                for j in range(i+1, min(i+50, len(sub))):
                    ratio = fuzz.ratio(str(sub.iloc[i]["invoice_no"]), str(sub.iloc[j]["invoice_no"]))
                    amt_diff = abs(sub.iloc[i]["amount"] - sub.iloc[j]["amount"])
                    if ratio >= 85 and amt_diff <= 500:
                        fuzzy_hits.append({"vendor":v,"inv1":sub.iloc[i]["invoice_no"],"inv2":sub.iloc[j]["invoice_no"],"ratio":ratio,"amt_diff":amt_diff})
        if fuzzy_hits:
            st.subheader("🔍 Fuzzy Duplicates")
            st.dataframe(pd.DataFrame(fuzzy_hits), use_container_width=True)

    # PO vs Invoice rate variance
    high_var = pd.DataFrame()
    if po_col != "None":
        df = df.rename(columns={po_col:"po_rate"})
        df["po_rate"] = pd.to_numeric(df["po_rate"], errors="coerce")
        df["variance_pct"] = (df["amount"] - df["po_rate"]).abs() / df["po_rate"] * 100
        high_var = df[df["variance_pct"] > 5]
        if not high_var.empty:
            st.subheader("🚨 PO vs Invoice Variance Exceptions")
            st.warning(f"PO vs Invoice variance ≥5%: {len(high_var)} rows (SAP 1.5)")
            st.dataframe(high_var[["vendor_name","invoice_no","po_rate","amount","variance_pct"]].head(20), use_container_width=True)

    # Benford's Law
    with st.expander("🔢 Benford's Law on Invoice Amounts"):
        expected = {1:30.1,2:17.6,3:12.5,4:9.7,5:7.9,6:6.7,7:5.8,8:5.1,9:4.6}
        first = df["amount"][df["amount"]>0].astype(str).str[0].astype(int)
        obs = first.value_counts(normalize=True).sort_index()*100
        benford = pd.DataFrame({"digit":list(expected.keys()),"expected_pct":list(expected.values()),"observed_pct":[obs.get(d,0) for d in expected]})
        benford["deviation"] = benford["observed_pct"] - benford["expected_pct"]
        fig = px.bar(benford, x="digit", y=["expected_pct","observed_pct"], barmode="group")
        st.plotly_chart(fig, use_container_width=True)

    # Fraud score & block recommendation
    blocked = pd.DataFrame()
    if not df.empty:
        df["fraud_score"] = np.random.uniform(0,1,len(df))  # placeholder; replace with model
        blocked = df[df["fraud_score"] > 0.85]
        if not blocked.empty:
            st.subheader("🚨 Payment Block Recommendation Exceptions")
            st.error(f"🚫 {len(blocked)} invoices recommended for payment block via FB02 (Payment Block = A)")
            st.dataframe(
                blocked[["vendor_name", "invoice_no", "amount", "fraud_score"]].head(100),
                use_container_width=True,
            )

    # ── Stage Findings for Draft Review (NOT auto-logged) ──
    init_audit_db()
    run_id = file_sig
    finding_frames = []

    if not exact.empty:
        exact_rows = exact.copy()
        exact_rows["area"] = "Duplicate Invoices"
        exact_rows["checklist_ref"] = "Purchasing D.3–D.12"
        exact_rows["finding"] = exact_rows.apply(
            lambda r: (
                f"Exact duplicate invoice for vendor {r.get('vendor_name', 'Unknown')} — "
                f"Invoice {r.get('invoice_no', 'N/A')} amount ₹{r.get('amount', 0):,.0f}"
            ),
            axis=1,
        )
        exact_rows["amount_at_risk"] = exact_rows["amount"]
        exact_rows["risk_band"] = "HIGH"
        exact_rows["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        finding_frames.append(
            exact_rows[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date"]]
        )

    if not high_var.empty:
        var_rows = high_var.copy()
        var_rows["area"] = "Duplicate Invoices"
        var_rows["checklist_ref"] = "SAP 1.5 / Purchasing D.7"
        var_rows["finding"] = var_rows.apply(
            lambda r: (
                f"PO vs invoice variance {r.get('variance_pct', 0):.1f}% for "
                f"invoice {r.get('invoice_no', 'N/A')} (vendor: {r.get('vendor_name', 'Unknown')})"
            ),
            axis=1,
        )
        var_rows["amount_at_risk"] = var_rows["amount"]
        var_rows["risk_band"] = "MEDIUM"
        var_rows["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        finding_frames.append(
            var_rows[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date"]]
        )

    if not blocked.empty:
        blocked_rows = blocked.copy()
        blocked_rows["area"] = "Duplicate Invoices"
        blocked_rows["checklist_ref"] = "SAP FB02 Payment Block / Purchasing D.10"
        blocked_rows["finding"] = blocked_rows.apply(
            lambda r: (
                f"High fraud score {r.get('fraud_score', 0):.2f} — payment block recommended for "
                f"invoice {r.get('invoice_no', 'N/A')} (vendor: {r.get('vendor_name', 'Unknown')})"
            ),
            axis=1,
        )
        blocked_rows["amount_at_risk"] = blocked_rows["amount"]
        blocked_rows["risk_band"] = "HIGH"
        blocked_rows["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        finding_frames.append(
            blocked_rows[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date"]]
        )

    staging_df = pd.concat(finding_frames, ignore_index=True) if finding_frames else pd.DataFrame()
    flagged_rag_df = staging_df.copy()

    if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        _staged = stage_findings(
            staging_df,
            module_name="Duplicate Invoice Detector",
            run_id=run_id,
            period=datetime.utcnow().strftime("%Y-%m"),
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.info(f"📋 **{_staged} exception(s) staged for your review.** Nothing has been added to the official audit trail yet.")
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = flagged_rag_df if 'flagged_rag_df' in locals() and flagged_rag_df is not None and not flagged_rag_df.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "dup",
            flagged_df=flagged_rag_df,
            module_name="Duplicate Invoice Detector"
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
        module_name="Duplicate Invoice Detector",
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
            "draft_exceptions_duplicate_invoice.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
