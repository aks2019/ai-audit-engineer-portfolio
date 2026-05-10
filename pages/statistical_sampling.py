import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import save_sampling_run
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

PAGE_KEY = "sample"

st.title("📐 Statistical Sampling Engine")
render_engagement_selector(PAGE_KEY)
st.caption("Monetary Unit Sampling (MUS) | Random Sampling | Cell Sampling | Confidence-based")

uploaded = st.file_uploader("Upload Population Data (CSV/Excel)", type=["csv","xlsx"])
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Population: {len(df):,} rows")

    with st.expander("🔧 Column Mapping"):
        id_col = st.selectbox("Unique ID", df.columns)
        amt_col = st.selectbox("Monetary Amount", df.columns)
        stratify_col = st.selectbox("Stratify By (optional)", ["None"]+list(df.columns))

    df = df.rename(columns={id_col:"_id", amt_col:"_amount"})
    total_value = df["_amount"].sum()

    st.metric("Total Population Value", f"₹{total_value:,.0f}")

    method = st.selectbox("Sampling Method", ["Monetary Unit Sampling (MUS)", "Simple Random", "Cell Sampling", "Stratified Random"])
    confidence = st.slider("Confidence Level", 0.80, 0.99, 0.95)
    materiality = st.number_input("Materiality Threshold (₹)", min_value=1000, value=500000, step=10000)
    expected_error = st.slider("Expected Error Rate", 0.0, 0.10, 0.02)

    # Sample size calculation (simplified)
    z = {0.80:1.28, 0.90:1.645, 0.95:1.96, 0.99:2.576}[confidence]
    sample_size = int(min(len(df), max(30, (z**2 * total_value * expected_error * (1-expected_error)) / (materiality**2))))
    st.metric("Calculated Sample Size", sample_size)

    if st.button("🎯 Draw Sample"):
        np.random.seed(42)
        if method == "Monetary Unit Sampling (MUS)":
            # Select items proportional to amount
            probs = df["_amount"] / total_value
            selected = np.random.choice(df.index, size=sample_size, p=probs, replace=True)
            sample = df.loc[selected].drop_duplicates("_id").copy()
        elif method == "Simple Random":
            sample = df.sample(n=min(sample_size, len(df)), random_state=42).copy()
        elif method == "Cell Sampling":
            df["cell"] = pd.qcut(df["_amount"], q=5, labels=False, duplicates="drop")
            sample = df.groupby("cell").apply(lambda x: x.sample(n=max(1, sample_size//5), random_state=42)).reset_index(drop=True)
        elif method == "Stratified Random" and stratify_col != "None":
            sample = df.groupby(stratify_col).apply(lambda x: x.sample(n=max(1, min(len(x), sample_size//df[stratify_col].nunique())), random_state=42)).reset_index(drop=True)
        else:
            sample = df.sample(n=min(sample_size, len(df)), random_state=42).copy()

        st.success(f"Sample drawn: {len(sample)} items | Sample value: ₹{sample['_amount'].sum():,.0f}")
        st.dataframe(sample, use_container_width=True)

        csv = sample.to_csv(index=False).encode()
        st.download_button("📥 Download Sample CSV", csv, "audit_sample.csv", "text/csv")

        save_sampling_run(
            run_name=f"{method}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}",
            population_size=len(df),
            sample_size=len(sample),
            method=method,
            confidence_level=confidence,
            materiality_threshold=materiality
        )
        st.caption("📝 Sampling run saved to audit.db")


# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    # sample variable contains the drawn sample (which represents audited items)
    sample_df = sample if 'sample' in locals() and sample is not None and not sample.empty else None
    if sample_df is not None:
        render_rag_report_section(
            PAGE_KEY,
            flagged_df=sample_df,
            module_name="Statistical Sampling"
        )
    else:
        st.caption("ℹ️ Draw a sample first to enable RAG audit report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")



# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("sample", "Statistical Sampling")
except Exception as _e:
    st.caption(f"Draft review unavailable: {_e}")
