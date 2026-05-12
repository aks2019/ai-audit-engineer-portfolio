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
from utils.compliance_loader import get_industry_profile
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "rec"
MODULE_NAME = "Receivables Bad Debt"

st.title("💰 Customer Receivables & Bad Debt Detector")
render_engagement_selector(PAGE_KEY)
st.caption("Depot 5 / SAP HO 15 | SAP: FBL5N / S_ALR_87012197")

uploaded = st.file_uploader("Upload Customer Outstanding (CSV/Excel)", type=["csv", "xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} customer records")

    with st.expander("🔧 Column Mapping"):
        amt_col = st.selectbox("Outstanding Amount", df.columns, key=f"{PAGE_KEY}_amt")
        days_col = st.selectbox("Days Overdue", df.columns, key=f"{PAGE_KEY}_days")
        cust_col = st.selectbox("Customer Name", df.columns, key=f"{PAGE_KEY}_cust")
        limit_col = st.selectbox("Credit Limit (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_lim")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(str({"amt_col": amt_col, "days_col": days_col, "cust_col": cust_col, "limit_col": limit_col}).encode("utf-8")).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={amt_col: "amount", days_col: "days_overdue", cust_col: "customer_name"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["days_overdue"] = pd.to_numeric(df["days_overdue"], errors="coerce").fillna(0)

    if limit_col != "None":
        df = df.rename(columns={limit_col: "credit_limit"})
        df["credit_limit"] = pd.to_numeric(df["credit_limit"], errors="coerce").fillna(0)
        df["limit_breach"] = df["amount"] > df["credit_limit"]
    else:
        df["credit_limit"] = 0.0
        df["limit_breach"] = False

    profile = get_industry_profile("manufacturing_fmcg")
    critical_days = profile.get("thresholds", {}).get("days_overdue_critical", 60)
    period_str = datetime.utcnow().strftime("%Y-%m")

    df["opportunity_cost"] = df["amount"] * 0.12 / 365 * df["days_overdue"]
    critical = df[df["days_overdue"] > critical_days].copy()
    limit_breach = df[df["limit_breach"]].copy()
    ml_risk = pd.DataFrame()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Outstanding", f"{df['amount'].sum():,.0f} ₹")
    col2.metric(f">{critical_days} Days Critical", f"{len(critical):,}")
    col3.metric("Opportunity Cost (12%)", f"{df['opportunity_cost'].sum():,.0f} ₹")

    st.subheader(f"🚨 Exception table — critical overdue (> {critical_days} days — Depot 5 / HO 15)")
    if not critical.empty:
        st.warning(f"**{len(critical)}** customer balance(s) past **{critical_days}** days.")
        st.dataframe(critical[["customer_name", "amount", "days_overdue", "opportunity_cost"]].nlargest(200, "amount"), use_container_width=True)
    else:
        st.success("No balances above the critical-days threshold.")

    st.subheader("🚨 Exception table — credit limit breaches")
    if limit_col != "None":
        if not limit_breach.empty:
            st.warning(f"**{len(limit_breach)}** limit breach(es).")
            st.dataframe(limit_breach[["customer_name", "amount", "credit_limit"]].head(200), use_container_width=True)
        else:
            st.success("No credit limit breaches (where limit was mapped).")
    else:
        st.info("Credit limit column not mapped — limit breach rule not applied.")

    if len(df) >= 20:
        try:
            from xgboost import XGBClassifier

            X = df[["amount", "days_overdue"]].fillna(0)
            y = (df["days_overdue"] > critical_days).astype(int)
            xgb = XGBClassifier(n_estimators=100, max_depth=3, random_state=42, eval_metric="logloss", use_label_encoder=False)
            xgb.fit(X, y)
            df["bad_debt_prob"] = xgb.predict_proba(X)[:, 1]
            ml_risk = df[df["bad_debt_prob"] >= 0.5].nlargest(200, "bad_debt_prob").copy()
            st.subheader("🚨 Exception table — elevated bad-debt probability (XGBoost ≥ 50%)")
            if not ml_risk.empty:
                st.dataframe(ml_risk[["customer_name", "amount", "days_overdue", "bad_debt_prob"]], use_container_width=True)
            else:
                st.success("No customers ≥50% modeled bad-debt probability.")
            st.subheader("Top 10 modeled risk (preview)")
            st.dataframe(df.nlargest(10, "bad_debt_prob")[["customer_name", "amount", "days_overdue", "bad_debt_prob"]], use_container_width=True)
        except Exception as e:
            st.info(f"XGBoost skipped: {e}")
            df["bad_debt_prob"] = np.nan

    iso_out = pd.DataFrame()
    num_cols = ["amount", "days_overdue"]
    if len(df) >= 10:
        Xi = df[num_cols].fillna(0)
        iso = IsolationForest(contamination=0.05, random_state=42)
        pred = iso.fit_predict(Xi)
        iso_out = df[pred == -1].copy()
        st.subheader("🚨 Exception table — statistical outliers (IsolationForest)")
        if not iso_out.empty:
            st.dataframe(iso_out[["customer_name", "amount", "days_overdue"]].head(200), use_container_width=True)
        else:
            st.success("No multivariate outliers on amount × days overdue.")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "Receivables"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out["customer_name"].map(lambda x: str(x).strip() if pd.notna(x) else "")
        out["amount_at_risk"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0).abs().astype(float)
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]]
        )

    if not critical.empty:

        def _f_crit(r):
            return (
                f"Critical overdue — **{r.get('customer_name','')}**, ₹{float(r.get('amount',0)):,.0f}, "
                f"**{int(float(r.get('days_overdue',0)))}** days (> {critical_days}), "
                f"opp. cost ₹{float(r.get('opportunity_cost',0)):,.0f}"
            )

        _append_staging(critical, checklist_ref=f"SAP Depot 5 / HO 15 (> {critical_days}d)", risk_band="HIGH", finding_fn=_f_crit, kind="crit")

    if limit_col != "None" and not limit_breach.empty:

        def _f_lim(r):
            return (
                f"Credit limit breach — **{r.get('customer_name','')}** outstanding ₹{float(r.get('amount',0)):,.0f} "
                f"vs limit ₹{float(r.get('credit_limit',0)):,.0f}"
            )

        _append_staging(limit_breach, checklist_ref="Credit / HO 15", risk_band="MEDIUM", finding_fn=_f_lim, kind="lim")

    if "bad_debt_prob" in df.columns and not ml_risk.empty:

        def _f_ml(r):
            p = float(r.get("bad_debt_prob") or 0)
            return f"Elevated bad-debt probability **{p:.0%}** — **{r.get('customer_name','')}**, ₹{float(r.get('amount',0)):,.0f}, {int(float(r.get('days_overdue',0)))}d overdue"

        _append_staging(ml_risk, checklist_ref="Analytics / Provision review", risk_band="HIGH", finding_fn=_f_ml, kind="xgb")

    if not iso_out.empty:

        def _f_iso(r):
            return (
                f"Statistical receivables outlier — **{r.get('customer_name','')}** "
                f"₹{float(r.get('amount',0)):,.0f} / **{int(float(r.get('days_overdue',0)))}** days overdue"
            )

        _append_staging(iso_out, checklist_ref="FBL5N / analytics", risk_band="MEDIUM", finding_fn=_f_iso, kind="iso")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [critical, limit_breach, ml_risk, iso_out] if x is not None and not x.empty]
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
        st.info("No receivables exceptions to stage.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("rec", flagged_df=flagged_rag_df, module_name=MODULE_NAME)
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
            "draft_exceptions_receivables_bad_debt.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
