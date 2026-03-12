from pathlib import Path

from audit_anomaly_detector.config import TrainingConfig, load_default_config
from audit_anomaly_detector.data.loaders import load_audit_table
from audit_anomaly_detector.features.engineering import basic_feature_pipeline
from audit_anomaly_detector.models.detector import save_model, train_model
from audit_anomaly_detector.utils.logging import get_logger


logger = get_logger(__name__)


def run_training(config: TrainingConfig | None = None) -> Path:
    """End-to-end training pipeline stub.

    Steps:
    1. Load audit data
    2. Build features
    3. Train anomaly detector
    4. Save model
    """

    cfg = config or load_default_config()

    logger.info("Loading training data...")
    df = load_audit_table(config=cfg.data, split="train")

    logger.info("Running feature engineering...")
    features, _ = basic_feature_pipeline(df)

    logger.info("Training anomaly detector...")
    model, scores = train_model(features, config=cfg.model)

    logger.info("Saving trained model...")
    model_path = save_model(model, config=cfg.model)

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    scores_path = cfg.output_dir / f"{cfg.experiment_name}_train_scores.parquet"
    features.assign(anomaly_score=scores).to_parquet(scores_path, index=False)

    logger.info("Training complete.")
    logger.info("Model saved at %s", model_path)
    logger.info("Training scores saved at %s", scores_path)

    return model_path


if __name__ == "__main__":
    run_training()

