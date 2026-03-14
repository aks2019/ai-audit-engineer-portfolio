import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🚨")
st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma** | SAP FICO Auditor | Week 3 Prototype")

# ====================== UPLOADER ======================
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

    # ====================== FILTERS (Sidebar) ======================
    st.sidebar.header("🔍 Risk Filters")
    min_amount = st.sidebar.slider("Minimum Amount (₹)", 0, int(df["amount"].max()), 100000)
    risk_threshold = st.sidebar.slider("Minimum Anomaly Probability", 0.0, 1.0, 0.8)

    filtered = df[df["amount"] >= min_amount].copy()
    filtered = filtered[filtered["anomaly_probability"] >= risk_threshold]

    # ====================== METRIC CARDS ======================
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Transactions", f"{len(df):,}")
    col2.metric("High-Risk Flagged", f"{(df['anomaly_score'] == 1).sum():,}")
    col3.metric("Risk %", f"{(df['anomaly_score'] == 1).mean()*100:.1f}%")

    # ====================== CHARTS ======================
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Top 20 Highest Risk Payments")
        top20 = filtered.nlargest(20, "amount")
        fig_bar = px.bar(top20, x="vendor_name", y="amount", color="anomaly_probability",
                         title="Amount vs Risk", labels={"amount": "Payment Amount (₹)"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with colB:
        st.subheader("Amount vs Anomaly Probability")
        hover_list = ["vendor_name", "transaction_id"]
        if "category" in filtered.columns:
            hover_list.append("category")
        fig_scatter = px.scatter(filtered, x="amount", y="anomaly_probability",
                                 color="anomaly_score", hover_data=hover_list,
                                 title="Risk Scatter Plot", labels={"amount": "Payment Amount (₹)"})
        st.plotly_chart(fig_scatter, use_container_width=True)

    # ====================== TABLE + DOWNLOAD ======================
    st.subheader("🚨 Flagged High-Risk Transactions")
    st.dataframe(filtered, use_container_width=True)

    csv = filtered.to_csv(index=False).encode()
    st.download_button(
        label="📥 Download Flagged Transactions as CSV",
        data=csv,
        file_name="flagged_high_risk.csv",
        mime="text/csv"
    )

else:
    st.info("👆 Upload a CSV/Excel file to see interactive dashboard")

st.caption("Week 3 Complete: Uploader + Filters + Charts | Ready for real audit files | Next week: Deployment")