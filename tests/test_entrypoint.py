import subprocess
import sys


def test_experiment_entrypoint_is_runnable_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/run_experiments.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "SeNP" in result.stdout

