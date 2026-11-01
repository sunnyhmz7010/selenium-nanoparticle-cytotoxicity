"""验证阈值插值、删失状态和推理输入对实验响应的独立性。"""

import math
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_huvec_external import build_inputs, concentration_scale, read_experiments
from summarize_huvec_for_paper import CONCENTRATIONS, apparent_ic50
from src.data import BASELINE_FEATURES


def points(values):
    return [{"nanoparticle": "example", "time_h": 24, "concentration_reported": c, "viability_percent": v}
            for c, v in zip(CONCENTRATIONS, values)]


class CurveTests(unittest.TestCase):
    def test_log_interpolation_is_geometric_midpoint(self):
        curve = points([100] * 9 + [75, 25, 10, 5])
        result = apparent_ic50(curve)
        self.assertEqual(result["status"], "interpolated")
        self.assertAlmostEqual(result["apparent_ic50_reported_scale"], math.sqrt(64 * 128))
        self.assertNotAlmostEqual(result["apparent_ic50_reported_scale"], (64 + 128) / 2)

    def test_no_crossing_is_censored(self):
        result = apparent_ic50(points([100 - i for i in range(13)]))
        self.assertEqual(result["status"], "not_reached")
        self.assertEqual(result["apparent_ic50_reported_scale"], ">512")

    def test_multiple_crossings_are_unavailable(self):
        result = apparent_ic50(points([100, 100, 100, 40, 80, 40] + [30] * 7))
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["apparent_ic50_reported_scale"], "NA")

    def test_zero_to_positive_crossing_has_no_log_zero_interpolation(self):
        result = apparent_ic50(points([100] + [40] * 12))
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["apparent_ic50_reported_scale"], "NA")

    def test_exact_threshold_keeps_observed_concentration(self):
        result = apparent_ic50(points([100] * 6 + [50] + [25] * 6))
        self.assertEqual(result["status"], "observed_at_50")
        self.assertEqual(result["apparent_ic50_reported_scale"], 8)


class InputTests(unittest.TestCase):
    def test_micromolar_selenium_is_converted_before_model_features(self):
        rows, _ = read_experiments()
        scale = concentration_scale("umol_l", "Se")
        frame = build_inputs(rows, scale, BASELINE_FEATURES)
        self.assertAlmostEqual(scale, 0.078971)
        self.assertAlmostEqual(frame["Concentration (ug/ml)"].max(), 40.433152)
        for dose, transformed in zip(frame["Concentration (ug/ml)"], frame["log_concentration"]):
            self.assertAlmostEqual(transformed, math.log1p(dose))

    def test_molar_dose_without_reference_substance_is_rejected(self):
        with self.assertRaises(ValueError):
            concentration_scale("umol_l")
        with self.assertRaises(ValueError):
            concentration_scale("umol_l", "unknown")

    def test_prediction_inputs_do_not_read_experimental_viability(self):
        rows, _ = read_experiments()
        initial = build_inputs(rows, 1.0, BASELINE_FEATURES)
        without_response = [{k: v for k, v in r.items() if k != "viability_percent"} for r in rows]
        pd.testing.assert_frame_equal(initial, build_inputs(without_response, 1.0, BASELINE_FEATURES))
        self.assertTrue(initial["Year"].isna().all())
        self.assertTrue(initial["No_of_Cells (cells/well)"].isna().all())
        self.assertTrue(initial["Synthesis_Method"].isna().all())

    def test_response_related_feature_is_rejected(self):
        rows, _ = read_experiments()
        with self.assertRaises(ValueError):
            build_inputs(rows, 1.0, BASELINE_FEATURES + ["IC50_uM"])


if __name__ == "__main__":
    unittest.main()
