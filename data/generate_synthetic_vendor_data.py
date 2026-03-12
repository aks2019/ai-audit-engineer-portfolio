from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

try:
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without loguru
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("synthetic-vendor-data")


RNG_SEED = 42
N_ROWS = 10_000


def _sample_dates(n: int) -> List[dt.date]:
    """Sample realistic payment dates over the last 2 years."""

    end = dt.date.today()
    start = end - dt.timedelta(days=730)
    days = np.random.default_rng(RNG_SEED).integers(
        low=0, high=(end - start).days, size=n
    )
    return [start + dt.timedelta(days=int(d)) for d in days]


def _build_base_dataframe(n_rows: int, rng: np.random.Generator) -> pd.DataFrame:
    vendor_ids = [f"V{1000 + i}" for i in range(200)]
    vendor_names = [f"Vendor_{i:03d}" for i in range(200)]
    plants = [f"P{str(i).zfill(3)}" for i in range(1, 11)]
    cost_centers = [f"CC{str(i).zfill(4)}" for i in range(100, 200)]
    categories = [
        "Raw Material",
        "Packaging",
        "Logistics",
        "Services",
        "Utilities",
        "Maintenance",
        "IT Services",
    ]
    frequencies = ["One-off", "Monthly", "Quarterly", "Ad-hoc"]

    logger.info("Sampling base attributes for %d rows.", n_rows)

    vendor_idx = rng.integers(0, len(vendor_ids), size=n_rows)
    payment_dates = _sample_dates(n_rows)

    # Baseline amounts in INR
    base_amounts = rng.lognormal(mean=11.0, sigma=0.5, size=n_rows)
    base_amounts = np.clip(base_amounts, 50_000, 50_000_000)  # 50k – 5Cr

    previous_avg = base_amounts * rng.uniform(0.7, 1.3, size=n_rows)

    df = pd.DataFrame(
        {
            "transaction_id": [f"T{100000 + i}" for i in range(n_rows)],
            "payment_date": payment_dates,
            "invoice_number": [
                f"INV-{rng.integers(100000, 999999)}" for _ in range(n_rows)
            ],
            "po_number": [f"PO-{rng.integers(100000, 999999)}" for _ in range(n_rows)],
            "vendor_id": [vendor_ids[i] for i in vendor_idx],
            "vendor_name": [vendor_names[i] for i in vendor_idx],
            "amount": base_amounts,
            "category": rng.choice(categories, size=n_rows, replace=True),
            "plant_code": rng.choice(plants, size=n_rows, replace=True),
            "cost_center": rng.choice(cost_centers, size=n_rows, replace=True),
            "related_party": rng.choice([0, 1], p=[0.9, 0.1], size=n_rows),
            "days_overdue": rng.integers(-10, 120, size=n_rows),
            "payment_frequency": rng.choice(frequencies, size=n_rows, replace=True),
            "previous_avg_amount": previous_avg,
        }
    )

    return df


def _inject_anomalies(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    logger.info("Injecting audit-relevant anomalies.")
    df = df.copy()

    # 1. Sudden spikes vs historical average
    n_spikes = int(0.02 * len(df))
    spike_idx = rng.choice(df.index, size=n_spikes, replace=False)
    df.loc[spike_idx, "amount"] = df.loc[spike_idx, "previous_avg_amount"] * rng.uniform(
        3.0, 10.0, size=n_spikes
    )

    # 2. Related-party unusually high values
    related_mask = (df["related_party"] == 1) & (
        df["amount"] < df["previous_avg_amount"] * 5
    )
    related_idx = df[related_mask].index
    n_related = min(len(related_idx), int(0.01 * len(df)))
    if n_related > 0:
        chosen = rng.choice(related_idx, size=n_related, replace=False)
        df.loc[chosen, "amount"] = rng.uniform(10_00_000, 5_00_00_000, size=n_related)

    # 3. Just-below approval thresholds (e.g. 5L, 10L, 50L)
    thresholds = np.array([500_000, 1_000_000, 5_000_000], dtype=float)
    n_threshold = int(0.03 * len(df))
    thr_idx = rng.choice(df.index, size=n_threshold, replace=False)
    deltas = rng.uniform(1000, 5000, size=n_threshold)
    chosen_thresholds = rng.choice(thresholds, size=n_threshold, replace=True)
    df.loc[thr_idx, "amount"] = chosen_thresholds - deltas

    # 4. Overdue clusters for specific vendors/cost centers
    cluster_vendors = df["vendor_id"].value_counts().head(5).index.tolist()
    cluster_cc = df["cost_center"].value_counts().head(5).index.tolist()
    cluster_mask = df["vendor_id"].isin(cluster_vendors) & df["cost_center"].isin(
        cluster_cc
    )
    cluster_idx = df[cluster_mask].index
    n_overdue = min(len(cluster_idx), int(0.05 * len(df)))
    if n_overdue > 0:
        chosen = rng.choice(cluster_idx, size=n_overdue, replace=False)
        df.loc[chosen, "days_overdue"] = rng.integers(60, 180, size=n_overdue)

    return df


def generate_synthetic_vendor_payments(n_rows: int = N_ROWS) -> pd.DataFrame:
    """Generate a synthetic SAP FICO-style vendor payment dataset."""

    rng = np.random.default_rng(RNG_SEED)
    logger.info("Generating synthetic vendor payment dataset with %d rows.", n_rows)
    df = _build_base_dataframe(n_rows, rng)
    df = _inject_anomalies(df, rng)
    df["payment_date"] = pd.to_datetime(df["payment_date"])
    return df


def generate_and_save(output_path: Path | str = Path("data") / "raw" / "vendor_payments.csv") -> Path:
    """Generate synthetic data and save to CSV."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate_synthetic_vendor_payments()
    logger.info("Writing synthetic vendor payments to %s", output_path)
    df.to_csv(output_path, index=False)

    return output_path


if __name__ == "__main__":
    generate_and_save()

