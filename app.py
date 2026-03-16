import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ====================== BEAUTIFUL BACKGROUND & STYLING ======================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e2937 100%);
        color: #e2e8f0;
    }
    .stTitle {
        font-size: 2.8rem !important;
        text-shadow: 0 0 20px #22c55e;
    }
    .sidebar .sidebar-content {
        background: rgba(15, 23, 42, 0.95);
        border-right: 2px solid #22c55e;
    }
    .stMetric {
        background: rgba(34, 197, 94, 0.1);
        border-radius: 12px;
        padding: 15px;
    }
    .stDataFrame {
        border: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# ====================== HEADER WITH BIG SIREN ======================
st.set_page_config(page_title="AI Vendor Payment Anomaly Detector", layout="wide", page_icon="🚨")

st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**Built by Ashok Kumar Sharma | SAP FICO Auditor | Week 8 Production Version**")
st.caption("100% Population Testing • Real-time Anomaly Detection • Full Explainability")

# ====================== SIDEBAR – RICH FILTERS ======================
st.sidebar.header("🔧 Audit Filters")
uploaded_file = st.sidebar.file_uploader("Upload SAP/Caseware CSV", type=["csv", "xlsx"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

    # Amount Range Filter
    min_amt, max_amt = st.sidebar.slider(
        "Amount Range (₹)",
        float(df['amount'].min()),
        float(df['amount'].max()),
        (float(df['amount'].min()), float(df['amount'].max()))
    )

    # Category Filter
    categories = st.sidebar.multiselect("Category", options=df['category'].unique(), default=df['category'].unique())

    # Related Party Filter
    show_related = st.sidebar.checkbox("Show Only Related Party Transactions", value=False)

    # Days Overdue Filter
    min_overdue, max_overdue = st.sidebar.slider(
        "Days Overdue",
        int(df['days_overdue'].min()),
        int(df['days_overdue'].max()),
        (int(df['days_overdue'].min()), int(df['days_overdue'].max()))
    )

    # Plant Code Filter
    plants = st.sidebar.multiselect("Plant Code", options=df['plant_code'].unique(), default=df['plant_code'].unique())

    # Apply all filters
    filtered_df = df[
        (df['amount'] >= min_amt) & (df['amount'] <= max_amt) &
        (df['category'].isin(categories)) &
        (df['days_overdue'] >= min_overdue) & (df['days_overdue'] <= max_overdue) &
        (df['plant_code'].isin(plants))
    ]
    if show_related:
        filtered_df = filtered_df[filtered_df['related_party'] == 1]

    # ====================== AI ANOMALY SCORING ======================
    numeric_cols = filtered_df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    X = filtered_df[numeric_cols].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_scaled)
    filtered_df = filtered_df.copy()
    filtered_df['Risk_Score'] = -model.decision_function(X_scaled)
    filtered_df['Anomaly'] = model.predict(X_scaled)

    # ====================== TABS IN YOUR REQUESTED ORDER ======================
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Visual Analysis", "📊 Risk Distribution", "🔍 Top High-Risk Payments", "📥 Full Report"])

    with tab1:
        st.subheader("📈 Amount vs Risk Score (Scatter Plot)")
        fig_scatter = px.scatter(filtered_df, x='amount', y='Risk_Score',
                                 color='Anomaly', color_discrete_map={-1: 'red', 1: 'lime'},
                                 hover_data=['vendor_name', 'transaction_id', 'category'],
                                 title="High-Risk Transactions Clearly Visible")
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("📊 Key Risk Drivers")
        corr = [filtered_df[col].corr(filtered_df['Risk_Score']) for col in numeric_cols]
        fig_bar = px.bar(x=numeric_cols, y=corr, title="Which columns drive anomalies the most?")
        st.plotly_chart(fig_bar, use_container_width=True)

    with tab2:
        st.subheader("📊 Risk Score Distribution")
        fig_hist = px.histogram(filtered_df, x='Risk_Score', color='Anomaly',
                                title="How risk scores are distributed across your data",
                                nbins=50)
        st.plotly_chart(fig_hist, use_container_width=True)

    with tab3:
        st.subheader("🔍 Top 20 High-Risk Payments (AI Flagged)")
        top20 = filtered_df.sort_values('Risk_Score', ascending=False).head(20)
        st.dataframe(top20, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Total Filtered Records", len(filtered_df))
        with col2: st.metric("High-Risk Flagged", (filtered_df['Anomaly'] == -1).sum())
        with col3: st.metric("Highest Risk Score", round(filtered_df['Risk_Score'].max(), 3))

    with tab4:
        st.subheader("📥 Download Full AI Audit Report")
        csv = filtered_df.to_csv(index=False).encode()
        st.download_button("📥 Download Complete Risk Report", csv, "AI_Audit_Risk_Report.csv", "text/csv")
        st.success("✅ Executive Summary: AI performed 100% population testing and flagged high-risk payments with full explainability – ready for audit committee / CFO.")

else:
    st.info("👆 Upload your vendor payments file from the sidebar to start the AI audit")