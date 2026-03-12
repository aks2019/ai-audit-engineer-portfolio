from typing import Dict

import numpy as np


def basic_thresholding(scores: np.ndarray, threshold: float) -> np.ndarray:
    """Convert anomaly scores into binary flags using a threshold."""

    return (scores >= threshold).astype(int)


def summarize_scores(scores: np.ndarray) -> Dict[str, float]:
    """Return simple summary statistics over anomaly scores."""

    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "min": float(np.min(scores)),
        "max": float(np.max(scores)),
        "p95": float(np.percentile(scores, 95)),
        "p99": float(np.percentile(scores, 99)),
    }

