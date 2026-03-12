from pathlib import Path

import pandas as pd

from audit_anomaly_detector.config import DataConfig, ModelConfig, load_default_config
from audit_anomaly_detector.data.loaders import load_audit_table
from audit_anomaly_detector.features.engineering import basic_feature_pipeline
from audit_anomaly_detector.models.detector import load_model
from audit_anomaly_detector.utils.logging import get_logger


logger = get_logger(__name__)


def run_inference(
    data_config: DataConfig | None = None,
    model_config: ModelConfig | None = None,
) -> Path:
    """End-to-end inference pipeline stub.

    Loads audit records, computes features, scores anomalies, and writes
    results with scores to disk.
    """

    default_cfg = load_default_config()
    data_cfg = data_config or default_cfg.data
    model_cfg = model_config or default_cfg.model

    logger.info("Loading inference data...")
    df = load_audit_table(config=data_cfg, split="inference")

    logger.info("Running feature engineering...")
    features, original_df = basic_feature_pipeline(df)

    logger.info("Loading trained model...")
    model = load_model(config=model_cfg)

    logger.info("Scoring anomalies...")
    scores = -model.decision_function(features)

    results = original_df.copy()
    results["anomaly_score"] = scores

    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "inference_scores.parquet"
    results.to_parquet(output_path, index=False)

    logger.info("Inference complete. Results saved at %s", output_path)

    return output_path


if __name__ == "__main__":
    run_inference()

