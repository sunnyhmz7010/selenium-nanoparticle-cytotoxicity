from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier, XGBRegressor


ROOT = Path(r"D:\BaiduSyncdisk\暨南大学\综测\暨南大学2025年度大学生创新创业训练计划项目\智构·智解：基于多模态深度学习的纳米硒毒性预测")
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _clean_na(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.replace(
            {
                "-": pd.NA,
                "--": pd.NA,
                "NA": pd.NA,
                "N/A": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "Surface_Charge": pd.NA,
            }
        )
    return series


def _parse_se_wt(value: object) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value)
    m = re.search(r"Se\s*([0-9]+(?:\.[0-9]+)?)", text)
    return float(m.group(1)) if m else np.nan


def _normalize_surface_charge(value: object, zeta: float | None = None) -> str:
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    low = text.lower()
    if low in {"negative", "neg", "-"}:
        return "Negative"
    if low in {"positive", "pos", "+"}:
        return "Positive"
    if low in {"neutral", "0", "zero"}:
        return "Neutral"
    try:
        val = float(text)
        if val < 0:
            return "Negative"
        if val > 0:
            return "Positive"
        return "Neutral"
    except ValueError:
        pass
    if zeta is not None and not pd.isna(zeta):
        if zeta < 0:
            return "Negative"
        if zeta > 0:
            return "Positive"
        return "Neutral"
    return text


def prepare_raw_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in df.columns:
        df[col] = _clean_na(df[col])

    numeric_cols = [
        "Year",
        "Diameter (nm)",
        "Size_in_Water (nm)",
        "Size_in_Medium (nm)",
        "Zeta_in_Water (mV)",
        "Zeta_in_Medium (mV)",
        "No_of_Cells (cells/well)",
        "Time (hr)",
        "Concentration (ug/ml)",
        "Cell_Viability (%)",
        "IC50 (µM)",
        "Binding Energy Se3d (eV)",
        "Long-term Stability (weeks)",
        "Crystallinity / Fringe Spacing (Å)",
        "Size Ratio",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = _num(df[col])

    df["Elemental_Se_wt"] = df["Elemental Composition (wt%)"].map(_parse_se_wt)
    df["size_final"] = df["Diameter (nm)"].fillna(df["Size_in_Water (nm)"]).fillna(df["Size_in_Medium (nm)"])
    df["zeta_final"] = df["Zeta_in_Water (mV)"].fillna(df["Zeta_in_Medium (mV)"])
    df["abs_zeta"] = df["zeta_final"].abs()
    df["log_size"] = np.log1p(df["size_final"])
    df["log_concentration"] = np.log1p(df["Concentration (ug/ml)"])
    df["IC50_uM"] = df["IC50 (µM)"]
    df["Stability_weeks"] = df["Long-term Stability (weeks)"]
    df["Binding_Energy_Se3d"] = df["Binding Energy Se3d (eV)"]
    df["Crystal_Code"] = np.where(df["Crystallinity / Fringe Spacing (Å)"].notna(), 1.0, 0.0)
    df["zeta_missing"] = df["zeta_final"].isna().astype(int)
    df["cell_count_missing"] = df["No_of_Cells (cells/well)"].isna().astype(int)
    df["coat_missing"] = df["Coat/Functional Group"].isna().astype(int)
    df["surface_charge_missing"] = df["Surface_Charge"].isna().astype(int)
    df["Surface_Charge"] = [
        _normalize_surface_charge(v, z)
        for v, z in zip(df["Surface_Charge"], df["zeta_final"])
    ]
    df["toxicity_class"] = (df["Cell_Viability (%)"] < 85).astype(int)
    df["group_id"] = df["DOI"].fillna(df["Article_ID"]).astype(str)
    return df


@dataclass
class ExperimentSpec:
    name: str
    task: str
    dataframe: pd.DataFrame
    features: list[str]
    target: str
    groups: pd.Series
    splitter: object
    models: dict[str, object]


def make_preprocessor(frame: pd.DataFrame, features: list[str]) -> ColumnTransformer:
    numeric = [c for c in features if pd.api.types.is_numeric_dtype(frame[c])]
    categorical = [c for c in features if c not in numeric]
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
        ]
    )


def sanitize_frame(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    out = frame[features].copy()
    for col in features:
        if pd.api.types.is_numeric_dtype(frame[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = out[col].astype(object)
            out[col] = out[col].where(pd.notna(out[col]), np.nan)
    return out


def evaluate_regression(spec: ExperimentSpec) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    X = sanitize_frame(spec.dataframe, spec.features)
    y = spec.dataframe[spec.target]
    groups = spec.groups
    for model_name, model in spec.models.items():
        fold_metrics = []
        for fold, (train_idx, test_idx) in enumerate(spec.splitter.split(X, y, groups)):
            pipe = Pipeline([("prep", make_preprocessor(spec.dataframe, spec.features)), ("model", clone(model))])
            pipe.fit(X.iloc[train_idx], y.iloc[train_idx])
            pred = pipe.predict(X.iloc[test_idx])
            fold_metrics.append(
                {
                    "fold": fold,
                    "r2": r2_score(y.iloc[test_idx], pred),
                    "mae": mean_absolute_error(y.iloc[test_idx], pred),
                    "rmse": mean_squared_error(y.iloc[test_idx], pred) ** 0.5,
                }
            )
        rows.append(
            {
                "experiment": spec.name,
                "task": "regression",
                "model": model_name,
                "rows": len(spec.dataframe),
                "doi_groups": spec.groups.nunique(),
                "r2_mean": float(np.mean([m["r2"] for m in fold_metrics])),
                "r2_std": float(np.std([m["r2"] for m in fold_metrics], ddof=0)),
                "mae_mean": float(np.mean([m["mae"] for m in fold_metrics])),
                "mae_std": float(np.std([m["mae"] for m in fold_metrics], ddof=0)),
                "rmse_mean": float(np.mean([m["rmse"] for m in fold_metrics])),
                "rmse_std": float(np.std([m["rmse"] for m in fold_metrics], ddof=0)),
                "features": ",".join(spec.features),
            }
        )
    return rows


def evaluate_classification(spec: ExperimentSpec) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    X = sanitize_frame(spec.dataframe, spec.features)
    y = spec.dataframe[spec.target].astype(int)
    groups = spec.groups
    for model_name, model in spec.models.items():
        fold_metrics = []
        for fold, (train_idx, test_idx) in enumerate(spec.splitter.split(X, y, groups)):
            pipe = Pipeline([("prep", make_preprocessor(spec.dataframe, spec.features)), ("model", clone(model))])
            pipe.fit(X.iloc[train_idx], y.iloc[train_idx])
            proba = pipe.predict_proba(X.iloc[test_idx])[:, 1]
            pred = (proba >= 0.5).astype(int)
            auc = np.nan
            if y.iloc[test_idx].nunique() > 1:
                auc = roc_auc_score(y.iloc[test_idx], proba)
            fold_metrics.append(
                {
                    "fold": fold,
                    "auc": auc,
                    "accuracy": accuracy_score(y.iloc[test_idx], pred),
                    "f1": f1_score(y.iloc[test_idx], pred, zero_division=0),
                }
            )
        rows.append(
            {
                "experiment": spec.name,
                "task": "classification",
                "model": model_name,
                "rows": len(spec.dataframe),
                "doi_groups": spec.groups.nunique(),
                "auc_mean": float(np.nanmean([m["auc"] for m in fold_metrics])),
                "auc_std": float(np.nanstd([m["auc"] for m in fold_metrics], ddof=0)),
                "accuracy_mean": float(np.mean([m["accuracy"] for m in fold_metrics])),
                "accuracy_std": float(np.std([m["accuracy"] for m in fold_metrics], ddof=0)),
                "f1_mean": float(np.mean([m["f1"] for m in fold_metrics])),
                "f1_std": float(np.std([m["f1"] for m in fold_metrics], ddof=0)),
                "features": ",".join(spec.features),
            }
        )
    return rows


def build_current_specs() -> list[ExperimentSpec]:
    feature_list = [
        "Coat/Functional Group",
        "Synthesis_Method",
        "Surface_Charge",
        "Cell_Type",
        "Cell_Tissue",
        "Year",
        "size_final",
        "zeta_final",
        "abs_zeta",
        "Time (hr)",
        "Concentration (ug/ml)",
        "log_size",
        "log_concentration",
        "No_of_Cells (cells/well)",
        "zeta_missing",
        "cell_count_missing",
        "coat_missing",
        "surface_charge_missing",
    ]
    reg_df = pd.read_csv(DATA_DIR / "subset_regression_mtt_negative_charge.csv")
    cls_zeta_df = pd.read_csv(DATA_DIR / "subset_classification_best_auc_mtt_zeta.csv")
    cls_all_df = pd.read_csv(DATA_DIR / "subset_classification_broad_mtt_all.csv")

    reg_models = {
        "random_forest": RandomForestRegressor(n_estimators=500, min_samples_leaf=2, random_state=42, n_jobs=-1),
        "xgboost": XGBRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=4,
        ),
    }
    cls_models = {
        "extra_trees": ExtraTreesClassifier(n_estimators=600, min_samples_leaf=2, class_weight="balanced", random_state=42, n_jobs=-1),
        "random_forest": RandomForestClassifier(n_estimators=500, min_samples_leaf=2, class_weight="balanced", random_state=42, n_jobs=-1),
        "xgboost": XGBClassifier(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=4,
            eval_metric="logloss",
        ),
    }
    return [
        ExperimentSpec(
            name="current_regression_grouped_mtt_negative_charge",
            task="regression",
            dataframe=reg_df,
            features=feature_list,
            target="Cell_Viability (%)",
            groups=reg_df["group_id"],
            splitter=GroupKFold(n_splits=5),
            models=reg_models,
        ),
        ExperimentSpec(
            name="current_classification_grouped_mtt_zeta",
            task="classification",
            dataframe=cls_zeta_df,
            features=feature_list,
            target="toxicity_class",
            groups=cls_zeta_df["group_id"],
            splitter=GroupKFold(n_splits=5),
            models=cls_models,
        ),
        ExperimentSpec(
            name="current_classification_grouped_mtt_all",
            task="classification",
            dataframe=cls_all_df,
            features=feature_list,
            target="toxicity_class",
            groups=cls_all_df["group_id"],
            splitter=GroupKFold(n_splits=5),
            models=cls_models,
        ),
    ]


def build_raw_specs(raw_df: pd.DataFrame) -> list[ExperimentSpec]:
    base = raw_df[(raw_df["Test"] == "MTT") & raw_df["Cell_Viability (%)"].notna() & raw_df["Time (hr)"].notna() & raw_df["Concentration (ug/ml)"].notna()].copy()
    base = base[base["group_id"].notna()]

    core_features = [
        "Coat/Functional Group",
        "Synthesis_Method",
        "Surface_Charge",
        "Cell_Type",
        "Cell_Tissue",
        "Year",
        "size_final",
        "zeta_final",
        "abs_zeta",
        "Time (hr)",
        "Concentration (ug/ml)",
        "log_size",
        "log_concentration",
        "No_of_Cells (cells/well)",
        "zeta_missing",
        "cell_count_missing",
        "coat_missing",
        "surface_charge_missing",
    ]
    chem_features = core_features + ["Elemental_Se_wt", "Stability_weeks", "Binding_Energy_Se3d", "Crystal_Code"]
    leak_features = chem_features + ["IC50_uM"]

    reg_models = {
        "random_forest": RandomForestRegressor(n_estimators=500, min_samples_leaf=2, random_state=42, n_jobs=-1),
        "xgboost": XGBRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=4,
        ),
    }
    return [
        ExperimentSpec(
            name="raw_mtt_core_grouped_regression",
            task="regression",
            dataframe=base,
            features=core_features,
            target="Cell_Viability (%)",
            groups=base["group_id"],
            splitter=GroupKFold(n_splits=3),
            models=reg_models,
        ),
        ExperimentSpec(
            name="raw_mtt_chemistry_no_ic50_grouped_regression",
            task="regression",
            dataframe=base,
            features=chem_features,
            target="Cell_Viability (%)",
            groups=base["group_id"],
            splitter=GroupKFold(n_splits=3),
            models=reg_models,
        ),
        ExperimentSpec(
            name="raw_mtt_chemistry_plus_ic50_grouped_regression",
            task="regression",
            dataframe=base,
            features=leak_features,
            target="Cell_Viability (%)",
            groups=base["group_id"],
            splitter=GroupKFold(n_splits=3),
            models=reg_models,
        ),
        ExperimentSpec(
            name="raw_mtt_core_random_regression",
            task="regression",
            dataframe=base,
            features=core_features,
            target="Cell_Viability (%)",
            groups=base["group_id"],
            splitter=KFold(n_splits=3, shuffle=True, random_state=42),
            models=reg_models,
        ),
        ExperimentSpec(
            name="raw_mtt_chemistry_plus_ic50_random_regression",
            task="regression",
            dataframe=base,
            features=leak_features,
            target="Cell_Viability (%)",
            groups=base["group_id"],
            splitter=KFold(n_splits=3, shuffle=True, random_state=42),
            models=reg_models,
        ),
    ]


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    script_results = RESULTS_DIR / "reproduced_experiment_results.csv"
    script_summary = RESULTS_DIR / "reproduced_experiment_summary.json"

    result_rows: list[dict[str, object]] = []

    for spec in build_current_specs():
        if spec.task == "regression":
            result_rows.extend(evaluate_regression(spec))
        else:
            result_rows.extend(evaluate_classification(spec))

    raw_df = prepare_raw_dataset(ROOT / "senp_validation_dataset_final.csv")
    for spec in build_raw_specs(raw_df):
        result_rows.extend(evaluate_regression(spec))

    results_df = pd.DataFrame(result_rows)
    results_df.to_csv(script_results, index=False, encoding="utf-8-sig")

    summary = {
        "current_dataset_rows": int(pd.read_csv(DATA_DIR / "final_input_training_dataset.csv").shape[0]),
        "current_dataset_doi_groups": int(pd.read_csv(DATA_DIR / "final_input_training_dataset.csv")["group_id"].nunique()),
        "raw_dataset_rows": int(raw_df.shape[0]),
        "raw_mtt_rows": int(((raw_df["Test"] == "MTT") & raw_df["Cell_Viability (%)"].notna() & raw_df["Time (hr)"].notna() & raw_df["Concentration (ug/ml)"].notna()).sum()),
        "best_results": results_df.sort_values(
            by=[
                "r2_mean" if "r2_mean" in results_df.columns else "auc_mean"
            ],
            ascending=False,
        ).head(10).fillna("").to_dict(orient="records"),
    }

    with script_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Saved: {script_results}")
    print(f"Saved: {script_summary}")
    print(results_df.to_string(index=False))


if __name__ == "__main__":
    main()
