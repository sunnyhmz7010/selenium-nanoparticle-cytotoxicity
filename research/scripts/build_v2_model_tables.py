"""核验归档 OOF 指标，生成中文 V2 表格，不重新训练或改写历史结果。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT.parent / "paper/v2/tables"
QA = ROOT.parent / "paper/revision/v2-zh-qa"
MODELS = {"random_forest": "RF", "xgboost": "XGBoost"}
CONFIGS = {"baseline": "基础", "chemistry_no_ic50": "化学增强，不含 IC50", "ic50_assisted": "IC50 辅助"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def recompute_metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    observed = [float(row["observed"]) for row in rows]
    errors = [float(row["prediction"]) - float(row["observed"]) for row in rows]
    observed_mean = mean(observed)
    centered = sum((value - observed_mean) ** 2 for value in observed)
    squared_error = sum(error ** 2 for error in errors)
    return {"mae": mean(abs(error) for error in errors), "rmse": math.sqrt(squared_error / len(rows)),
            "r2": 1 - squared_error / centered}


def main() -> int:
    checks = []
    hashes = {}
    for name, dimensions in (
        ("improved_434", ("feature_set", "model")), ("general_benchmark", ("model",)),
        ("transfer_comparison", ("strategy", "model")), ("dose_time_interaction", ("feature_set", "model")),
    ):
        directory = ROOT / "results" / name
        oof = read_csv(directory / "oof_predictions.csv")
        metrics = read_csv(directory / "metrics.csv")
        for record in metrics:
            subset = [row for row in oof if all(row[dimension] == record[dimension] for dimension in dimensions)]
            if len(subset) != int(record["n_oof"]):
                raise ValueError(f"OOF 数量不符: {name}, {record}")
            if len({row["row_index"] for row in subset}) != len(subset):
                raise ValueError(f"OOF 样本重复: {name}")
            calculated = recompute_metrics(subset)
            for metric, value in calculated.items():
                if not math.isclose(value, float(record[metric]), rel_tol=1e-10, abs_tol=1e-10):
                    raise ValueError(f"归档指标与 OOF 不符: {name}, {metric}")
            checks.append({"result": name, **{dimension: record[dimension] for dimension in dimensions}, "n_oof": len(subset), "status": "passed", **calculated})
        for filename in ("metrics.csv", "oof_predictions.csv", "improvement_analysis.csv"):
            path = directory / filename
            if path.exists():
                hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    performance = [r"\begin{tabular}{llrrr}", r"\toprule", r"模型 & 特征配置 & MAE（百分点） & RMSE（百分点） & $R^2$ \\", r"\midrule"]
    metrics = read_csv(ROOT / "results/improved_434/metrics.csv")
    for config in CONFIGS:
        for model in MODELS:
            record = next(row for row in metrics if row["model"] == model and row["feature_set"] == config)
            performance.append(f"{MODELS[model]} & {CONFIGS[config]} & {float(record['mae']):.2f} & {float(record['rmse']):.2f} & {float(record['r2']):.3f}" + r" \\")
    performance.extend([r"\bottomrule", r"\end{tabular}"])
    write_text(TABLES / "senp-performance.tex", "\n".join(performance) + "\n")

    gains = [r"\begin{tabularx}{\linewidth}{lXrrr}", r"\toprule", r"模型 & 对照 & \shortstack{$\Delta$MAE\\样本等权} & \shortstack{$\Delta$MAE\\文献组等权} & \shortstack{文献组等权\\95\% 区间} \\", r"\midrule"]
    delta_records = []
    for name, key, variants in (
        ("improved_434", "feature_set", {"chemistry_no_ic50": "化学增强", "ic50_assisted": "IC50 辅助"}),
        ("dose_time_interaction", "variant_feature_set", {"dose_time_interaction": "加入剂量—时间交互"}),
        ("transfer_comparison", "strategy", {"general_to_senp": "General→SeNP 迁移"}),
    ):
        directory = ROOT / "results" / name
        oof = read_csv(directory / "oof_predictions.csv")
        for record in read_csv(directory / "improvement_analysis.csv"):
            if record[key] not in variants:
                continue
            feature_column = "strategy" if name == "transfer_comparison" else "feature_set"
            baseline = "senp_only" if name == "transfer_comparison" else "baseline"
            model = record["model"]
            base_rows = {row["row_index"]: row for row in oof if row["model"] == model and row[feature_column] == baseline}
            variant_rows = {row["row_index"]: row for row in oof if row["model"] == model and row[feature_column] == record[key]}
            if base_rows.keys() != variant_rows.keys():
                raise ValueError("配对比较的样本不一致")
            grouped = defaultdict(list)
            deltas = []
            for index, base in base_rows.items():
                variant = variant_rows[index]
                if base["observed"] != variant["observed"] or base["group_id"] != variant["group_id"]:
                    raise ValueError("配对比较的观测值或文献组不一致")
                delta = abs(float(variant["prediction"]) - float(base["observed"])) - abs(float(base["prediction"]) - float(base["observed"]))
                grouped[base["group_id"]].append(delta)
                deltas.append(delta)
            pooled = mean(deltas)
            group_mean = mean(mean(values) for values in grouped.values())
            if not math.isclose(pooled, float(record["pooled_mae_delta"]), abs_tol=1e-10):
                raise ValueError("按样本汇总的 MAE 差值不符")
            if "group_mean_mae_delta" in record and not math.isclose(group_mean, float(record["group_mean_mae_delta"]), abs_tol=1e-10):
                raise ValueError("文献组等权平均的差值不符")
            low, high = float(record["group_bootstrap_ci_low"]), float(record["group_bootstrap_ci_high"])
            gains.append(f"{MODELS[model]} & {variants[record[key]]} & {pooled:+.3f} & {group_mean:+.3f} & $[{low:.3f}, {high:.3f}]$" + r" \\")
            delta_records.append({"result": name, "variant": record[key], "model": model, "pooled_mae_delta": pooled, "group_mean_mae_delta": group_mean, "group_bootstrap_ci_low": low, "group_bootstrap_ci_high": high, "publication_groups": len(grouped)})
    gains.extend([r"\bottomrule", r"\end{tabularx}"])
    write_text(TABLES / "paired-comparisons.tex", "\n".join(gains) + "\n")

    transfer = [r"\begin{tabular}{llrrr}", r"\toprule", r"模型 & 策略 & MAE（百分点） & RMSE（百分点） & $R^2$ \\", r"\midrule"]
    transfer_metrics = read_csv(ROOT / "results/transfer_comparison/metrics.csv")
    for model in MODELS:
        for strategy, label in (("senp_only", "SeNP-only"), ("general_zero_shot", "General zero-shot"), ("general_to_senp", "General→SeNP")):
            record = next(row for row in transfer_metrics if row["model"] == model and row["strategy"] == strategy)
            transfer.append(f"{MODELS[model]} & {label} & {float(record['mae']):.2f} & {float(record['rmse']):.2f} & {float(record['r2']):.3f}" + r" \\")
    transfer.extend([r"\bottomrule", r"\end{tabular}"])
    write_text(TABLES / "transfer-performance.tex", "\n".join(transfer) + "\n")
    write_text(QA / "model-numeric-verification.json", json.dumps({"metric_checks": checks, "paired_comparisons": delta_records, "source_sha256": hashes}, ensure_ascii=False, indent=2) + "\n")
    print(f"Verified {len(checks)} archived model configurations and {len(delta_records)} paired comparisons.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
