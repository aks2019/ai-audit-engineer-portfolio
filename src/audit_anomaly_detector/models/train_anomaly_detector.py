from __future__ import annotations

"""
Vendor Payment Anomaly Detector - Model Training Script

This module trains:
1. An Isolation Forest for unsupervised anomaly detection
2. An XGBoost regressor to approximate the composite risk score

It also:
- Generates SHAP-based, plain-language explanations
- Writes flagged transactions to CSV
- Saves everything to PostgreSQL audit table (with graceful fallback)
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
<<<<<<< HEAD
from src.audit_anomaly_detector.database.postgres_connector import save_flagged_to_postgres
=======
from src.audit_anomaly_detector.database.postgres_connector import (
    save_flagged_to_postgres,
)

>>>>>>> e493e81aee087ef3d70c60041e0d312900c25112

PROCESSED_PATH = Path("data") / "processed" / "vendor_payments_processed.csv"
MODELS_DIR = Path("models")
RESULTS_DIR = Path("data") / "results"
FLAGGED_PATH = RESULTS_DIR / "flagged_transactions.csv"


def _build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = ["amount"] + list(RISK_FEATURE_COLUMNS)
    return df[feature_cols].copy()


def _fit_isolation_forest(X: pd.DataFrame) -> IsolationForest:
    model = IsolationForest(
        contamination=0.05, random_state=42, n_estimators=200, n_jobs=-1
    )
    model.fit(X)
    return model


def _compute_anomaly_scores(model: IsolationForest, X: pd.DataFrame) -> tuple:
    raw_pred = model.predict(X)
    anomaly_score = -raw_pred

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
    model = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        objective="reg:squarederror", random_state=42
    )
    model.fit(X, y)
    return model


def _explain_with_shap(model: XGBRegressor, X: pd.DataFrame, df_original: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    top = df_original.sort_values("composite_risk_score", ascending=False).head(top_n)
    top_indices = top.index
    X_top = X.loc[top_indices]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_top)
    feature_names = list(X.columns)

    explanations: List[str] = []
    for i, row_idx in enumerate(top_indices):
        row_vals = X_top.iloc[i]
        row_shap = shap_values[i]
        sorted_idx = np.argsort(np.abs(row_shap))[::-1]
        top_feat = sorted_idx[:3]

        parts: List[str] = []
        for fi in top_feat:
            name = feature_names[fi]
            value = row_vals.iloc[fi]
            contrib = row_shap[fi]

            if name == "amount":
                parts.append(f"amount is ₹{value:,.0f}")
            elif name == "amount_ratio":
                parts.append(f"amount is {value:.1f}× historical average")
            elif name == "related_party_risk" and value >= 0.5:
                parts.append("related-party high-value flag")
            elif name == "overdue_risk_score" and value > 0:
                parts.append(f"overdue by ~{value*30:.0f} days")

        explanation = "Flagged because " + " + ".join(parts) if parts else "Flagged due to combined risk signals."
        explanations.append(explanation)

    top = top.copy()
    top["risk_explanation"] = explanations
    return top


def main() -> None:
    if not PROCESSED_PATH.exists():
        raise FileNotFoundError(f"Processed data not found at {PROCESSED_PATH}")

    df = pd.read_csv(PROCESSED_PATH, parse_dates=["payment_date"])

    X = _build_feature_matrix(df)
    y = df["composite_risk_score"]

    # Train models
    iso_model = _fit_isolation_forest(X)
    anomaly_score, anomaly_probability = _compute_anomaly_scores(iso_model, X)
    df["anomaly_score"] = anomaly_score
    df["anomaly_probability"] = anomaly_probability

    xgb_model = _fit_xgb_regressor(X, y)

    # SHAP explanations
    explained_top = _explain_with_shap(xgb_model, X, df, top_n=10)

    # Save models & CSV
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(iso_model, MODELS_DIR / "isolation_forest.joblib")
    joblib.dump(xgb_model, MODELS_DIR / "xgboost_risk_regressor.joblib")
    df.to_csv(PROCESSED_PATH, index=False)

    flagged_out = explained_top[
        ["transaction_id", "vendor_name", "amount", "anomaly_score",
         "anomaly_probability", "risk_explanation"]
    ].copy()

    flagged_out.to_csv(FLAGGED_PATH, index=False)

<<<<<<< HEAD
    # === SAVE TO SQLITE (simple & zero-setup) ===
    from src.audit_anomaly_detector.database.db_connector import save_flagged_to_db
    save_flagged_to_db(flagged_out)
    
    # Final output
=======
    # Also persist flagged rows into PostgreSQL audit table, if reachable.
    try:
        inserted = save_flagged_to_postgres(flagged_out)
        print(f"Data saved to PostgreSQL audit table (rows inserted: {inserted}).")
    except Exception as exc:  # noqa: BLE001 - safe to log generic DB error here
        print(f"Warning: could not save to PostgreSQL ({exc}).")

    # ------------------------------------------------------------------
    # 7. Print audit-friendly outputs
    # ------------------------------------------------------------------
>>>>>>> e493e81aee087ef3d70c60041e0d312900c25112
    n_anomalies = int((df["anomaly_score"] == 1).sum())
    print("Model trained successfully!")
    print(f"Total transactions: {len(df):,}")
    print(f"Number of anomalies detected: {n_anomalies:,}")
    print("✅ Week 2 complete — Data saved in SQLite database!")
    
    # Final output
    n_anomalies = int((df["anomaly_score"] == 1).sum())
    print("Model trained successfully!")
    print(f"Total transactions: {len(df):,}")
    print(f"Number of anomalies detected: {n_anomalies:,}")
    print("\n=== Top 10 flagged transactions with explanations ===")
    print(flagged_out.to_string(index=False, justify="left", max_colwidth=120))


if __name__ == "__main__":
    main()