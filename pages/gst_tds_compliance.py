import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.compliance_loader import load_compliance_calendar, get_tds_rate, get_tds_threshold, get_gst_due_day
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "gst"
MODULE_NAME = "Gst Tds Compliance"

render_engagement_selector(PAGE_KEY)

if f"{PAGE_KEY}_gst_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_gst_run_id"] = None
if f"{PAGE_KEY}_tds_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_tds_run_id"] = None
if f"{PAGE_KEY}_gst_rag_df" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_gst_rag_df"] = None
if f"{PAGE_KEY}_tds_rag_df" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_tds_rag_df"] = None


def _render_inline_review(run_id: str, section_label: str, widget_prefix: str):
    if not run_id:
        return
    st.divider()
    st.subheader(f"Review & Confirm Findings — {section_label}")
    st.caption("Use the Select column in the table to confirm/discard. No separate selector is required.")

    engagement_id = get_active_engagement_id(PAGE_KEY)
    drafts = load_draft_findings(
        run_id=run_id,
        module_name=MODULE_NAME,
        status="Draft",
        engagement_id=engagement_id,
    )
    if drafts.empty:
        st.info("No draft exceptions pending for this run.")
        return

    select_all = st.checkbox(
        "Select all draft exceptions",
        value=False,
        key=f"{widget_prefix}_select_all",
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
            "vendor_name": st.column_config.TextColumn("Vendor / Ref", disabled=True),
            "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
            "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
            "risk_band": st.column_config.SelectboxColumn(
                "Risk Band",
                options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            ),
        },
        key=f"{widget_prefix}_draft_editor",
    )

    selected_ids = edited.loc[edited["select"] == True, "id"].astype(int).tolist()
    confirmed_by = st.text_input(
        "Confirmed / Reviewed by (auditor name)",
        value="Auditor",
        key=f"{widget_prefix}_confirmed_by",
    )

    c_confirm, c_discard = st.columns(2)
    with c_confirm:
        if st.button(
            "Confirm Selected to Official Audit Trail",
            type="primary",
            use_container_width=True,
            key=f"{widget_prefix}_confirm_btn",
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
            key=f"{widget_prefix}_discard_reason",
        )
        if st.button(
            "Discard Selected (False Positives)",
            use_container_width=True,
            key=f"{widget_prefix}_discard_btn",
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
        f"draft_exceptions_{widget_prefix}.csv",
        "text/csv",
        key=f"{widget_prefix}_export_drafts",
    )


tab1, tab2 = st.tabs(["GST Compliance", "TDS Compliance"])

with tab1:
    st.title("🧾 GST Compliance Mismatch Engine")
    st.caption("GSTR-2A vs Books | ITC Eligibility | Filing Timeliness")

    gstr_file = st.file_uploader("Upload GSTR-2A (Excel/CSV)", type=["csv", "xlsx"], key="gstr")
    books_file = st.file_uploader("Upload Books Data (Excel/CSV)", type=["csv", "xlsx"], key="books")

    if gstr_file and books_file:
        gstr = pd.read_excel(gstr_file) if gstr_file.name.endswith(".xlsx") else pd.read_csv(gstr_file)
        books = pd.read_excel(books_file) if books_file.name.endswith(".xlsx") else pd.read_csv(books_file)

        with st.expander("🔧 Column Mapping"):
            g_inv = st.selectbox("GSTR Invoice No", gstr.columns, key="g_inv")
            g_amt = st.selectbox("GSTR Taxable Amount", gstr.columns, key="g_amt")
            b_inv = st.selectbox("Books Invoice No", books.columns, key="b_inv")
            b_amt = st.selectbox("Books Taxable Amount", books.columns, key="b_amt")

        gst_token = hashlib.sha256(
            gstr_file.getvalue() + books_file.getvalue() + json.dumps(
                {"g_inv": g_inv, "g_amt": g_amt, "b_inv": b_inv, "b_amt": b_amt},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]

        if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_gst_run_btn"):
            st.session_state[f"{PAGE_KEY}_gst_analysis_token"] = gst_token

        if st.session_state.get(f"{PAGE_KEY}_gst_analysis_token") != gst_token:
            st.info("Map columns, then click **Run Detection**.")
            st.stop()

        gstr = gstr.rename(columns={g_inv: "invoice_no", g_amt: "amount"})
        books = books.rename(columns={b_inv: "invoice_no", b_amt: "amount"})
        gstr["amount"] = pd.to_numeric(gstr["amount"], errors="coerce").fillna(0)
        books["amount"] = pd.to_numeric(books["amount"], errors="coerce").fillna(0)

        merged = pd.merge(books, gstr, on="invoice_no", how="outer", suffixes=("_books", "_gstr"), indicator=True)

        type1 = merged[merged["_merge"] == "left_only"]
        type2 = merged[merged["_merge"] == "right_only"]
        both = merged[merged["_merge"] == "both"]
        type3 = both[(both["amount_books"] - both["amount_gstr"]).abs() > 100]

        st.subheader("📊 GST reconciliation summary")
        st.metric("Books not in 2A (ITC at risk)", len(type1))
        st.metric("2A not in books", len(type2))
        st.metric("Amount mismatch >₹100", len(type3))

        if not type1.empty:
            st.subheader("🚨 Type 1 — Books not in GSTR-2A (ITC at risk)")
            st.dataframe(type1.head(100), use_container_width=True)
        if not type2.empty:
            st.subheader("🚨 Type 2 — GSTR-2A not in books")
            st.dataframe(type2.head(100), use_container_width=True)
        if not type3.empty:
            st.subheader("🚨 Type 3 — Amount mismatch (Books vs 2A)")
            st.dataframe(type3.head(100), use_container_width=True)

        cal = load_compliance_calendar()
        due_day = get_gst_due_day("GSTR-3B_category_1")
        st.info(f"GSTR-3B Category 1 due day: {due_day} of following month (from compliance_calendar.yaml)")

        period_str = datetime.utcnow().strftime("%Y-%m")
        init_audit_db()
        file_sig = hashlib.sha256(gstr_file.getvalue() + books_file.getvalue()).hexdigest()[:12]
        run_id = f"gst-{file_sig}:{gst_token[:8]}:v1"

        def _vendor_from_row(r: pd.Series) -> str:
            for c in r.index:
                if "vendor" in str(c).lower() or "supplier" in str(c).lower():
                    v = r.get(c)
                    if pd.notna(v) and str(v).strip():
                        return str(v).strip()
            return str(r.get("invoice_no", "Unknown"))

        frames = []
        seq = [0]

        def _next_ref(prefix: str) -> str:
            seq[0] += 1
            return f"{PAGE_KEY}-gst-{run_id}-{prefix}-{seq[0]}"

        if not type1.empty:
            t = type1.head(500).copy()
            t["area"] = "GST Compliance"
            t["checklist_ref"] = "GST Section 16 / GSTR-2A Rules"
            t["vendor_name"] = t.apply(_vendor_from_row, axis=1)
            t["amount_at_risk"] = pd.to_numeric(t.get("amount_books", 0), errors="coerce").fillna(0).abs()
            t["risk_band"] = "HIGH"
            t["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            t["period"] = period_str
            t["source_row_ref"] = [_next_ref("t1") for _ in range(len(t))]
            t["finding"] = t.apply(
                lambda r: (
                    f"Books not in GSTR-2A: Invoice {r.get('invoice_no', 'N/A')} — "
                    f"ITC at risk ₹{float(r.get('amount_books', 0) or 0):,.0f}"
                ),
                axis=1,
            )
            frames.append(
                t[
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

        if not type3.empty:
            t = type3.head(500).copy()
            t["area"] = "GST Compliance"
            t["checklist_ref"] = "GST Section 16 / GSTR-2A Rules"
            t["vendor_name"] = t.apply(_vendor_from_row, axis=1)
            t["amount_at_risk"] = (
                t[["amount_books", "amount_gstr"]].fillna(0).abs().max(axis=1).astype(float)
            )
            t["risk_band"] = "HIGH"
            t["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            t["period"] = period_str
            t["source_row_ref"] = [_next_ref("t3") for _ in range(len(t))]
            t["finding"] = t.apply(
                lambda r: (
                    f"GST amount mismatch: Invoice {r.get('invoice_no', 'N/A')} — "
                    f"Books ₹{float(r.get('amount_books', 0) or 0):,.0f} vs GSTR ₹{float(r.get('amount_gstr', 0) or 0):,.0f}"
                ),
                axis=1,
            )
            frames.append(
                t[
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

        staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        rag_parts = [x for x in [type1, type3] if x is not None and not x.empty]
        if rag_parts:
            st.session_state[f"{PAGE_KEY}_gst_rag_df"] = pd.concat(rag_parts, ignore_index=True).head(200)
        else:
            st.session_state[f"{PAGE_KEY}_gst_rag_df"] = None

        if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_gst_run_id") != run_id:
            staged = stage_findings(
                staging_df,
                module_name=MODULE_NAME,
                run_id=run_id,
                period=period_str,
                source_file_name=f"{getattr(gstr_file, 'name', 'gstr')}+{getattr(books_file, 'name', 'books')}",
                engagement_id=get_active_engagement_id(PAGE_KEY),
            )
            st.session_state[f"{PAGE_KEY}_gst_run_id"] = run_id
            st.info(
                f"📋 **{staged} GST exception(s) staged for your review.** "
                "Nothing has been added to the official audit trail until you confirm below."
            )
        elif not staging_df.empty:
            st.caption(f"📋 GST exceptions already staged (run: `{run_id}`). Review below.")
        else:
            st.info("No GST exceptions to stage for this reconciliation.")

        _render_inline_review(st.session_state.get(f"{PAGE_KEY}_gst_run_id"), "GST", f"{PAGE_KEY}_gst")

with tab2:
    st.title("💸 TDS Compliance Engine")
    st.caption("Rate validation | Deposit timeliness | Interest calculation")

    tds_file = st.file_uploader("Upload TDS Ledger (Excel/CSV)", type=["csv", "xlsx"], key="tds")
    if tds_file:
        tds = pd.read_excel(tds_file) if tds_file.name.endswith(".xlsx") else pd.read_csv(tds_file)

        with st.expander("🔧 Column Mapping"):
            sec_col = st.selectbox("TDS Section", tds.columns, key="tds_sec")
            amt_col = st.selectbox("Payment Amount", tds.columns, key="tds_amt")
            rate_col = st.selectbox("TDS Deducted Rate % (optional)", ["None"] + list(tds.columns), key="tds_rate")
            payee_col = st.selectbox("Payee Type (Individual/Company)", ["None"] + list(tds.columns), key="tds_payee")

        tds_token = hashlib.sha256(
            tds_file.getvalue() + json.dumps(
                {"sec_col": sec_col, "amt_col": amt_col, "rate_col": rate_col, "payee_col": payee_col},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]

        if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_tds_run_btn"):
            st.session_state[f"{PAGE_KEY}_tds_analysis_token"] = tds_token

        if st.session_state.get(f"{PAGE_KEY}_tds_analysis_token") != tds_token:
            st.info("Map columns, then click **Run Detection**.")
            st.stop()

        tds = tds.rename(columns={sec_col: "section", amt_col: "amount"})
        tds["amount"] = pd.to_numeric(tds["amount"], errors="coerce").fillna(0)
        cal = load_compliance_calendar()

        errors = []
        for _, row in tds.iterrows():
            sec = str(row["section"])
            payee = str(row.get(payee_col, "individual") if payee_col != "None" else "individual").lower()
            expected = get_tds_rate(sec, "company" if "company" in payee else "individual")
            threshold = get_tds_threshold(sec)
            try:
                expected = float(expected)
            except (TypeError, ValueError):
                continue
            if expected and row["amount"] >= threshold:
                if rate_col != "None" and pd.notna(row.get(rate_col)):
                    actual = float(row[rate_col])
                    if abs(actual - expected) > 0.1:
                        vn = row.get(payee_col, "Unknown") if payee_col != "None" else "Unknown"
                        errors.append(
                            {
                                "section": sec,
                                "amount": row["amount"],
                                "expected": expected,
                                "actual": actual,
                                "vendor_name": vn,
                            }
                        )

        st.subheader("📊 TDS rate validation")
        if errors:
            err_df = pd.DataFrame(errors)
            st.subheader("🚨 TDS rate mismatches")
            st.dataframe(err_df, use_container_width=True)

            period_str = datetime.utcnow().strftime("%Y-%m")
            init_audit_db()
            file_sig = hashlib.sha256(tds_file.getvalue()).hexdigest()[:12]
            run_id = f"tds-{file_sig}:{tds_token[:8]}:v1"

            staging_df = err_df.head(500).copy()
            staging_df["area"] = "TDS Compliance"
            staging_df["checklist_ref"] = "Income Tax Section 192-206"
            staging_df["amount_at_risk"] = pd.to_numeric(staging_df["amount"], errors="coerce").fillna(0).abs()
            staging_df["risk_band"] = "HIGH"
            staging_df["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            staging_df["period"] = period_str
            staging_df["vendor_name"] = staging_df["vendor_name"].astype(str)
            seq = [0]

            def _tds_ref():
                seq[0] += 1
                return f"{PAGE_KEY}-tds-{run_id}-{seq[0]}"

            staging_df["source_row_ref"] = [_tds_ref() for _ in range(len(staging_df))]
            staging_df["finding"] = staging_df.apply(
                lambda r: (
                    f"TDS rate mismatch Section {r.get('section', 'N/A')}: "
                    f"expected {float(r.get('expected', 0)):.2f}% vs actual {float(r.get('actual', 0)):.2f}% "
                    f"on payment ₹{float(r.get('amount', 0)):,.0f}"
                ),
                axis=1,
            )
            staging_df = staging_df[
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

            st.session_state[f"{PAGE_KEY}_tds_rag_df"] = err_df.head(200)

            if st.session_state.get(f"{PAGE_KEY}_tds_run_id") != run_id:
                staged = stage_findings(
                    staging_df,
                    module_name=MODULE_NAME,
                    run_id=run_id,
                    period=period_str,
                    source_file_name=getattr(tds_file, "name", "manual"),
                    engagement_id=get_active_engagement_id(PAGE_KEY),
                )
                st.session_state[f"{PAGE_KEY}_tds_run_id"] = run_id
                st.info(
                    f"📋 **{staged} TDS exception(s) staged for your review.** "
                    "Nothing has been added to the official audit trail until you confirm below."
                )
            else:
                st.caption(f"📋 TDS exceptions already staged (run: `{run_id}`). Review below.")
        else:
            st.success("No TDS rate mismatches detected.")
            st.session_state[f"{PAGE_KEY}_tds_rag_df"] = None

        st.info(
            f"TDS deposit due: {cal['tds']['general_deposit']['due_day_of_following_month']}th of following month | "
            f"Late interest: {cal['tds']['interest_late_deposit']['section_201_1a']}%/month"
        )

        _render_inline_review(st.session_state.get(f"{PAGE_KEY}_tds_run_id"), "TDS", f"{PAGE_KEY}_tds")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section

    gst_rag = st.session_state.get(f"{PAGE_KEY}_gst_rag_df")
    tds_rag = st.session_state.get(f"{PAGE_KEY}_tds_rag_df")
    if gst_rag is not None and not gst_rag.empty:
        render_rag_report_section("gst", flagged_df=gst_rag, module_name=MODULE_NAME)
    elif tds_rag is not None and not tds_rag.empty:
        render_rag_report_section("gst", flagged_df=tds_rag, module_name=MODULE_NAME)
    else:
        st.caption("ℹ️ No flagged data for RAG report. Run detection in GST and/or TDS tab after upload.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")
