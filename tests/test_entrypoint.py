import subprocess
import sys
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

