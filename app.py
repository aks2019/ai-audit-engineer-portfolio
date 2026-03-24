import streamlit as st

st.set_page_config(page_title="AI Audit Engineer Portfolio", layout="wide", page_icon="🔍")

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e2937 100%); color: #e2e8f0; }
    .sidebar .sidebar-content { background: rgba(15, 23, 42, 0.95); border-right: 2px solid #22c55e; }
</style>
""", unsafe_allow_html=True)

st.title("🚨 AI AUDIT ENGINEER")
st.caption("**Ashok Kumar Sharma | SAP FICO AI Auditor | 100% Continuous Monitoring + AI Audit ChatBot")

tab1, tab2 = st.tabs(["🔴 1. Payment Anomaly Detector", "📋 2. AI Audit Bot"])

with tab1:
    import pages.anomaly_detector
with tab2:
    import pages._2_Policy_RAG_Bot