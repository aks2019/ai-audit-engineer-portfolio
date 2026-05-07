import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.compliance_loader import load_compliance_calendar, get_tds_rate, get_tds_threshold, get_gst_due_day

tab1, tab2 = st.tabs(["GST Compliance", "TDS Compliance"])

with tab1:
    st.title("🧾 GST Compliance Mismatch Engine")
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
                        errors.append({"section": sec, "amount": row["amount"], "expected": expected, "actual": actual})
        if errors:
            err_df = pd.DataFrame(errors)
            st.subheader("🚨 TDS Rate Mismatches")
            st.dataframe(err_df, use_container_width=True)
        else:
            st.success("No TDS rate mismatches detected.")

        st.info(f"TDS deposit due: {cal['tds']['general_deposit']['due_day_of_following_month']}th of following month | Late interest: {cal['tds']['interest_late_deposit']['section_201_1a']}%/month")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = type1 if 'type1' in locals() and type1 is not None and not type1.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "gst",
            flagged_df=flagged_rag_df,
            module_name="Gst Tds Compliance"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("gst", "Gst Tds Compliance")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
