from pathlib import Path

import pandas as pd
import pytest

from audit_anomaly_detector.config import DataConfig
from audit_anomaly_detector.data.loaders import load_audit_table


def test_load_audit_table_missing_file(tmp_path: Path) -> None:
    cfg = DataConfig(processed_data_dir=tmp_path, train_file="missing.csv")
    with pytest.raises(FileNotFoundError):
        _ = load_audit_table(config=cfg, split="train")

