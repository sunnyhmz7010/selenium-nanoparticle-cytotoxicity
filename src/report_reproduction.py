from __future__ import annotations

import hashlib
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold


SEED = 42
REPORT_TARGETS = {
    ("random_forest", "baseline"): {"mae": 11.044676, "r2": 0.700973},
    ("random_forest", "enhanced"): {"mae": 7.627901, "r2": 0.914680},
    ("xgboost", "baseline"): {"mae": 9.868701, "r2": 0.750721},
    ("xgboost", "enhanced"): {"mae": 7.196281, "r2": 0.956696},
    ("tabtransformer", "baseline"): {"mae": 24.130409, "r2": 0.002994},
    ("tabtransformer", "enhanced"): {"mae": 25.495027, "r2": 0.056558},
}

REQUIRED_COLUMNS = ["Cell_Viability (%)", "Time (hr)", "Concentration (ug/ml)"]
EXCLUDED_TEST_PATTERN = r"Characterization|Western|Cellular Uptake|DNA|LDH"
CANDIDATE_FEATURES = [
    "IC50_uM",
    "Elemental_Se_wt",
    "Stability_weeks",
    "Binding_Energy_Se3d",
    "Crystal_Code",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_report_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the filtering rules visible in the historical report script."""

    frame = source.copy()
    frame["source_row"] = np.arange(len(frame)) + 2
    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    material = frame["Material"].astype("string")
    is_selenium = material.str.contains("Se", case=False, regex=False, na=False)
    is_selenite = material.str.contains("Na₂SeO₃|Na2SeO3", case=False, regex=True, na=False)
    valid_material = is_selenium & ~is_selenite
    valid_test = ~frame["Test"].astype("string").str.contains(EXCLUDED_TEST_PATTERN, case=False, regex=True, na=False)
    complete = frame[REQUIRED_COLUMNS].notna().all(axis=1)

    reasons = np.select(
        [~valid_material, ~valid_test, ~complete],
        ["非纳米硒材料", "非细胞存活率检测", "缺少建模必需字段"],
        default="",
    )
    included = frame.loc[valid_material & valid_test & complete].copy()
    excluded = frame.loc[~(valid_material & valid_test & complete)].copy()
    excluded["exclusion_reason"] = pd.Series(reasons, index=frame.index).loc[excluded.index]

    included["Concentration_uM"] = included["Concentration (ug/ml)"] / 78.96
    included["sample_id"] = included["source_row"].map(lambda value: f"xlsx-row-{value}")
    return included.reset_index(drop=True), excluded.reset_index(drop=True)


def load_report_source(path: Path, sheet_name: str = "工作表1") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    source = pd.read_excel(path, sheet_name=sheet_name)
    included, excluded = prepare_report_frame(source)
    metadata = {
        "input_path": path.as_posix(),
        "input_sha256": file_sha256(path),
        "sheet_name": sheet_name,
        "source_rows": int(len(source)),
        "included_rows": int(len(included)),
        "excluded_rows": int(len(excluded)),
    }
    return included, excluded, metadata


def assign_folds(frame: pd.DataFrame, seed: int = SEED) -> pd.Series:
    folds = np.empty(len(frame), dtype=int)
    splitter = KFold(n_splits=3, shuffle=True, random_state=seed)
    for fold, (_, valid_index) in enumerate(splitter.split(frame)):
        folds[valid_index] = fold
    return pd.Series(folds, index=frame.index, name="fold")


def evaluate_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    required = {"model", "feature_set", "fold", "observed", "prediction"}
    if predictions.empty or not required.issubset(predictions.columns):
        raise ValueError("必须提供逐样本预测才能计算指标")
    rows: list[dict[str, object]] = []
    for (model, feature_set), group in predictions.groupby(["model", "feature_set"], sort=True):
        fold_mae = group.groupby("fold").apply(
            lambda part: mean_absolute_error(part["observed"], part["prediction"]),
            include_groups=False,
        )
        rows.append(
            {
                "model": model,
                "feature_set": feature_set,
                "n_predictions": int(len(group)),
                "mae": float(mean_absolute_error(group["observed"], group["prediction"])),
                "cv_mae_mean": float(fold_mae.mean()),
                "cv_mae_sd": float(fold_mae.std(ddof=0)),
                "r2": float(r2_score(group["observed"], group["prediction"])),
                "metric_source": "逐样本预测重新计算",
            }
        )
    return pd.DataFrame(rows)


def compare_with_report(computed: pd.DataFrame) -> dict[str, object]:
    keyed = {
        (str(row.model), str(row.feature_set)): row
        for row in computed.itertuples(index=False)
    }
    models: list[dict[str, object]] = []
    for (model, feature_set), target in REPORT_TARGETS.items():
        row = keyed.get((model, feature_set))
        computed_mae = None if row is None else float(getattr(row, "mae"))
        computed_r2 = None if row is None else float(getattr(row, "r2"))
        exact = (
            row is not None
            and round(computed_mae, 2) == round(target["mae"], 2)
            and round(computed_r2, 3) == round(target["r2"], 3)
        )
        models.append(
            {
                "model": model,
                "feature_set": feature_set,
                "target_mae": target["mae"],
                "target_r2": target["r2"],
                "computed_mae": computed_mae,
                "computed_r2": computed_r2,
                "mae_delta": None if row is None else computed_mae - target["mae"],
                "r2_delta": None if row is None else computed_r2 - target["r2"],
                "status": "exact" if exact else "missing" if row is None else "different",
            }
        )
    return {
        "status": "exact" if all(item["status"] == "exact" for item in models) else "partial",
        "models": models,
    }


def candidate_feature_combinations() -> list[list[str]]:
    return [
        list(group)
        for size in range(1, len(CANDIDATE_FEATURES) + 1)
        for group in combinations(CANDIDATE_FEATURES, size)
    ]


def make_dashboard_payload(audit: dict[str, object], comparison: dict[str, object]) -> dict[str, object]:
    return {
        "report_reproduction": {
            "status": comparison["status"],
            "values_are_computed": True,
            "report_values_are_targets_only": True,
            "audit": audit,
            "models": comparison["models"],
        }
    }
