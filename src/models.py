from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


def model_parameter_grid(model_name: str) -> list[dict[str, Any]]:
    if model_name == "random_forest":
        return [
            {"n_estimators": 250, "max_depth": None, "min_samples_leaf": 2},
            {"n_estimators": 250, "max_depth": 10, "min_samples_leaf": 2},
            {"n_estimators": 250, "max_depth": None, "min_samples_leaf": 4},
        ]
    if model_name == "xgboost":
        return [
            {"n_estimators": 150, "max_depth": 2, "learning_rate": 0.05},
            {"n_estimators": 250, "max_depth": 2, "learning_rate": 0.05},
            {"n_estimators": 250, "max_depth": 3, "learning_rate": 0.05},
        ]
    raise ValueError(f"Unsupported model: {model_name}")


def make_model(model_name: str, params: dict[str, Any], seed: int):
    if model_name == "random_forest":
        return RandomForestRegressor(random_state=seed, n_jobs=1, **params)
    if model_name == "xgboost":
        return XGBRegressor(
            random_state=seed,
            n_jobs=1,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            objective="reg:squarederror",
            eval_metric="mae",
            tree_method="hist",
            **params,
        )
    raise ValueError(f"Unsupported model: {model_name}")


def make_pipeline(frame: pd.DataFrame, feature_columns: list[str], model_name: str, params: dict[str, Any], seed: int) -> Pipeline:
    observed_columns = [column for column in feature_columns if frame[column].notna().any()]
    numeric = [column for column in observed_columns if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in observed_columns if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric))
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    return Pipeline([("preprocess", preprocessor), ("model", make_model(model_name, params, seed))])
