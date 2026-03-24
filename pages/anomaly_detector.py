import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from db_utils import save_audit_run

st.title("🔴 AI Vendor Payment Anomaly Detector")
st.caption("100% Population Testing • SAP FICO-MM Ready • Built by Ashok Sharma")

st.sidebar.header("Audit Filters")
uploaded_file = st.sidebar.file_uploader("Upload SAP/Caseware CSV", type=["csv", "xlsx"])

if uploaded_file:
    # Load data
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # Sidebar filters
    min_amt, max_amt = st.sidebar.slider(
        "Amount Range (₹)", 
        float(df['amount'].min()), 
        float(df['amount'].max()), 
        (float(df['amount'].min()), float(df['amount'].max()))
    )
    categories = st.sidebar.multiselect("Category", df['category'].unique(), default=df['category'].unique())
    show_related = st.sidebar.checkbox("Show Only Related Party Transactions", False)
    min_overdue, max_overdue = st.sidebar.slider(
        "Days Overdue", 
        int(df['days_overdue'].min()), 
        int(df['days_overdue'].max()), 
        (int(df['days_overdue'].min()), int(df['days_overdue'].max()))
    )
    plants = st.sidebar.multiselect("Plant Code", df['plant_code'].unique(), default=df['plant_code'].unique())

    # Apply filters
    filtered_df = df[
        (df['amount'] >= min_amt) & (df['amount'] <= max_amt) &
        (df['category'].isin(categories)) &
        (df['days_overdue'] >= min_overdue) & (df['days_overdue'] <= max_overdue) &
        (df['plant_code'].isin(plants))
    ]
    if show_related:
        filtered_df = filtered_df[filtered_df['related_party'] == 1]

    # Anomaly detection
    numeric_cols = filtered_df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    X = filtered_df[numeric_cols].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_scaled)
    filtered_df = filtered_df.copy()
    filtered_df['Risk_Score'] = -model.decision_function(X_scaled)
    filtered_df['Anomaly'] = model.predict(X_scaled)

    # Save to audit log
    save_audit_run(filtered_df, "Manual Upload")

    # Tabs with charts
    tab1, tab2, tab3, tab4 = st.tabs(["Visual Analysis", "Risk Distribution", "Top High-Risk", "Full Report"])
    
    with tab1:
        st.subheader("Amount vs Risk Score (Scatter Plot)")
        fig_scatter = px.scatter(
            filtered_df, 
            x='amount', 
            y='Risk_Score', 
            color='Anomaly', 
            color_discrete_map={-1: 'red', 1: 'lime'},
            hover_data=['vendor_name', 'transaction_id', 'category']
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.subheader("Key Risk Drivers")
        corr = [filtered_df[col].corr(filtered_df['Risk_Score']) for col in numeric_cols]
        fig_bar = px.bar(x=numeric_cols, y=corr, title="Which columns drive anomalies the most?")
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with tab2:
        st.subheader("Risk Score Distribution")
        fig_hist = px.histogram(filtered_df, x='Risk_Score', color='Anomaly', nbins=50)
        st.plotly_chart(fig_hist, use_container_width=True)
    
    with tab3:
        st.subheader("Top 20 High-Risk Payments (AI Flagged)")
        top20 = filtered_df.sort_values('Risk_Score', ascending=False).head(20)
        st.dataframe(top20, use_container_width=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Filtered Records", len(filtered_df))
        col2.metric("High-Risk Flagged", (filtered_df['Anomaly'] == -1).sum())
        col3.metric("Highest Risk Score", round(filtered_df['Risk_Score'].max(), 3))
    
    with tab4:
        csv = filtered_df.to_csv(index=False).encode()
        st.download_button("Download Complete Risk Report", csv, "AI_Audit_Risk_Report.csv", "text/csv")
        st.success("Executive Summary: AI performed 100% population testing with full explainability")
else:
    st.info("Upload vendor payments CSV from sidebar to start the AI audit")