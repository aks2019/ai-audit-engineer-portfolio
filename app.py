import streamlit as st

st.set_page_config(page_title="AI Audit Engineer", page_icon="🚨", layout="wide")

# Sidebar navigation (matches your existing screenshot)
st.sidebar.title("AI Audit Engineer")
st.sidebar.page_link("app.py", label="🏠 Home")
st.sidebar.page_link("pages/anomaly_detector.py", label="🚨 Anomaly Detector")
st.sidebar.page_link("pages/dynamic_audit_builder.py", label="🛠️ Dynamic Audit Builder")
st.sidebar.page_link("pages/financial_statement_auditor.py", label="📊 Financial Statement Auditor")
st.sidebar.page_link("pages/policy_rag_bot.py", label="📜 Policy RAG Bot")

st.title("🚀 AI Audit Engineer – Unified Local Dashboard")
st.markdown("**100% Population Testing | Localhost only")
st.info("Created by | Ashok Kumar Sharma | [GitHub] | (https://github.com/aks2019/ai-audit-engineer-portfolio)")
st.caption("Use sidebar to switch pages.")
