from pathlib import Path

import pandas as pd

from audit_anomaly_detector.config import TrainingConfig
from audit_anomaly_detector.pipelines.training import run_training


def test_run_training_writes_model(tmp_path: Path, monkeypatch) -> None:
    # Arrange config to use temporary directories and a small CSV
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)

    train_path = processed / "train.csv"
    pd.DataFrame({"amount": [1.0, 2.0, 3.0]}).to_csv(train_path, index=False)

    cfg = TrainingConfig()
    cfg.data.raw_data_dir = raw
    cfg.data.processed_data_dir = processed
    cfg.output_dir = tmp_path / "artifacts"
    cfg.model.model_dir = tmp_path / "models"

    # Act
    model_path = run_training(config=cfg)

    # Assert
    assert model_path.exists()

