import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🚨")
st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma** | SAP FICO Auditor | Week 5 Production Version")

BACKEND_URL = "http://127.0.0.1:8000"   # Change to Render URL later

uploaded_file = st.file_uploader(
    "Upload vendor payments CSV/Excel (SAP / Caseware IDEA export)",
    type=["csv", "xlsx"]
)

if uploaded_file:
    files = {"file": uploaded_file.getvalue()}
    response = requests.post(f"{BACKEND_URL}/predict", files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)})

    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        st.success(f"✅ Backend processed {len(df):,} transactions!")

        # Filters, metrics, charts, table (same beautiful UI as before)
        st.sidebar.header("🔍 Risk Filters")
        min_amount = st.sidebar.slider("Minimum Amount (₹)", 0, int(df["amount"].max()), 100000)
        risk_threshold = st.sidebar.slider("Minimum Anomaly Probability", 0.0, 1.0, 0.8)

        filtered = df[(df["amount"] >= min_amount) & (df["anomaly_probability"] >= risk_threshold)]

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Transactions", f"{len(df):,}")
        col2.metric("High-Risk Flagged", f"{(df['anomaly_score'] == 1).sum():,}")
        col3.metric("Risk %", f"{(df['anomaly_score'] == 1).mean()*100:.1f}%")

        colA, colB = st.columns(2)
        with colA:
            st.subheader("Top 20 Highest Payments")
            fig_bar = px.bar(filtered.nlargest(20, "amount"), x="vendor_name", y="amount", color="anomaly_probability")
            st.plotly_chart(fig_bar, use_container_width=True)
        with colB:
            st.subheader("Amount vs Anomaly Probability")
            fig_scatter = px.scatter(filtered, x="amount", y="anomaly_probability", color="anomaly_score", hover_data=["vendor_name"])
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("🚨 Flagged Transactions")
        st.dataframe(filtered, use_container_width=True)

        csv = filtered.to_csv(index=False).encode()
        st.download_button("📥 Download Results", csv, "flagged_transactions.csv", "text/csv")
    else:
        st.error("Backend not responding. Run backend first.")