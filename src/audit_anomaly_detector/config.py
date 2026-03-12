from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    """Configuration for input audit data sources."""

    raw_data_dir: Path = Field(default=Path("data") / "raw")
    processed_data_dir: Path = Field(default=Path("data") / "processed")
    train_file: str = "train.csv"
    inference_file: str = "inference.csv"


class ModelConfig(BaseModel):
    """Configuration for the anomaly detector model."""

    model_type: str = "isolation_forest"
    random_state: int = 42
    contamination: float = 0.01
    n_estimators: int = 200
    model_dir: Path = Field(default=Path("models"))
    model_name: str = "audit_anomaly_detector.pkl"


class FeatureConfig(BaseModel):
    """Configuration for feature engineering."""

    include_aggregations: bool = True
    include_sequence_features: bool = False
    max_categories: int = 50


class TrainingConfig(BaseModel):
    """Top-level training configuration."""

    data: DataConfig = Field(default_factory=DataConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    experiment_name: str = "default_experiment"
    output_dir: Path = Field(default=Path("artifacts"))


def load_default_config() -> TrainingConfig:
    """Return a default configuration instance.

    Later you can extend this to load from YAML/JSON if present.
    """

    return TrainingConfig()


def load_config_from_file(path: Optional[Path]) -> TrainingConfig:
    """Placeholder for loading configuration from a file."""

    if path is None or not path.exists():
        return load_default_config()
    # TODO: implement YAML/JSON config loading
    return load_default_config()

