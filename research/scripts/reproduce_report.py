from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.report_reproduction import (  # noqa: E402
    CANDIDATE_FEATURES,
    compare_with_report,
    engineer_historical_features,
    load_report_source,
    run_tree_model,
    search_feature_combinations,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按历史报告口径审计并复现纳米硒模型")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "senp" / "纳米硒毒性预测验证集数据集.xlsx",
    )
    parser.add_argument("--audit-only", action="store_true", help="只生成数据审计，不训练模型")
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    included, excluded, audit = load_report_source(args.input)
    engineered = engineer_historical_features(included)
    audit.update(
        {
            "report_target_rows": 310,
            "row_count_matches_report": len(engineered) == 310,
            "observed_target_min": float(engineered["Cell_Viability"].min()),
            "observed_target_max": float(engineered["Cell_Viability"].max()),
            "observed_target_mean": float(engineered["Cell_Viability"].mean()),
            "observed_target_sd": float(engineered["Cell_Viability"].std()),
            "report_target_min": 3.2,
            "report_target_max": 103.0,
            "report_target_mean": 57.3,
            "report_target_sd": 21.4,
            "source_alignment": "matched" if len(engineered) == 310 else "different",
        }
    )

    data_dir = ROOT / "data" / "reproduction"
    result_dir = ROOT / "results" / "report_reproduction"
    model_dir = ROOT / "models" / "report_reproduction"
    for directory in (data_dir, result_dir, model_dir):
        directory.mkdir(parents=True, exist_ok=True)
    included.to_csv(data_dir / "included_rows.csv", index=False)
    excluded.to_csv(data_dir / "excluded_rows.csv", index=False)
    write_json(data_dir / "audit.json", audit)

    if args.audit_only:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 0

    predictions: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for model_name in ("random_forest", "xgboost"):
        for feature_set, added in (("baseline", []), ("enhanced", CANDIDATE_FEATURES)):
            model_predictions, summary, bundle = run_tree_model(engineered, model_name, feature_set, added)
            predictions.append(model_predictions)
            summaries.append(summary)
            joblib.dump(bundle, model_dir / f"{model_name}_{feature_set}.joblib")

    prediction_frame = pd.concat(predictions, ignore_index=True)
    summary_frame = pd.DataFrame(summaries)
    combinations = search_feature_combinations(engineered)
    prediction_frame.to_csv(result_dir / "oof_predictions.csv", index=False)
    summary_frame.to_csv(result_dir / "metrics.csv", index=False)
    combinations.to_csv(result_dir / "feature_combinations.csv", index=False)

    comparison = compare_with_report(summary_frame)
    comparison["data_status"] = "exact" if audit["row_count_matches_report"] else "different"
    comparison["unavailable_models"] = {
        "tabtransformer": "报告对应训练代码和依赖版本未保存，不能以其他网络替代",
    }
    comparison["environment"] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    write_json(result_dir / "acceptance.json", comparison)

    print(json.dumps({"audit": audit, "acceptance": comparison}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
