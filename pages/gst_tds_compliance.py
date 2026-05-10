import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.compliance_loader import load_compliance_calendar, get_tds_rate, get_tds_threshold, get_gst_due_day
from utils.audit_db import init_audit_db
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "gst"

# Initialize session state for run_id if not exists
if f"{PAGE_KEY}_gst_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_gst_run_id"] = None
if f"{PAGE_KEY}_tds_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_tds_run_id"] = None

tab1, tab2 = st.tabs(["GST Compliance", "TDS Compliance"])

with tab1:
    st.title("🧾 GST Compliance Mismatch Engine")
    render_engagement_selector(PAGE_KEY)
    st.caption("GSTR-2A vs Books | ITC Eligibility | Filing Timeliness")

    gstr_file = st.file_uploader("Upload GSTR-2A (Excel/CSV)", type=["csv","xlsx"], key="gstr")
    books_file = st.file_uploader("Upload Books Data (Excel/CSV)", type=["csv","xlsx"], key="books")

    if gstr_file and books_file:
        gstr = pd.read_excel(gstr_file) if gstr_file.name.endswith(".xlsx") else pd.read_csv(gstr_file)
        books = pd.read_excel(books_file) if books_file.name.endswith(".xlsx") else pd.read_csv(books_file)

        with st.expander("🔧 Column Mapping"):
            g_inv = st.selectbox("GSTR Invoice No", gstr.columns, key="g_inv")
            g_amt = st.selectbox("GSTR Taxable Amount", gstr.columns, key="g_amt")
            b_inv = st.selectbox("Books Invoice No", books.columns, key="b_inv")
            b_amt = st.selectbox("Books Taxable Amount", books.columns, key="b_amt")

        gstr = gstr.rename(columns={g_inv:"invoice_no", g_amt:"amount"})
        books = books.rename(columns={b_inv:"invoice_no", b_amt:"amount"})

        merged = pd.merge(books, gstr, on="invoice_no", how="outer", suffixes=("_books","_gstr"), indicator=True)

        type1 = merged[merged["_merge"] == "left_only"]   # books not in 2A
        type2 = merged[merged["_merge"] == "right_only"]  # 2A not in books
        both = merged[merged["_merge"] == "both"]
        type3 = both[(both["amount_books"] - both["amount_gstr"]).abs() > 100]

        st.metric("Books not in 2A (ITC at risk)", len(type1))
        st.metric("2A not in books", len(type2))
        st.metric("Amount mismatch >₹100", len(type3))

        for name, df_m in [("Type 1: Books not in 2A", type1), ("Type 3: Amount mismatch", type3)]:
            if not df_m.empty:
                st.subheader(name)
                st.dataframe(df_m.head(50), use_container_width=True)

        # Filing timeliness
        cal = load_compliance_calendar()
        due_day = get_gst_due_day("GSTR-3B_category_1")
        st.info(f"GSTR-3B Category 1 due day: {due_day} of following month (from compliance_calendar.yaml)")

        # ── Stage Findings for Draft Review (NOT auto-logged) ──
        init_audit_db()
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        # Combine Type 1 (Books not in 2A) and Type 3 (Amount mismatch) for staging
        staging_dfs = []
        
        if not type1.empty:
            type1_staged = type1.head(100).copy()
            type1_staged["area"] = "GST Compliance"
            type1_staged["checklist_ref"] = "GST Section 16 / GSTR-2A Rules"
            type1_staged["finding"] = type1_staged.apply(
                lambda r: f"Books not in GSTR-2A: Invoice #{r.get('invoice_no', 'N/A')} — ITC at risk ₹{r.get('amount_books', 0):,.0f}", 
                axis=1
            )
            type1_staged["amount_at_risk"] = type1_staged["amount_books"].fillna(0)
            type1_staged["risk_band"] = "HIGH"
            type1_staged["vendor_name"] = type1_staged.get("vendor_name", "")
            type1_staged["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            staging_dfs.append(type1_staged)
        
        if not type3.empty:
            type3_staged = type3.head(100).copy()
            type3_staged["area"] = "GST Compliance"
            type3_staged["checklist_ref"] = "GST Section 16 / GSTR-2A Rules"
            type3_staged["finding"] = type3_staged.apply(
                lambda r: f"GST amount mismatch: Invoice #{r.get('invoice_no', 'N/A')} — Books ₹{r.get('amount_books', 0):,.0f} vs GSTR ₹{r.get('amount_gstr', 0):,.0f}", 
                axis=1
            )
            type3_staged["amount_at_risk"] = type3_staged[["amount_books", "amount_gstr"]].fillna(0).abs().max(axis=1)
            type3_staged["risk_band"] = "HIGH"
            type3_staged["vendor_name"] = type3_staged.get("vendor_name", "")
            type3_staged["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            staging_dfs.append(type3_staged)
        
        if staging_dfs:
            combined_staging_df = pd.concat(staging_dfs, ignore_index=True)
            from utils.audit_db import stage_findings as _stage_findings
            _staged = _stage_findings(
                combined_staging_df,
                module_name="Gst Tds Compliance",
                run_id=run_id,
                period=datetime.utcnow().strftime("%Y-%m"),
                source_file_name=getattr(gstr_file, "name", "manual"),
                engagement_id=get_active_engagement_id(PAGE_KEY),
            )
            st.info(f"📋 **{_staged} GST exception(s) staged for your review.** Nothing has been added to the official audit trail yet.")
            st.session_state[f"{PAGE_KEY}_gst_run_id"] = run_id

with tab2:
    st.title("💸 TDS Compliance Engine")
    st.caption("Rate validation | Deposit timeliness | Interest calculation")

    tds_file = st.file_uploader("Upload TDS Ledger (Excel/CSV)", type=["csv","xlsx"], key="tds")
    if tds_file:
        tds = pd.read_excel(tds_file) if tds_file.name.endswith(".xlsx") else pd.read_csv(tds_file)

        with st.expander("🔧 Column Mapping"):
            sec_col = st.selectbox("TDS Section", tds.columns)
            amt_col = st.selectbox("Payment Amount", tds.columns)
            rate_col = st.selectbox("TDS Deducted Rate % (optional)", ["None"]+list(tds.columns))
            payee_col = st.selectbox("Payee Type (Individual/Company)", ["None"]+list(tds.columns))

        tds = tds.rename(columns={sec_col:"section", amt_col:"amount"})
        cal = load_compliance_calendar()

        errors = []
        for _, row in tds.iterrows():
            sec = str(row["section"])
            payee = str(row.get(payee_col, "individual")).lower()
            expected = get_tds_rate(sec, "company" if "company" in payee else "individual")
            threshold = get_tds_threshold(sec)
            try:
                expected = float(expected)
            except (TypeError, ValueError):
                continue  # skip sections with non-numeric rates (e.g. "Slab rate", "DTAA rate")
            if expected and row["amount"] >= threshold:
                if rate_col != "None" and pd.notna(row.get(rate_col)):
                    actual = float(row[rate_col])
                    if abs(actual - expected) > 0.1:
                        errors.append({"section": sec, "amount": row["amount"], "expected": expected, "actual": actual, "vendor_name": row.get(payee_col, "Unknown")})
        if errors:
            err_df = pd.DataFrame(errors)
            st.subheader("🚨 TDS Rate Mismatches")
            st.dataframe(err_df, use_container_width=True)
            
            # ── Stage Findings for Draft Review (NOT auto-logged) ──
            init_audit_db()
            run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            
            staging_df = err_df.head(100).copy()
            staging_df["area"] = "TDS Compliance"
            staging_df["checklist_ref"] = "Income Tax Section 192-206"
            staging_df["finding"] = staging_df.apply(
                lambda r: f"TDS rate mismatch for Section {r.get('section', 'N/A')}: Expected {r.get('expected', 0):.2f}% vs Actual {r.get('actual', 0):.2f}% on payment ₹{r.get('amount', 0):,.0f}", 
                axis=1
            )
            staging_df["amount_at_risk"] = staging_df["amount"]
            staging_df["risk_band"] = "HIGH"
            staging_df["vendor_name"] = staging_df.get("vendor_name", "")
            staging_df["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
            
            if not staging_df.empty:
                from utils.audit_db import stage_findings as _stage_findings
                _staged = _stage_findings(
                    staging_df,
                    module_name="Gst Tds Compliance",
                    run_id=run_id,
                    period=datetime.utcnow().strftime("%Y-%m"),
                    source_file_name=getattr(tds_file, "name", "manual"),
                    engagement_id=get_active_engagement_id(PAGE_KEY),
                )
                st.info(f"📋 **{_staged} TDS exception(s) staged for your review.** Nothing has been added to the official audit trail yet.")
                st.session_state[f"{PAGE_KEY}_tds_run_id"] = run_id
        else:
            st.success("No TDS rate mismatches detected.")

        st.info(f"TDS deposit due: {cal['tds']['general_deposit']['due_day_of_following_month']}th of following month | Late interest: {cal['tds']['interest_late_deposit']['section_201_1a']}%/month")


# --- AI Audit Report (RAG) ---
# Note: RAG report uses GST type1 data as the primary flagged data
try:
    from utils.audit_page_helpers import render_rag_report_section
    if 'type1' in dir() and type1 is not None and not type1.empty:
        render_rag_report_section(
            "gst",
            flagged_df=type1,
            module_name="Gst Tds Compliance"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")


# --- Draft Review ---
# This will load and display all drafts for GST/TDS Compliance module
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("gst", "Gst Tds Compliance")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")