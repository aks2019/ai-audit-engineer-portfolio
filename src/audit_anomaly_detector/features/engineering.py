from typing import Tuple

import pandas as pd
from sklearn.preprocessing import OneHotEncoder


def basic_feature_pipeline(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Very simple starter feature pipeline.

    - Splits numeric and categorical columns
    - One-hot encodes categoricals
    - Returns (features, original_df_with_index)

    You should replace this with domain-specific audit feature engineering.
    """

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=["number"]).columns.tolist()

    num_df = df[numeric_cols].copy()

    if categorical_cols:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        encoded = enc.fit_transform(df[categorical_cols])
        encoded_df = pd.DataFrame(
            encoded,
            index=df.index,
            columns=enc.get_feature_names_out(categorical_cols),
        )
        features = pd.concat([num_df, encoded_df], axis=1)
    else:
        features = num_df

    return features, df

