import sys
from pathlib import Path

# Make 'src' importable
sys.path.insert(0, str(Path(__file__).parent))

from src.audit_anomaly_detector.models.train_anomaly_detector import main

if __name__ == "__main__":
    main()