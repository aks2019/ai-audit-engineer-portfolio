from __future__ import annotations

"""
Audit-focused feature engineering for vendor payments.

This module exposes a single entry point:

    from src.audit_anomaly_detector.features.engineer_features import engineer_features

The function accepts a pandas DataFrame with the raw vendor payment schema and
returns a new DataFrame with additional risk features, including a composite
risk score suitable for downstream anomaly modeling.
"""

from typing import Sequence

import pandas as pd


RISK_FEATURE_COLUMNS: Sequence[str] = [
    "amount_zscore",
    "amount_ratio",
    "high_value_flag",
    "related_party_risk",
    "overdue_risk_score",
    "composite_risk_score",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create audit-focused risk features on a copy of the input DataFrame.

    Expected input columns (at minimum):
    - amount
    - category
    - related_party
    - days_overdue
    - previous_avg_amount

    The function is deliberately explicit and side-effect free to keep it
    easy to review in an audit context.
    """

    df = df.copy()

    # 1. amount_zscore:
    #    How unusual the amount is compared to other payments in the SAME category.
    #    We compute the z-score within each category:
    #      (amount - mean_amount_in_category) / std_amount_in_category
    df["amount_mean_by_category"] = df.groupby("category")["amount"].transform("mean")
    df["amount_std_by_category"] = df.groupby("category")["amount"].transform("std")

    # Avoid division by zero: if std is 0 or NaN, treat z-score as 0 (no variation).
    df["amount_zscore"] = 0.0
    non_zero_std = df["amount_std_by_category"] > 0
    df.loc[non_zero_std, "amount_zscore"] = (
        (df.loc[non_zero_std, "amount"] - df.loc[non_zero_std, "amount_mean_by_category"])
        / df.loc[non_zero_std, "amount_std_by_category"]
    )

    # 2. amount_ratio:
    #    Current amount divided by previous_avg_amount.
    #    Values >> 1 indicate potential spikes versus vendor's historical pattern.
    df["amount_ratio"] = df["amount"] / df["previous_avg_amount"].replace(0, pd.NA)
    df["amount_ratio"] = df["amount_ratio"].fillna(0)

    # 3. high_value_flag:
    #    Flag payments that fall into the highest 5% of amounts overall.
    high_value_threshold = df["amount"].quantile(0.95)
    df["high_value_flag"] = (df["amount"] >= high_value_threshold).astype(int)

    # 4. related_party_risk:
    #    Flag related-party payments above a high-value threshold (₹5 lakh here).
    #    These tend to attract more audit scrutiny.
    df["related_party_risk"] = (
        (df["related_party"] == 1) & (df["amount"] > 500_000)
    ).astype(int)

    # 5. overdue_risk_score:
    #    Convert days_overdue into a coarse risk score.
    #    - 0 when not overdue or negative (early payments).
    #    - Increases by ~1 per month overdue.
    #    - Capped at 3.0 to avoid overly dominating the combined risk.
    df["overdue_risk_score"] = (df["days_overdue"] / 30.0).clip(lower=0.0, upper=3.0)

    # Composite risk score (0–10)
    # Build a simple, interpretable composite risk score from the components.
    #
    # We first normalise some continuous measures into 0–1 scales:
    #   - amount_zscore: focus on high positive deviations, capped at 3 std dev.
    #   - amount_ratio: focus on spikes above 1x previous average, capped at 3x.
    #   - overdue_risk_score: already 0–3, scale to 0–1.
    #
    # Then compute a weighted average and scale to 0–10:
    #   composite_raw = (0.30 * z_norm +
    #                    0.30 * ratio_norm +
    #                    0.20 * high_value_flag +
    #                    0.10 * related_party_risk +
    #                    0.10 * overdue_norm)
    #   composite_risk_score = composite_raw * 10

    # Normalised z-score: emphasis on unusually large positive amounts.
    z_pos = df["amount_zscore"].clip(lower=0.0, upper=3.0)
    z_norm = z_pos / 3.0

    # Normalised amount ratio: focus on spikes above historical average.
    ratio_excess = (df["amount_ratio"] - 1.0).clip(lower=0.0, upper=3.0)
    ratio_norm = ratio_excess / 3.0

    # Normalised overdue risk (0–1).
    overdue_norm = df["overdue_risk_score"] / 3.0

    composite_raw = (
        0.30 * z_norm
        + 0.30 * ratio_norm
        + 0.20 * df["high_value_flag"]
        + 0.10 * df["related_party_risk"]
        + 0.10 * overdue_norm
    )

    df["composite_risk_score"] = (composite_raw * 10.0).clip(upper=10.0)

    # Drop helper columns not needed downstream.
    df = df.drop(columns=["amount_mean_by_category", "amount_std_by_category"])

    return df

