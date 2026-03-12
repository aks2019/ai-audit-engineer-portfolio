import numpy as np
import pandas as pd

from audit_anomaly_detector.models.detector import train_model


def test_train_model_returns_scores() -> None:
    features = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
    model, scores = train_model(features)

    assert scores.shape[0] == features.shape[0]
    assert isinstance(scores, np.ndarray)

