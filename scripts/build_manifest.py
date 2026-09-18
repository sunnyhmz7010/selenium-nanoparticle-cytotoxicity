from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKED_DIRS = ("paper", "data", "src", "scripts", "models", "results", "web", "tests", "historical_modeling")
SKIP_NAMES = {"__pycache__", ".pytest_cache"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files() -> list[Path]:
    files: list[Path] = []
    for directory in TRACKED_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not any(part in SKIP_NAMES for part in path.parts):
                files.append(path)
    return sorted(files)


def write_hashes(files: list[Path]) -> Path:
    output = ROOT / "manifest" / "sha256.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "sha256", "bytes"])
        for path in files:
            writer.writerow([path.relative_to(ROOT).as_posix(), sha256(path), path.stat().st_size])
    return output


def write_baseline() -> Path:
    output = ROOT / "manifest" / "repository_baseline.json"
    payload = {
        "repository": "sunnyhmz7010/selenium-nanoparticle-cytotoxicity",
        "source_commit": "2e4b970e35893faf950c03ca11720c0c0e97087e",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_root": "paper/",
        "curated_senp_rows": 383,
        "mtt_analysis_rows": 205,
        "boundaries": [
            "论文文件已集中到 paper/，保留原始 LaTeX 内容。",
            "当前归档不含可逐项复核的分子量、修饰物分类和新合成材料前瞻实验表。",
            "R²=0.957 等论文报告数字不作为当前重建结果。",
        ],
        "tracked_roots": list(TRACKED_DIRS),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def sync_dashboard() -> None:
    acceptance_path = ROOT / "results/report_reproduction/acceptance.json"
    audit_path = ROOT / "data/reproduction/audit.json"
    improved_path = ROOT / "results/improved_434/summary.json"
    target = ROOT / "web" / "data" / "dashboard.json"
    required = (acceptance_path, audit_path, improved_path)
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"缺少网页结果文件: {', '.join(missing)}")

    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    improved = json.loads(improved_path.read_text(encoding="utf-8"))
    payload = {
        "report_reproduction": {
            **acceptance,
            "audit": audit,
            "values_are_computed": True,
            "report_values_are_targets_only": True,
        },
        "improved_434": improved,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write repository baseline and SHA256 artifact manifest.")
    parser.add_argument("--no-dashboard-sync", action="store_true", help="不重新生成 web/data/dashboard.json")
    args = parser.parse_args()
    if not args.no_dashboard_sync:
        sync_dashboard()
    write_baseline()
    files = iter_files()
    write_hashes(files)
    print(json.dumps({"files": len(files), "hashes": "manifest/sha256.csv"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

