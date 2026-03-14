import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🚨")
st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma** | SAP FICO Auditor | Week 4 Live Version")

uploaded_file = st.file_uploader(
    "Upload vendor payments CSV/Excel (SAP / Caseware IDEA export)",
    type=["csv", "xlsx"]
)

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success(f"✅ Loaded {len(df):,} transactions successfully!")

    # Safe check for model columns
    has_anomaly_cols = "anomaly_probability" in df.columns and "anomaly_score" in df.columns

    # ====================== SIDEBAR FILTERS ======================
    st.sidebar.header("🔍 Risk Filters")
    min_amount = st.sidebar.slider("Minimum Amount (₹)", 0, int(df["amount"].max()), 100000)

    if has_anomaly_cols:
        risk_threshold = st.sidebar.slider("Minimum Anomaly Probability", 0.0, 1.0, 0.8)
        filtered = df[(df["amount"] >= min_amount) & (df["anomaly_probability"] >= risk_threshold)].copy()
    else:
        st.sidebar.info("📌 Raw file uploaded.\nRun training first for risk filters.")
        filtered = df[df["amount"] >= min_amount].copy()

    # ====================== METRIC CARDS ======================
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Transactions", f"{len(df):,}")
    col2.metric("High-Risk Flagged", f"{(df['anomaly_score'] == 1).sum():,}" if has_anomaly_cols else "N/A")
    col3.metric("Risk %", f"{(df['anomaly_score'] == 1).mean()*100:.1f}%" if has_anomaly_cols else "N/A")

    # ====================== CHARTS ======================
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Top 20 Highest Payments")
        top20 = filtered.nlargest(20, "amount")
        fig_bar = px.bar(top20, x="vendor_name", y="amount", color="amount",
                         title="Amount vs Risk", labels={"amount": "Payment Amount (₹)"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with colB:
        st.subheader("Amount Distribution")
        fig_scatter = px.scatter(filtered, x="amount", y="amount", 
                                 color="vendor_name" if "category" in filtered.columns else None,
                                 title="Payment Scatter", labels={"amount": "Payment Amount (₹)"})
        st.plotly_chart(fig_scatter, use_container_width=True)

    # ====================== TABLE + DOWNLOAD ======================
    st.subheader("📋 Transactions Table")
    st.dataframe(filtered, use_container_width=True)

    csv = filtered.to_csv(index=False).encode()
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name="filtered_transactions.csv",
        mime="text/csv"
    )

else:
    st.info("👆 Upload a CSV/Excel file to start")

st.caption("Week 4 Live Version | https://aiauditengineer.streamlit.app | Ready for recruiters!")