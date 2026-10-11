from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from .models import make_pipeline, model_parameter_grid


@dataclass
class EvaluationBundle:
    metrics: pd.DataFrame
    fold_metrics: pd.DataFrame
    oof_predictions: pd.DataFrame
    selection_log: pd.DataFrame


def _confidence_interval(values: np.ndarray, seed: int = 42, repetitions: int = 1000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(repetitions, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _candidate_name(columns: list[str]) -> str:
    return "+".join(columns)


def _inner_select(
    train_frame: pd.DataFrame,
    target: str,
    groups: pd.Series,
    candidates: list[list[str]],
    model_name: str,
    inner_splits: int,
    seed: int,
) -> tuple[list[str], dict[str, object], float, list[dict[str, object]]]:
    n_groups = groups.nunique()
    n_splits = min(inner_splits, n_groups)
    if n_splits < 2:
        raise ValueError("At least two training groups are required for inner grouped CV")
    splitter = GroupKFold(n_splits=n_splits)
    rows: list[dict[str, object]] = []
    for candidate, params in product(candidates, model_parameter_grid(model_name)):
        fold_scores: list[float] = []
        for inner_train, inner_valid in splitter.split(train_frame, train_frame[target], groups):
            pipe = make_pipeline(train_frame.iloc[inner_train], candidate, model_name, params, seed)
            pipe.fit(train_frame.iloc[inner_train][candidate], train_frame.iloc[inner_train][target])
            prediction = pipe.predict(train_frame.iloc[inner_valid][candidate])
            fold_scores.append(mean_absolute_error(train_frame.iloc[inner_valid][target], prediction))
        rows.append(
            {
                "model": model_name,
                "candidate_features": _candidate_name(candidate),
                "params": repr(params),
                "inner_mae": float(np.mean(fold_scores)),
                "inner_mae_sd": float(np.std(fold_scores, ddof=0)),
            }
        )
    scores = pd.DataFrame(rows).sort_values(["inner_mae", "candidate_features", "params"], kind="stable")
    best = scores.iloc[0]
    selected = next(candidate for candidate in candidates if _candidate_name(candidate) == best["candidate_features"])
    params = next(params for params in model_parameter_grid(model_name) if repr(params) == best["params"])
    return selected, params, float(best["inner_mae"]), rows


def run_nested_grouped_cv(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target: str,
    groups: Iterable[object],
    model_names: tuple[str, ...] = ("random_forest", "xgboost"),
    outer_splits: int = 3,
    inner_splits: int = 2,
    seed: int = 42,
    candidate_feature_sets: list[list[str]] | None = None,
    feature_set_name: str = "custom",
) -> EvaluationBundle:
    frame = frame.reset_index(drop=True)
    group_series = pd.Series(groups).reset_index(drop=True).astype(str)
    if len(group_series) != len(frame):
        raise ValueError("groups must have the same length as frame")
    if group_series.nunique() < outer_splits:
        raise ValueError("outer_splits cannot exceed the number of groups")
    candidates = candidate_feature_sets or [feature_columns]
    outer_splitter = GroupKFold(n_splits=outer_splits)
    oof_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []

    for fold, (train_idx, test_idx) in enumerate(outer_splitter.split(frame, frame[target], group_series)):
        train_frame = frame.iloc[train_idx].copy()
        test_frame = frame.iloc[test_idx].copy()
        train_groups = group_series.iloc[train_idx]
        for model_name in model_names:
            selected, params, inner_mae, inner_rows = _inner_select(
                train_frame=train_frame,
                target=target,
                groups=train_groups,
                candidates=candidates,
                model_name=model_name,
                inner_splits=inner_splits,
                seed=seed + fold,
            )
            for row in inner_rows:
                selection_rows.append({"outer_fold": fold, "feature_set": feature_set_name, **row})
            pipe = make_pipeline(train_frame, selected, model_name, params, seed + fold)
            pipe.fit(train_frame[selected], train_frame[target])
            prediction = pipe.predict(test_frame[selected])
            observed = test_frame[target].to_numpy(dtype=float)
            fold_rows.append(
                {
                    "feature_set": feature_set_name,
                    "model": model_name,
                    "outer_fold": fold,
                    "n_test": len(test_frame),
                    "n_groups": test_frame["group_id"].nunique() if "group_id" in test_frame else group_series.iloc[test_idx].nunique(),
                    "mae": mean_absolute_error(observed, prediction),
                    "rmse": mean_squared_error(observed, prediction) ** 0.5,
                    "r2": r2_score(observed, prediction),
                    "selected_features": _candidate_name(selected),
                    "inner_mae": inner_mae,
                }
            )
            for row_index, group_id, observed_value, predicted_value in zip(test_idx, group_series.iloc[test_idx], observed, prediction):
                oof_rows.append(
                    {
                        "row_index": int(row_index),
                        "group_id": group_id,
                        "feature_set": feature_set_name,
                        "model": model_name,
                        "outer_fold": fold,
                        "observed": float(observed_value),
                        "prediction": float(predicted_value),
                        "selected_features": _candidate_name(selected),
                    }
                )

    oof = pd.DataFrame(oof_rows)
    fold_metrics = pd.DataFrame(fold_rows)
    metric_rows: list[dict[str, object]] = []
    for model_name in model_names:
        subset = oof[oof["model"].eq(model_name)].sort_values("row_index")
        observed = subset["observed"].to_numpy()
        prediction = subset["prediction"].to_numpy()
        fold_subset = fold_metrics[fold_metrics["model"].eq(model_name)]
        mae_ci = _confidence_interval(np.abs(observed - prediction), seed + 1)
        rmse_ci = _confidence_interval((observed - prediction) ** 2, seed + 2)
        metric_rows.append(
            {
                "validation": "publication_grouped_nested_cv",
                "feature_set": feature_set_name,
                "model": model_name,
                "n_oof": len(subset),
                "n_groups": subset["group_id"].nunique(),
                "mae": mean_absolute_error(observed, prediction),
                "rmse": mean_squared_error(observed, prediction) ** 0.5,
                "r2": r2_score(observed, prediction),
                "mae_ci_low": mae_ci[0],
                "mae_ci_high": mae_ci[1],
                "rmse_ci_low": float(np.sqrt(max(rmse_ci[0], 0))),
                "rmse_ci_high": float(np.sqrt(max(rmse_ci[1], 0))),
                "fold_mae_sd": float(fold_subset["mae"].std(ddof=0)),
                "fold_rmse_sd": float(fold_subset["rmse"].std(ddof=0)),
                "fold_r2_sd": float(fold_subset["r2"].std(ddof=0)),
                "selected_features": " | ".join(sorted(fold_subset["selected_features"].unique())),
            }
        )
    return EvaluationBundle(pd.DataFrame(metric_rows), fold_metrics, oof, pd.DataFrame(selection_rows))


def fit_final_pipeline(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target: str,
    model_name: str,
    groups: Iterable[object],
    candidate_feature_sets: list[list[str]] | None = None,
    inner_splits: int = 3,
    seed: int = 42,
):
    """Select a configuration using grouped inner CV, then fit it on all rows."""

    frame = frame.reset_index(drop=True)
    group_series = pd.Series(groups).reset_index(drop=True).astype(str)
    candidates = candidate_feature_sets or [feature_columns]
    selected, params, inner_mae, selection_rows = _inner_select(
        train_frame=frame,
        target=target,
        groups=group_series,
        candidates=candidates,
        model_name=model_name,
        inner_splits=inner_splits,
        seed=seed,
    )
    pipeline = make_pipeline(frame, selected, model_name, params, seed)
    pipeline.fit(frame[selected], frame[target])
    metadata = {
        "model": model_name,
        "selected_features": selected,
        "params": params,
        "inner_mae": inner_mae,
        "selection_rows": selection_rows,
    }
    return pipeline, metadata


def write_evaluation_bundle(bundle: EvaluationBundle, output_dir: Path, prefix: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle.metrics.to_csv(output_dir / f"{prefix}_metrics.csv", index=False)
    bundle.fold_metrics.to_csv(output_dir / f"{prefix}_fold_metrics.csv", index=False)
    bundle.oof_predictions.to_csv(output_dir / f"{prefix}_oof_predictions.csv", index=False)
    bundle.selection_log.to_csv(output_dir / f"{prefix}_selection_log.csv", index=False)
