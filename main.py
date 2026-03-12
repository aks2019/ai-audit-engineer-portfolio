from __future__ import annotations

import argparse
from pathlib import Path

from audit_anomaly_detector.pipelines.training import run_training
from audit_anomaly_detector.pipelines.inference import run_inference
from audit_anomaly_detector.utils.logging import get_logger


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Vendor Payment Anomaly Detector - main entry point"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("train", help="Run model training pipeline")
    subparsers.add_parser("inference", help="Run inference pipeline on latest data")

    gen_parser = subparsers.add_parser(
        "generate-data", help="Generate synthetic vendor payment data"
    )
    gen_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "raw" / "vendor_payments.csv",
        help="Output CSV path for synthetic vendor payments",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "train":
        logger.info("Starting training pipeline...")
        run_training()
    elif args.command == "inference":
        logger.info("Starting inference pipeline...")
        run_inference()
    elif args.command == "generate-data":
        logger.info("Generating synthetic vendor payment data...")
        # Import here to avoid hard dependency during simple operations
        from data.generate_synthetic_vendor_data import generate_and_save

        generate_and_save(output_path=args.output)
    else:
        raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()

