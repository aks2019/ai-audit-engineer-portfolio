"""
Top-level package for the audit anomaly detector.

This package is organized into the following submodules:
- data: data access and loading
- features: feature engineering logic
- models: anomaly detection models and model registry
- evaluation: metrics and evaluation utilities
- pipelines: training and inference orchestration
- utils: shared helpers (logging, config, etc.)
"""

__all__ = [
    "config",
    "data",
    "features",
    "models",
    "evaluation",
    "pipelines",
    "utils",
]

