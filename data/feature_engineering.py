from __future__ import annotations

"""
Vendor Payment Anomaly Detector - Feature Engineering Script

This script:
1. Loads raw vendor payment data from data/raw/vendor_payments.csv
2. Creates audit-focused risk features
3. Writes the processed data to data/processed/vendor_payments_processed.csv
4. Prints key summaries useful for an internal auditor

Only pandas is used for transformations to keep the logic simple and auditable.
"""

from pathlib import Path

import pandas as pd

from src.audit_anomaly_detector.features.engineer_features import engineer_features


RAW_PATH = Path("data") / "raw" / "vendor_payments.csv"
PROCESSED_DIR = Path("data") / "processed"
PROCESSED_PATH = PROCESSED_DIR / "vendor_payments_processed.csv"


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw data not found at {RAW_PATH}")

    df = pd.read_csv(RAW_PATH, parse_dates=["payment_date"])

    # ------------------------------------------------------------------
    # 2. Create audit-focused features via reusable library function
    # ------------------------------------------------------------------
    df = engineer_features(df)

    # ------------------------------------------------------------------
    # 4. Save processed data
    # ------------------------------------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_PATH, index=False)

    # ------------------------------------------------------------------
    # 5. Print useful summaries for audit review
    # ------------------------------------------------------------------
    print("\n=== Processed data shape ===")
    print(df.shape)

    print("\n=== First 5 rows (with new features) ===")
    print(df.head())

    risk_cols = [
        "amount_zscore",
        "amount_ratio",
        "high_value_flag",
        "related_party_risk",
        "overdue_risk_score",
        "composite_risk_score",
    ]

    print("\n=== Risk feature summary statistics ===")
    print(df[risk_cols].describe().transpose())

    print("\n=== Top 10 highest composite_risk_score transactions ===")
    top10 = df.sort_values("composite_risk_score", ascending=False).head(10)
    print(
        top10[
            [
                "transaction_id",
                "vendor_id",
                "vendor_name",
                "amount",
                "category",
                "related_party",
                "days_overdue",
                "amount_zscore",
                "amount_ratio",
                "overdue_risk_score",
                "composite_risk_score",
            ]
        ]
    )


if __name__ == "__main__":
    main()

