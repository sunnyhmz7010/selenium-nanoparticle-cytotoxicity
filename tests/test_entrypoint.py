import subprocess
import sys
import json
from pathlib import Path


def test_experiment_entrypoint_is_runnable_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/run_experiments.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "SeNP" in result.stdout


def test_dashboard_distinguishes_computed_results_from_report_targets():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")

    assert 'id="reproduction-status"' in html
    assert 'id="reproduction-table"' in html
    assert "report_reproduction" in script
    assert "computed_mae" in script
    assert "target_mae" in script
    assert "row.computed_mae != null" in script
    assert "value != null && Number.isFinite" in script


def test_dashboard_declares_an_inline_favicon_to_avoid_a_missing_asset_request():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert 'rel="icon" href="data:,' in html


def test_improved_434_entrypoint_is_runnable_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/run_improved_434.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "434" in result.stdout


def test_dashboard_renders_improved_434_metrics_and_effect_intervals():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")

    assert 'id="improved-table"' in html
    assert 'id="improved-best-mae"' in html
    assert "improved_434" in script
    assert "group_bootstrap_ci_low" in script
    assert "group_bootstrap_ci_high" in script


def test_web_dashboard_uses_only_report_and_434_result_contract():
    payload = json.loads(Path("web/data/dashboard.json").read_text(encoding="utf-8"))
    script = Path("web/app.js").read_text(encoding="utf-8")
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert set(payload) == {"report_reproduction", "improved_434"}
    assert payload["improved_434"]["data"]["rows"] == 434
    assert payload["improved_434"]["data"]["publication_groups"] == 24
    assert "analysis_mtt_rows" not in json.dumps(payload)
    assert "renderMetrics(data)" not in script
    assert "renderCoverage(data.coverage" not in script
    assert "renderScatter(data)" not in script
    assert 'id="analysis-rows"' not in html


def test_manifest_dashboard_sync_builds_the_strict_web_payload():
    script = Path("scripts/build_manifest.py").read_text(encoding="utf-8")

    assert "results/dashboard.json" not in script
    assert "results/improved_434/summary.json" in script
    assert "results/report_reproduction/acceptance.json" in script

