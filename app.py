# import streamlit as st

# st.set_page_config(page_title="AI Audit Engineer Portfolio", layout="wide", page_icon="🔍")

# st.markdown("""
# <style>
#     .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e2937 100%); color: #e2e8f0; }
#     .sidebar .sidebar-content { background: rgba(15, 23, 42, 0.95); border-right: 2px solid #22c55e; }
# </style>
# """, unsafe_allow_html=True)

# st.title("🚨 AI AUDIT ENGINEER")
# st.caption("**Ashok Kumar Sharma | SAP FICO AI Auditor | 100% Continuous Monitoring + AI Audit ChatBot")

# tab1, tab2 = st.tabs(["🔴 Payment Anomaly Detector", "📋 Policy RAG Bot"])

# with tab1:
#     import pages.anomaly_detector
# with tab2:
#     import pages.policy_rag_bot


# #New setting, delete above codes if the below works well

import streamlit as st

st.set_page_config(page_title="AI Audit Engineer", page_icon="🚨", layout="wide")

# Sidebar navigation (matches your existing screenshot)
st.sidebar.title("AI Audit Engineer")
st.sidebar.page_link("app.py", label="🏠 Home", icon="🏠")
st.sidebar.page_link("pages/policy_rag_bot.py", label="📜 Policy RAG Bot", icon="2️⃣")
st.sidebar.page_link("pages/anomaly_detector.py", label="🚨 Anomaly Detector", icon="1️⃣")
st.sidebar.page_link("pages/dynamic_audit_builder.py", label="🛠️ Dynamic Audit Builder", icon="3️⃣")

st.title("🚀 AI Audit Engineer – Unified Local Dashboard")
st.markdown("**Payment Anomaly Detector + Contract RAG Bot** | SAP FICO-MM | 100% Population Testing | Localhost only")

st.info("✅ Anomaly + Contract RAG integration complete. Use sidebar to switch pages.")
st.caption("Phase 3 complete | Ready for BRS Anomaly Agent (Week 13)")

