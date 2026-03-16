import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import plotly.express as px

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🔴")

st.title("🔴 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma | SAP FICO Auditor | Week 5 Production Version**")

st.subheader("Upload vendor payments CSV/Excel (SAP / Caseware IDEA export)")
uploaded_file = st.file_uploader(
    "Drag and drop file here",
    type=["csv", "xlsx"],
    help="Limit 200MB • CSV or XLSX from SAP/Caseware IDEA"
)

if uploaded_file is not None:
    with st.spinner("🔄 Processing your SAP/Caseware export..."):
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        st.success(f"✅ Loaded {len(df):,} vendor payment records from {uploaded_file.name}")

        # Use numeric columns (works with your real SAP data)
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
        if len(numeric_cols) == 0:
            st.error("No numeric columns found. Please include 'Amount' or similar.")
            st.stop()

        X = df[numeric_cols].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Your ML model (Isolation Forest – 5% flagged as high risk)
        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(X_scaled)
        
        df['Risk_Score'] = -model.decision_function(X_scaled)
        df['Anomaly'] = model.predict(X_scaled)  # -1 = high risk

        # Results
        st.subheader("🔍 Top 20 High-Risk Payments (AI Flagged)")
        high_risk = df.sort_values('Risk_Score', ascending=False).head(20)
        st.dataframe(high_risk, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Records", len(df))
            st.metric("High-Risk Flagged", (df['Anomaly'] == -1).sum())
        with col2:
            st.metric("Highest Risk Score", round(df['Risk_Score'].max(), 2))

        # Simple explainability
        st.subheader("📊 Key Risk Drivers")
        corr = [df[col].corr(df['Risk_Score']) for col in numeric_cols]
        fig = px.bar(x=numeric_cols, y=corr, labels={'x': 'Column', 'y': 'Impact on Risk'})
        st.plotly_chart(fig, use_container_width=True)

        # Download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Full AI Risk Report", csv, "vendor_risk_report.csv", "text/csv")

else:
    st.info("👆 Upload vendor_payments_processed.csv (or any SAP/Caseware export) to run the AI audit")