import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import generate_rag_audit_report

# === SESSION STATE INITIALIZATION ===
if "df" not in st.session_state:
    st.session_state.df = None
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None

st.title("🛠️ Dynamic Audit Builder")
st.markdown("**No-Code SAP Auditor: Map any column to any audit rule instantly.**")

# 1. DATA UPLOAD SECTION
with st.expander("📤 Step 1: Upload SAP Data", expanded=True):
    uploaded_file = st.file_uploader("Upload SAP Extract (CSV/Excel)", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.success(f"✅ Loaded {len(df):,} rows and {len(df.columns)} columns.")
        except Exception as e:
            st.error(f"Error loading file: {e}")

if st.session_state.df is not None:
    df = st.session_state.df
    
    # 2. AUDIT TYPE SELECTION
    st.divider()
    audit_type = st.selectbox("Select Audit Template", [
        "Back-dated / Post-dated Entries",
        "Payment Anomaly (Amount + Days)",
        "GRN vs Invoice Date Mismatch",
        "Duplicate Transactions",
        "ML Unsupervised Outlier Detection"
    ])

    # 3. DYNAMIC COLUMN MAPPING (The "Drag & Drop" Logic)
    st.subheader("🗺️ Step 2: Map Columns to Audit Roles")
    st.info("Select the columns from your dataset that correspond to the required audit roles.")
    
    col1, col2 = st.columns(2)
    mapping = {}

    if audit_type == "Back-dated / Post-dated Entries":
        with col1:
            mapping["date_primary"] = st.selectbox("Primary Date (e.g., Posting Date)", df.columns)
        with col2:
            mapping["date_secondary"] = st.selectbox("Secondary Date (e.g., GRN/Dock Date)", df.columns)

    elif audit_type == "Payment Anomaly (Amount + Days)":
        with col1:
            mapping["amount"] = st.selectbox("Transaction Amount", df.columns)
        with col2:
            mapping["vendor"] = st.selectbox("Vendor/Entity Name", df.columns)
        with col1:
            mapping["days"] = st.selectbox("Outstanding/Ageing Days", df.columns)

    elif audit_type == "GRN vs Invoice Date Mismatch":
        with col1:
            mapping["grn_date"] = st.selectbox("GRN Date Column", df.columns)
        with col2:
            mapping["inv_date"] = st.selectbox("Invoice/Posting Date Column", df.columns)

    elif audit_type == "Duplicate Transactions":
        with col1:
            mapping["key_col"] = st.selectbox("Unique Identifier (e.g., Invoice No)", df.columns)
        with col2:
            mapping["amount_check"] = st.selectbox("Amount Column (for verification)", df.columns)

    elif audit_type == "ML Unsupervised Outlier Detection":
        st.write("Select multiple numeric columns to feed into the Isolation Forest model.")
        mapping["features"] = st.multiselect("Features for ML", options=df.select_dtypes(include=[np.number]).columns)

    # 4. EXECUTION ENGINE
    if st.button("🚀 Run Dynamic Audit", type="primary"):
        st.divider()
        with st.spinner("Executing audit logic..."):
            try:
                results_df = df.copy()
                anomalies = pd.DataFrame()

                # --- LOGIC ENGINE ---
                if audit_type == "Back-dated / Post-dated Entries":
                    d1 = pd.to_datetime(results_df[mapping["date_primary"]])
                    d2 = pd.to_datetime(results_df[mapping["date_secondary"]])
                    # Logic: Primary date is AFTER secondary date (backdating)
                    mask = d1 > d2
                    anomalies = results_df[mask].copy()
                    if not anomalies.empty:
                        anomalies["diff_days"] = (d1[mask] - d2[mask]).dt.days

                elif audit_type == "Payment Anomaly (Amount + Days)":
                    # Statistical Z-Score on Amount
                    amt = results_df[mapping["amount"]]
                    z_scores = (amt - amt.mean()) / amt.std()
                    mask = (z_scores.abs() > 3) | (results_df[mapping["days"]] > 90)
                    anomalies = results_df[mask].copy()

                elif audit_type == "GRN vs Invoice Date Mismatch":
                    d1 = pd.to_datetime(results_df[mapping["grn_date"]])
                    d2 = pd.to_datetime(results_df[mapping["inv_date"]])
                    mask = d1 > d2 # GRN after invoice is a mismatch
                    anomalies = results_df[mask].copy()

                elif audit_type == "Duplicate Transactions":
                    # Find duplicates based on key + amount
                    duplicates = results_df.duplicated(subset=[mapping["key_col"], mapping["amount_check"]], keep=False)
                    anomalies = results_df[duplicates].copy()

                elif audit_type == "ML Unsupervised Outlier Detection":
                    if len(mapping["features"]) >= 2:
                        X = results_df[mapping["features"]].fillna(0)
                        model = IsolationForest(contamination=0.05, random_state=42)
                        preds = model.fit_predict(X)
                        anomalies = results_df[preds == -1].copy()
                    else:
                        st.error("Please select at least 2 numeric features for ML.")

                # --- OUTPUT GENERATION ---
                if not anomalies.empty:
                    st.session_state.audit_results = {"type": audit_type, "df": anomalies}
                    st.success(f"🔍 Audit Complete! Found {len(anomalies)} potential issues.")
                else:
                    st.session_state.audit_results = {"type": audit_type, "df": pd.DataFrame()}
                    st.success("✅ No anomalies detected based on current mapping.")

            except Exception as e:
                st.error(f"Audit Execution Error: {e}")

            # 5. RESULTS & VISUALIZATION
    if st.session_state.audit_results is not None:
        res = st.session_state.audit_results
        if res["df"].empty:
            st.info("No anomalies to display.")
        else:
            st.subheader(f"📊 Results: {res['type']}")
            
            # Metrics
            c1, c2 = st.columns(2)
            c1.metric("Anomalies Found", len(res["df"]))
            c2.metric("Risk Level", "🔴 High" if len(res["df"]) > 5 else "🟡 Medium")

            # Data Table with RAG Integration
            st.write("### 🔍 Flagged Transactions")
            st.info("Select a row to perform an AI Policy Audit on that specific transaction.")
            
            # Use dataframe with selection capability (Streamlit's native feature)
            edited_df = st.dataframe(res["df"], use_container_width=True, on_select="rerun", selection_mode="multi-row")

            # RAG Integration for selected rows
            if len(edited_df.selection.rows) > 0:
                selected_indices = edited_df.selection.rows
                num_selected = len(selected_indices)
                selected_rows_df = res["df"].iloc[selected_indices]
                selected_rows_list = [row.to_dict() for _, row in selected_rows_df.iterrows()]

                st.divider()
                if num_selected == 1:
                    st.subheader("🤖 AI Policy Audit (Selected Transaction)")
                else:
                    st.subheader(f"🤖 AI Policy Audit ({num_selected} Selected Transactions)")

                # Determine vendor name for the prompt
                vendor_col = None
                for col in res["df"].columns:
                    if "vendor" in col.lower():
                        vendor_col = col
                        break
                
                display_vendor = "Unknown"
                if vendor_col and num_selected > 0:
                    unique_vendors = selected_rows_df[vendor_col].unique()
                    if len(unique_vendors) == 1:
                        display_vendor = str(unique_vendors[0])
                    else:
                        display_vendor = "Multiple Vendors"

                col_a, col_b = st.columns([1, 3])
                with col_a:
                    st.write("**Transaction Details:**")
                    if num_selected == 1:
                        for idx, val in selected_rows_df.iloc[0].items():
                            st.write(f"**{idx}:** {val}")
                    else:
                        st.write(f"{num_selected} rows selected.")

                with col_b:
                    button_label = "🔍 Run AI Policy Check on Selected Row" if num_selected == 1 else "🔍 Run AI Policy Check on Selected Transactions"
                    if st.button(button_label, type="primary"):
                        with st.spinner("Consulting policy documents..."):
                            result = generate_rag_audit_report(
                                flagged_transactions=selected_rows_list, 
                                vendor_name=display_vendor
                            )
                            st.markdown("#### Audit Opinion")
                            st.markdown(result["audit_summary"])
                            with st.expander("📚 Sources & References"):
                                for cite in result["citations"]:
                                    st.write(f"- {cite}")

            # Charts
            st.divider()
            st.subheader("📈 Visual Insights")
            flagged_df = res["df"]
            num_cols = flagged_df.select_dtypes(include=[np.number]).columns.tolist()

            if num_cols:
                chart_col = num_cols[0]
                top_n = flagged_df.copy().reset_index(drop=True).head(30)

                # Try to find a label column for the x-axis
                label_col = None
                for c in flagged_df.columns:
                    if any(kw in c.lower() for kw in ["vendor", "name", "party", "invoice", "doc"]):
                        label_col = c
                        break
                if label_col is None:
                    top_n["_row"] = top_n.index.astype(str)
                    label_col = "_row"

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    fig_bar = px.bar(
                        top_n, x=label_col, y=chart_col,
                        title=f"Top Flagged: {chart_col}",
                        color=chart_col, color_continuous_scale="Reds"
                    )
                    fig_bar.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with col_chart2:
                    if len(num_cols) >= 2:
                        fig_scatter = px.scatter(
                            top_n, x=num_cols[0], y=num_cols[1],
                            hover_data=[label_col],
                            title=f"{num_cols[0]} vs {num_cols[1]}",
                            color=num_cols[0], color_continuous_scale="Oranges"
                        )
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        fig_hist = px.histogram(top_n, x=chart_col, title=f"Distribution: {chart_col}", nbins=20)
                        st.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.info("No numeric columns available for charts.")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = anomalies if 'anomalies' in locals() and anomalies is not None and not anomalies.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "dab",
            flagged_df=flagged_rag_df,
            module_name="Dynamic Audit Builder"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("dab", "Dynamic Audit Builder")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
