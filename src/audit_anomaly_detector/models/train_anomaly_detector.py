from __future__ import annotations

"""
Vendor Payment Anomaly Detector - Model Training Script

This module trains:
1. An Isolation Forest for unsupervised anomaly detection
2. An XGBoost regressor to approximate the composite risk score

It also:
- Generates SHAP-based, plain-language explanations for the top risky transactions
- Writes flagged transactions with explanations to data/results/flagged_transactions.csv
- Saves trained models under models/

The focus is on simple, auditable logic rather than complex ML pipelines.
"""

from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import IsolationForest
from xgboost import XGBRegressor

from src.audit_anomaly_detector.features.engineer_features import RISK_FEATURE_COLUMNS
from src.audit_anomaly_detector.database.postgres_connector import (
    save_flagged_to_postgres,
)


PROCESSED_PATH = Path("data") / "processed" / "vendor_payments_processed.csv"
MODELS_DIR = Path("models")
RESULTS_DIR = Path("data") / "results"
FLAGGED_PATH = RESULTS_DIR / "flagged_transactions.csv"


def _build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Select numeric features used for modeling.

    We use:
    - amount
    - the engineered risk features from RISK_FEATURE_COLUMNS
    """

    feature_cols = ["amount"] + list(RISK_FEATURE_COLUMNS)
    return df[feature_cols].copy()


def _fit_isolation_forest(X: pd.DataFrame) -> IsolationForest:
    """Train an Isolation Forest as unsupervised anomaly detector."""

    model = IsolationForest(
        contamination=0.05,
        random_state=42,
        n_estimators=200,
        n_jobs=-1,
    )
    model.fit(X)
    return model


def _compute_anomaly_scores(
    model: IsolationForest, X: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Return (anomaly_score, anomaly_probability) for each row.

    - anomaly_score: -1 for normal, 1 for anomaly (auditor-friendly convention)
    - anomaly_probability: simple 0–1 scaling of anomaly-ness based on the
      model's decision function (higher means more anomalous)
    """

    # Sklearn IsolationForest's predict returns:
    #   1 for inliers (normal), -1 for outliers (anomalies).
    raw_pred = model.predict(X)
    anomaly_score = -raw_pred  # now: -1 = normal, 1 = anomaly

    # decision_function: larger values are less abnormal.
    # We invert and min-max scale into [0, 1] as a pseudo-probability.
    decision_scores = model.decision_function(X)
    anomaly_raw = -decision_scores
    min_val = anomaly_raw.min()
    max_val = anomaly_raw.max()
    if max_val > min_val:
        anomaly_probability = (anomaly_raw - min_val) / (max_val - min_val)
    else:
        anomaly_probability = np.zeros_like(anomaly_raw)

    return anomaly_score, anomaly_probability


def _fit_xgb_regressor(X: pd.DataFrame, y: pd.Series) -> XGBRegressor:
    """Train a simple gradient boosting regressor for composite risk score."""

    model = XGBRegressor(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X, y)
    return model


def _explain_with_shap(
    model: XGBRegressor,
    X: pd.DataFrame,
    df_original: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Generate plain-language SHAP explanations for top risky transactions.

    We:
    - Take the top N rows by composite_risk_score
    - Compute SHAP values for the XGBoost regressor
    - For each row, identify the top 3 contributing features
    - Turn those into a readable explanation string
    """

    # Select top risky transactions by composite risk score.
    top = df_original.sort_values("composite_risk_score", ascending=False).head(top_n)
    top_indices = top.index
    X_top = X.loc[top_indices]

    # TreeExplainer is suitable for tree-based models like XGBoost.
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_top)

    feature_names = list(X.columns)

    explanations: List[str] = []
    for i, row_idx in enumerate(top_indices):
        row_vals = X_top.iloc[i]
        row_shap = shap_values[i]

        # Rank features by absolute SHAP contribution.
        sorted_idx = np.argsort(np.abs(row_shap))[::-1]
        top_feat_indices = sorted_idx[:3]

        parts: List[str] = []
        for fi in top_feat_indices:
            name = feature_names[fi]
            value = row_vals.iloc[fi]
            shap_contrib = row_shap[fi]

            # Map feature names to simple audit language.
            if name == "amount":
                parts.append(
                    f"amount is ₹{value:,.0f} which strongly {'increases' if shap_contrib > 0 else 'reduces'} risk"
                )
            elif name == "amount_zscore":
                parts.append(
                    f"amount is {value:.1f} standard deviations above typical payments in this category"
                )
            elif name == "amount_ratio":
                parts.append(
                    f"amount is {value:.1f}× the vendor's historical average"
                )
            elif name == "high_value_flag":
                if value >= 0.5:
                    parts.append("payment sits in the highest 5% of all vendor payments")
            elif name == "related_party_risk":
                if value >= 0.5:
                    parts.append(
                        "payment is to a related party and above the high-value threshold"
                    )
            elif name == "overdue_risk_score":
                if value > 0:
                    parts.append(
                        f"invoice is overdue by roughly {value * 30:.0f} days, increasing risk"
                    )

        if not parts:
            explanation = "Flagged due to combined pattern of amount and risk signals."
        else:
            explanation = "Flagged because " + " + ".join(parts)

        explanations.append(explanation)

    top = top.copy()
    top["risk_explanation"] = explanations
    return top


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Load processed data
    # ------------------------------------------------------------------
    if not PROCESSED_PATH.exists():
        raise FileNotFoundError(f"Processed data not found at {PROCESSED_PATH}")

    df = pd.read_csv(PROCESSED_PATH, parse_dates=["payment_date"])

    # ------------------------------------------------------------------
    # 2. Build modeling matrix (drop identifiers from X)
    # ------------------------------------------------------------------
    X = _build_feature_matrix(df)
    y = df["composite_risk_score"]

    # ------------------------------------------------------------------
    # 3. Train Isolation Forest (unsupervised anomaly model)
    # ------------------------------------------------------------------
    iso_model = _fit_isolation_forest(X)
    # Sklearn IsolationForest's predict returns:
    #   1 for inliers (normal), -1 for outliers (anomalies).
    raw_pred = iso_model.predict(X)
    df["anomaly_score"] = -raw_pred  # now: -1 = normal, 1 = anomaly

    # Safe anomaly probability scaling based on decision_function.
    decision_vals = iso_model.decision_function(X)
    d_min = decision_vals.min()
    d_max = decision_vals.max()
    if d_max > d_min:
        df["anomaly_probability"] = 1 - (
            (decision_vals - d_min) / (d_max - d_min)
        )
    else:
        df["anomaly_probability"] = 0.0

    # ------------------------------------------------------------------
    # 4. Train XGBoost regressor for composite risk score
    # ------------------------------------------------------------------
    xgb_model = _fit_xgb_regressor(X, y)

    # ------------------------------------------------------------------
    # 5. SHAP explanations for top risky transactions
    # ------------------------------------------------------------------
    explained_top = _explain_with_shap(
        model=xgb_model,
        X=X,
        df_original=df,
        top_n=10,
    )

    # ------------------------------------------------------------------
    # 6. Persist models, processed data, and flagged transactions
    # ------------------------------------------------------------------
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(iso_model, MODELS_DIR / "isolation_forest.joblib")
    joblib.dump(xgb_model, MODELS_DIR / "xgboost_risk_regressor.joblib")

    # Save full processed dataframe (including anomaly columns) back to disk.
    df.to_csv(PROCESSED_PATH, index=False)

    flagged_out = explained_top[
        [
            "transaction_id",
            "vendor_name",
            "amount",
            "anomaly_score",
            "anomaly_probability",
            "risk_explanation",
        ]
    ].copy()
    flagged_out.to_csv(FLAGGED_PATH, index=False)

    # Also persist flagged rows into PostgreSQL audit table, if reachable.
    try:
        inserted = save_flagged_to_postgres(flagged_out)
        print(f"Data saved to PostgreSQL audit table (rows inserted: {inserted}).")
    except Exception as exc:  # noqa: BLE001 - safe to log generic DB error here
        print(f"Warning: could not save to PostgreSQL ({exc}).")

    # ------------------------------------------------------------------
    # 7. Print audit-friendly outputs
    # ------------------------------------------------------------------
    n_anomalies = int((df["anomaly_score"] == 1).sum())

    print("Model trained successfully!")
    print(f"Total transactions: {len(df):,}")
    print(f"Number of anomalies detected by Isolation Forest: {n_anomalies:,}")
    print("\n=== Top 10 flagged transactions with explanations ===")
    print(
        flagged_out.to_string(
            index=False,
            justify="left",
            max_colwidth=120,
        )
    )


if __name__ == "__main__":
    main()

