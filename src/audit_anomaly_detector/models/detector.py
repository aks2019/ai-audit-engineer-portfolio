from pathlib import Path
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from audit_anomaly_detector.config import ModelConfig


def build_model(config: ModelConfig | None = None) -> IsolationForest:
    """Create a default anomaly detection model.

    Start with IsolationForest; you can later extend this to support
    multiple model types based on `config.model_type`.
    """

    cfg = config or ModelConfig()
    return IsolationForest(
        n_estimators=cfg.n_estimators,
        contamination=cfg.contamination,
        random_state=cfg.random_state,
    )


def train_model(
    features: pd.DataFrame,
    config: ModelConfig | None = None,
) -> Tuple[IsolationForest, np.ndarray]:
    """Fit the anomaly detector on the training features."""

    model = build_model(config)
    model.fit(features)
    scores = -model.decision_function(features)  # higher = more anomalous
    return model, scores


def save_model(model: IsolationForest, config: ModelConfig | None = None) -> Path:
    """Persist a trained model to disk."""

    cfg = config or ModelConfig()
    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.model_dir / cfg.model_name
    joblib.dump(model, path)
    return path


def load_model(config: ModelConfig | None = None) -> IsolationForest:
    """Load a trained model from disk."""

    cfg = config or ModelConfig()
    path = cfg.model_dir / cfg.model_name
    if not path.exists():
        raise FileNotFoundError(f"Model file not found at {path}")
    model: IsolationForest = joblib.load(path)
    return model

