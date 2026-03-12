import pandas as pd

from audit_anomaly_detector.features.engineering import basic_feature_pipeline


def test_basic_feature_pipeline_runs() -> None:
    df = pd.DataFrame(
        {
            "amount": [100.0, 200.5],
            "user": ["u1", "u2"],
        }
    )
    features, original = basic_feature_pipeline(df)

    assert len(features) == len(df)
    assert original.equals(df)

