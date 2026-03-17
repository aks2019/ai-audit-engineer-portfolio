import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import os
from dotenv import load_dotenv
from db_utils import save_audit_run

load_dotenv()

st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🚨")
st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Sharma | SAP FICO Auditor | Week 8 Production Version**")
st.caption("Continuous Control Monitoring Agent • Powered by Postgres + pgvector")

uploaded_file = st.file_uploader("Upload SAP/Caseware export", type=["csv", "xlsx"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # AI Scoring
    numeric_cols = df.select_dtypes(include=['float64','int64']).columns.tolist()
    X = df[numeric_cols].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_scaled)
    df['Risk_Score'] = -model.decision_function(X_scaled)
    df['Anomaly'] = model.predict(X_scaled)

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Visual Analysis", "📊 Risk Distribution", "🔍 Top High-Risk", "📥 Report", "📚 Audit History"])

    with tab1:  # (same beautiful visuals as before)
        st.plotly_chart(px.scatter(df, x='amount', y='Risk_Score', color='Anomaly', ...), use_container_width=True)
        # ... (keep your existing charts)

    with tab5:  # NEW HISTORY TAB
        st.subheader("📚 Continuous Audit Log (Postgres + pgvector)")
        if st.button("💾 Save This Run to Continuous Monitoring Log"):
            save_audit_run(df, run_name=f"Run_{datetime.now().strftime('%Y-%m-%d')}")
            st.success("✅ Saved to Postgres! This is now part of your permanent audit trail.")

        # Show last 10 runs (simple query – we can expand later)
        st.info("History stored in Neon Postgres – ready for RAG agents next!")

else:
    st.info("👆 Upload file to run AI analysis")