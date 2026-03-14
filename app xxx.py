from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


RESULTS_PATH = Path("data") / "results" / "flagged_transactions.csv"
PROCESSED_PATH = Path("data") / "processed" / "vendor_payments_processed.csv"


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load flagged transactions and enrich them with risk features."""

    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Expected results file not found at {RESULTS_PATH}. "
            "Run the model training script first."
        )
    if not PROCESSED_PATH.exists():
        raise FileNotFoundError(
            f"Expected processed data not found at {PROCESSED_PATH}. "
            "Run the feature engineering script first."
        )

    flagged = pd.read_csv(RESULTS_PATH)
    processed = pd.read_csv(PROCESSED_PATH, parse_dates=["payment_date"])

    # Keep core risk fields from processed data for joining.
    base_cols = [
        "transaction_id",
        "category",
        "related_party",
        "composite_risk_score",
        "anomaly_score",
        "amount_zscore",
        "amount_ratio",
        "high_value_flag",
        "related_party_risk",
        "overdue_risk_score",
        "anomaly_probability",
    ]
    risk_cols = [c for c in base_cols if c in processed.columns]
    risk_info = processed[risk_cols].copy()

    # Join to enrich flagged rows.
    merged = flagged.merge(risk_info, on="transaction_id", how="left")

    # Human-readable related party labels for visualisation.
    merged["related_party_label"] = merged["related_party"].map(
        {0: "Non-related", 1: "Related"}
    )

    return flagged, processed, merged


def main() -> None:
    st.set_page_config(
        page_title="AI Vendor Payment Anomaly Detector",
        layout="wide",
    )

    st.title("AI Vendor Payment Anomaly Detector - Built by Ashok Kumar Sharma")
    st.caption("Run with: `streamlit run app.py`")

    flagged, processed, merged = load_data()

    # ------------------------------------------------------------------
    # Sidebar filters
    # ------------------------------------------------------------------
    st.sidebar.header("Filters")

    min_amount = float(merged["amount"].min())
    max_amount = float(merged["amount"].max())
    amount_range = st.sidebar.slider(
        "Amount range (₹)",
        min_value=min_amount,
        max_value=max_amount,
        value=(min_amount, max_amount),
        format="₹%0.0f",
    )

    categories = sorted(merged["category"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Category",
        options=categories,
        default=categories,
    )

    related_filter = st.sidebar.selectbox(
        "Related party filter",
        options=["All", "Related only", "Non-related"],
        index=0,
    )

    # Apply filters.
    df_view = merged.copy()
    df_view = df_view[
        (df_view["amount"] >= amount_range[0]) & (df_view["amount"] <= amount_range[1])
    ]
    if selected_categories:
        df_view = df_view[df_view["category"].isin(selected_categories)]

    if related_filter == "Related only":
        df_view = df_view[df_view["related_party"] == 1]
    elif related_filter == "Non-related":
        df_view = df_view[df_view["related_party"] == 0]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    total_tx = len(processed)
    total_anomalies = int((processed["anomaly_score"] == 1).sum()) if "anomaly_score" in processed.columns else len(flagged)
    risk_pct = (total_anomalies / total_tx * 100.0) if total_tx > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total transactions", f"{total_tx:,}")
    col2.metric("Anomalies detected", f"{total_anomalies:,}")
    col3.metric("% at risk", f"{risk_pct:0.1f}%")

    # ------------------------------------------------------------------
    # Table of flagged transactions
    # ------------------------------------------------------------------
    st.subheader("Flagged Vendor Payments")

    table_cols = [
        "transaction_id",
        "vendor_name",
        "amount",
        "category",
        "related_party",
        "composite_risk_score",
        "anomaly_score",
        "anomaly_probability",
        "risk_explanation",
    ]
    available_cols = [c for c in table_cols if c in df_view.columns]

    st.dataframe(
        df_view[available_cols]
        .sort_values("composite_risk_score", ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    st.subheader("Risk Visualisations")
    chart_col1, chart_col2 = st.columns(2)

    # Bar chart: Top 20 by composite risk score
    if "composite_risk_score" in merged.columns:
        top20 = (
            merged.sort_values("composite_risk_score", ascending=False)
            .head(20)
            .copy()
        )
        top20["label"] = (
            top20["vendor_name"].astype(str)
            + " ("
            + top20["transaction_id"].astype(str)
            + ")"
        )
        fig_bar = px.bar(
            top20,
            x="composite_risk_score",
            y="label",
            orientation="h",
            labels={
                "composite_risk_score": "Composite Risk Score (0–10)",
                "label": "Vendor / Transaction",
            },
            title="Top 20 Highest Composite Risk Scores",
        )
        fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
        chart_col1.plotly_chart(fig_bar, use_container_width=True)

    # Scatter plot: amount vs anomaly_probability
    if "anomaly_probability" in merged.columns:
        fig_scatter = px.scatter(
            merged,
            x="amount",
            y="anomaly_probability",
            color="related_party_label",
            hover_data=["transaction_id", "vendor_name", "category"],
            labels={
                "amount": "Amount (₹)",
                "anomaly_probability": "Anomaly Probability (0–1)",
                "related_party_label": "Related Party",
            },
            title="Amount vs Anomaly Probability",
        )
        chart_col2.plotly_chart(fig_scatter, use_container_width=True)

    # ------------------------------------------------------------------
    # Download button
    # ------------------------------------------------------------------
    st.subheader("Export")

    # Use CSV content with .xlsx extension for easy Excel consumption without extra dependencies.
    download_df = df_view[available_cols].copy()
    buffer = io.StringIO()
    download_df.to_csv(buffer, index=False)
    st.download_button(
        label="Download Flagged Transactions as Excel",
        data=buffer.getvalue(),
        file_name="flagged_transactions.xlsx",
        mime="text/csv",
    )

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    st.markdown(
        "---\n"
        "Built in Week 1 using Isolation Forest + SHAP | Ready for production"
    )


if __name__ == "__main__":
    main()

