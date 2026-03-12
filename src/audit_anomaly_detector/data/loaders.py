from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from audit_anomaly_detector.config import DataConfig


def load_audit_table(
    config: Optional[DataConfig] = None,
    split: Literal["train", "inference"] = "train",
) -> pd.DataFrame:
    """Load an audit dataset (e.g. journal entries) as a DataFrame.

    This is a simple CSV-based stub you can extend to:
    - query databases
    - read from data lakes
    - apply access controls
    """

    cfg = config or DataConfig()
    base_dir = cfg.processed_data_dir
    file_name = cfg.train_file if split == "train" else cfg.inference_file
    path = Path(base_dir) / file_name

    if not path.exists():
        raise FileNotFoundError(f"Expected data file not found at {path}")

    df = pd.read_csv(path)
    return df

