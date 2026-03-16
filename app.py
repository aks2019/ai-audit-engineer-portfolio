import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🔴")

st.title("🔴 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma | SAP FICO Auditor | Week 5 Production Version**")

st.subheader("Upload vendor payments CSV/Excel (SAP / Caseware IDEA export)")
uploaded_file = st.file_uploader(
    "Drag and drop file here",
    type=["csv", "xlsx"],
    help="Limit 200MB per file • CSV or XLSX from SAP/Caseware IDEA"
)

if uploaded_file is not None:
    with st.spinner("Processing your vendor payments..."):
        # Load data
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.success(f"✅ Loaded {len(df):,} vendor payment records")

        # Select numeric columns for anomaly detection (you can change these)
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
        if 'Amount' in df.columns:
            numeric_cols = ['Amount'] + [col for col in numeric_cols if col != 'Amount']
        
        if len(numeric_cols) == 0:
            st.error("No numeric columns found. Please include Amount or other numeric fields.")
            st.stop()

        X = df[numeric_cols].fillna(0)
        
        # Scale & train Isolation Forest (your ML cert model)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = IsolationForest(contamination=0.05, random_state=42)  # 5% anomalies
        model.fit(X_scaled)
        
        # Predict
        df['Anomaly_Score'] = model.decision_function(X_scaled)
        df['Risk_Score'] = -df['Anomaly_Score']  # higher = higher risk
        df['Anomaly'] = model.predict(X_scaled)   # -1 = anomaly

        # Show results
        st.subheader("🔍 Risk Scoring Results")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Transactions", len(df))
            st.metric("High-Risk Flagged", df['Anomaly'].eq(-1).sum())
        with col2:
            st.metric("Max Risk Score", round(df['Risk_Score'].max(), 2))

        st.dataframe(
            df.sort_values('Risk_Score', ascending=False).head(20)[['Vendor_ID' if 'Vendor_ID' in df.columns else df.columns[0], 
                                                                   'Amount' if 'Amount' in df.columns else numeric_cols[0], 
                                                                   'Risk_Score', 'Anomaly']],
            use_container_width=True
        )

        # Simple SHAP-style explanation (top features)
        st.subheader("📊 Top Risk Drivers (Explainability)")
        fig = px.bar(
            x=numeric_cols,
            y=[df[col].corr(df['Risk_Score']) for col in numeric_cols],
            labels={'x': 'Feature', 'y': 'Correlation with Risk'},
            title="Features driving anomalies"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.success("✅ Analysis complete! High-risk payments are flagged in red below. Download the full report using the button above.")
        
        # Download button
        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download Full Risk Report", csv, "vendor_risk_report.csv", "text/csv")

else:
    st.info("👆 Upload your vendor_payments_processed.csv (or any SAP/Caseware export) to start the AI audit")