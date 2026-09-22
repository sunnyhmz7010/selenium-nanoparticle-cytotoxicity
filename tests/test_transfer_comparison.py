import numpy as np
import pandas as pd

from scripts.run_transfer_comparison import COMMON_FEATURES, fit_strategy, prepare_common_frame


def test_prepare_common_frame_builds_shared_features_and_cleans_missing_markers():
    frame = pd.DataFrame(
        {
            "Diameter (nm)": [10.0],
            "Size_in_Water (nm)": [12.0],
            "Size_in_Medium (nm)": [np.nan],
            "Zeta_in_Water (mV)": ["-"],
            "Zeta_in_Medium (mV)": [np.nan],
            "Time (hr)": [24.0],
            "Concentration (ug/ml)": [2.0],
            "No_of_Cells (cells/well)": [1000.0],
            "Surface_Charge": ["-"],
            "Coat/Functional Group": ["PTR"],
            "Synthesis_Method": ["chemical"],
            "Cell_Type": ["A"],
            "Cell_Tissue": ["B"],
            "Year": [2020.0],
        }
    )

    result = prepare_common_frame(frame)

    assert set(COMMON_FEATURES).issubset(result.columns)
    assert result.loc[0, "size_final"] == 10.0
    assert result.loc[0, "log_time"] == np.log1p(24.0)
    assert result.loc[0, "zeta_missing"] == 1
    assert pd.isna(result.loc[0, "Surface_Charge"])


def test_rf_transfer_keeps_fixed_tree_budget_and_adds_senp_trees():
    general = pd.DataFrame({"numeric": np.arange(8, dtype=float), "category": ["g"] * 8, "target": np.arange(8, dtype=float)})
    senp = pd.DataFrame({"numeric": np.arange(4, dtype=float) + 0.5, "category": ["s"] * 4, "target": np.arange(4, dtype=float) + 1.0})

    preprocessor, model, metadata = fit_strategy(
        general,
        senp,
        ["numeric", "category"],
        target="target",
        model_name="random_forest",
        strategy="general_to_senp",
        total_trees=6,
        seed=42,
    )

    assert len(model.estimators_) == 6
    assert metadata["pretrained_trees"] == 3
    assert metadata["finetune_trees"] == 3
    assert metadata["total_trees"] == 6
    assert metadata["fitted_trees"] == 6
    assert preprocessor is not None


def test_xgboost_transfer_keeps_fixed_booster_budget():
    general = pd.DataFrame({"numeric": np.arange(12, dtype=float), "target": np.arange(12, dtype=float)})
    senp = pd.DataFrame({"numeric": np.arange(6, dtype=float) + 0.5, "target": np.arange(6, dtype=float) + 1.0})

    _, model, metadata = fit_strategy(
        general,
        senp,
        ["numeric"],
        target="target",
        model_name="xgboost",
        strategy="general_to_senp",
        total_trees=6,
        seed=42,
    )

    assert model.get_booster().num_boosted_rounds() == 6
    assert metadata["pretrained_trees"] == 3
    assert metadata["finetune_trees"] == 3
    assert metadata["fitted_trees"] == 6
