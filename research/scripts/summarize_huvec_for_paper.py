"""从归档报告值生成中文 V2 的描述性结果，不换算浓度或推定重复次数。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import correlation, mean


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/prospective/experimental_huvec_dose_time.csv"
OUTPUT = ROOT / "results/huvec_exploratory"
TABLES = ROOT.parent / "paper/v2/tables"
TIMES = (24, 48, 72)
CONCENTRATIONS = (0, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
MATERIALS = (
    "CS-SeNPs", "Glucose-SeNPs", "LET-SeNPs", "PAH-SeNPs", "PEG-SeNPs",
    "PEI-SeNPs", "PVP-SeNPs", "Sucrose-SeNPs", "TW80-SeNPs",
)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def average_ranks(values: list[float]) -> list[float]:
    """并列值使用平均秩，避免把材料数误当作 351 条独立记录。"""
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        stop = start + 1
        while stop < len(ordered) and ordered[stop][1] == ordered[start][1]:
            stop += 1
        rank = (start + 1 + stop) / 2
        for index, _ in ordered[start:stop]:
            ranks[index] = rank
        start = stop
    return ranks


def apparent_ic50(points: list[dict[str, object]]) -> dict[str, object]:
    positive = [point for point in points if point["concentration_reported"] > 0]
    downward = [
        (left, right) for left, right in zip(positive, positive[1:])
        if left["viability_percent"] > 50 >= right["viability_percent"]
    ]
    upward = [
        (left, right) for left, right in zip(positive, positive[1:])
        if left["viability_percent"] < 50 <= right["viability_percent"]
    ]
    result = {
        "nanoparticle": points[0]["nanoparticle"], "time_h": points[0]["time_h"],
        "status": "", "apparent_ic50_reported_scale": "",
        "lower_concentration": "", "upper_concentration": "",
        "lower_viability_percent": "", "upper_viability_percent": "",
        "downward_crossings": len(downward), "upward_crossings": len(upward),
    }
    exact = [point for point in positive if point["viability_percent"] == 50]
    if len(exact) == 1 and not upward and len(downward) <= 1:
        result.update(status="observed_at_50", apparent_ic50_reported_scale=exact[0]["concentration_reported"])
    elif len(downward) == 1 and not upward:
        left, right = downward[0]
        fraction = (50 - left["viability_percent"]) / (right["viability_percent"] - left["viability_percent"])
        log_value = math.log10(left["concentration_reported"]) + fraction * (
            math.log10(right["concentration_reported"]) - math.log10(left["concentration_reported"])
        )
        result.update(
            status="interpolated", apparent_ic50_reported_scale=10 ** log_value,
            lower_concentration=left["concentration_reported"], upper_concentration=right["concentration_reported"],
            lower_viability_percent=left["viability_percent"], upper_viability_percent=right["viability_percent"],
        )
    elif all(point["viability_percent"] > 50 for point in positive):
        result.update(status="not_reached", apparent_ic50_reported_scale=">512")
    else:
        # 多次穿越或没有正浓度括区时，保留不可确定状态，不选择有利的穿越点。
        result.update(status="ambiguous", apparent_ic50_reported_scale="NA")
    return result


def main() -> int:
    source_audit = json.loads((SOURCE.parent / "audit.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != source_audit["csv_sha256"]:
        raise ValueError("原始 CSV 的 SHA256 与归档审计不符，请先核实数据版本")
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if any(value == "" for value in raw.values()):
            raise ValueError("输入记录存在缺失字段")
        row = dict(raw)
        for column in ("size_nm", "zeta_mV", "concentration_reported", "viability_percent"):
            row[column] = float(raw[column])
            if not math.isfinite(row[column]):
                raise ValueError(f"输入存在非有限数值: {column}")
        row["time_h"] = int(raw["time_h"])
        rows.append(row)
    expected = {(material, time, concentration) for material in MATERIALS for time in TIMES for concentration in CONCENTRATIONS}
    observed = [(row["nanoparticle"], row["time_h"], row["concentration_reported"]) for row in rows]
    if len(rows) != 351 or len(set(observed)) != len(rows) or set(observed) != expected:
        raise ValueError("数据不满足 9 种材料 × 3 时间 × 13 浓度的完整唯一覆盖")
    if {row["cell_type"] for row in rows} != {"HUVEC"}:
        raise ValueError("细胞类型与归档约定不符")

    curves: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        curves[(row["nanoparticle"], row["time_h"])].append(row)
    for points in curves.values():
        points.sort(key=lambda point: point["concentration_reported"])
    ic50 = [apparent_ic50(curves[(material, time)]) for material in MATERIALS for time in TIMES]
    high_dose: list[dict[str, object]] = []
    for material in MATERIALS:
        material_rows = [row for row in rows if row["nanoparticle"] == material]
        descriptors = {(row["size_nm"], row["zeta_mV"]) for row in material_rows}
        if len(descriptors) != 1:
            raise ValueError(f"材料 {material} 的描述符不是固定报告值")
        size, zeta = next(iter(descriptors))
        record = {"nanoparticle": material, "size_nm": size, "zeta_mV": zeta}
        for time in TIMES:
            record[f"viability_{time}h_percent"] = curves[(material, time)][-1]["viability_percent"]
        record["decrease_24h_to_72h_percentage_points"] = record["viability_24h_percent"] - record["viability_72h_percent"]
        high_dose.append(record)
    high_dose.sort(key=lambda record: record["viability_72h_percent"])
    time_summary = [
        {"time_h": time, "concentration_reported": 512, "n_materials": 9,
         "mean_viability_percent": mean(record[f"viability_{time}h_percent"] for record in high_dose)}
        for time in TIMES
    ]
    correlations = []
    for time in TIMES:
        response = [record[f"viability_{time}h_percent"] for record in high_dose]
        for descriptor in ("size_nm", "zeta_mV"):
            rho = correlation(average_ranks([record[descriptor] for record in high_dose]), average_ranks(response))
            correlations.append({"time_h": time, "concentration_reported": 512, "descriptor": descriptor, "n_materials": 9, "spearman_rho": rho})
    finite_ic50 = [record["apparent_ic50_reported_scale"] for record in ic50 if record["status"] in {"interpolated", "observed_at_50"}]
    summary = {
        "source_csv": SOURCE.relative_to(ROOT).as_posix(), "source_csv_sha256": digest,
        "source_xlsx_sha256": source_audit["source_sha256"], "rows": len(rows),
        "materials": list(MATERIALS), "times_h": list(TIMES), "concentrations_reported": list(CONCENTRATIONS),
        "cell_type": "HUVEC", "curves": len(curves), "points_per_curve": 13,
        "concentration_unit_status": source_audit["concentration_unit_status"],
        "replicate_status": source_audit["replicate_status"],
        "viability_min": min(row["viability_percent"] for row in rows),
        "viability_max": max(row["viability_percent"] for row in rows),
        "values_above_100": sum(row["viability_percent"] > 100 for row in rows),
        "zero_concentration_all_100": all(row["viability_percent"] == 100 for row in rows if row["concentration_reported"] == 0),
        "ic50_interpolated_curves": sum(record["status"] == "interpolated" for record in ic50),
        "ic50_not_reached_curves": sum(record["status"] == "not_reached" for record in ic50),
        "ic50_ambiguous_curves": sum(record["status"] == "ambiguous" for record in ic50),
        "ic50_finite_range_reported_scale": [min(finite_ic50), max(finite_ic50)],
        "curves_with_local_viability_increases": sum(any(right["viability_percent"] > left["viability_percent"] for left, right in zip(points, points[1:])) for points in curves.values()),
        "mean_decrease_24h_to_72h_percentage_points": time_summary[0]["mean_viability_percent"] - time_summary[2]["mean_viability_percent"],
        "high_dose_time_summary": time_summary, "high_dose_materials": high_dose, "correlations": correlations,
        "ic50_method": "相邻正浓度点在 log10 浓度尺度插值；多次穿越不强行估值；未达到 50% 标记 >512；不拟合置信区间",
    }
    write_csv(OUTPUT / "material_comparison_512.csv", high_dose)
    write_csv(OUTPUT / "apparent_ic50.csv", ic50)
    write_csv(OUTPUT / "time_summary_512.csv", time_summary)
    write_csv(OUTPUT / "descriptor_correlations.csv", correlations)
    write_text(OUTPUT / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

    material_lines = [r"\begin{tabular}{lrrrrr}", r"\toprule", r"材料 & 粒径（nm） & Zeta（mV） & 24 h（\%） & 48 h（\%） & 72 h（\%） \\", r"\midrule"]
    for record in high_dose:
        values = [record["size_nm"], record["zeta_mV"]] + [record[f"viability_{time}h_percent"] for time in TIMES]
        material_lines.append(str(record["nanoparticle"]) + " & " + " & ".join(f"{value:.2f}" for value in values) + r" \\")
    material_lines.extend([r"\bottomrule", r"\end{tabular}"])
    write_text(TABLES / "huvec-high-dose.tex", "\n".join(material_lines) + "\n")
    ic50_lookup = {(record["nanoparticle"], record["time_h"]): record for record in ic50}
    ic50_lines = [r"\begin{tabular}{lrrr}", r"\toprule", r"材料 & 24 h & 48 h & 72 h \\", r"\midrule"]
    for material in MATERIALS:
        values = []
        for time in TIMES:
            value = ic50_lookup[(material, time)]["apparent_ic50_reported_scale"]
            values.append(f"{value:.2f}" if isinstance(value, float) else f"${value}$")
        ic50_lines.append(material + " & " + " & ".join(values) + r" \\")
    ic50_lines.extend([r"\bottomrule", r"\end{tabular}"])
    write_text(TABLES / "huvec-apparent-ic50.tex", "\n".join(ic50_lines) + "\n")
    print(json.dumps({key: summary[key] for key in ("rows", "curves", "viability_min", "viability_max", "values_above_100", "ic50_interpolated_curves", "ic50_not_reached_curves", "ic50_ambiguous_curves", "ic50_finite_range_reported_scale", "mean_decrease_24h_to_72h_percentage_points")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
