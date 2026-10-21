"""任务 30：直接复算冻结模型的 Tree SHAP，并检查预测重构。"""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/results/huvec_external_20261013_umol_se"
audit = json.loads((SOURCE / "audit.json").read_text(encoding="utf-8"))
model_path = ROOT / "research" / audit["model"]
assert hashlib.sha256(model_path.read_bytes()).hexdigest() == audit["model_sha256"]
assert audit["concentration_unit"] == "umol/L" and audit["molar_concentration_basis"] == "Se"

# 使用已冻结的输入映射：μmol/L Se × 78.971 / 1000 → μg/mL。
# 不拟合新的插补器、编码器或模型；输入不含实测存活率和 IC50。
pipeline = joblib.load(model_path)
X = pd.read_csv(SOURCE / "model_inputs.csv")[audit["features"]]
preprocessor = pipeline.named_steps["preprocess"]
forest = pipeline.named_steps["model"]
Xt = preprocessor.transform(X)
feature_names = preprocessor.get_feature_names_out()
prediction = pipeline.predict(X)

# 背景来自冻结树保存的历史训练路径样本计数。
explainer = shap.TreeExplainer(
    forest, feature_perturbation="tree_path_dependent", model_output="raw"
)
phi = np.asarray(explainer.shap_values(Xt, approximate=False, check_additivity=True))
base_value = float(np.asarray(explainer.expected_value).reshape(-1)[0])
assert phi.shape == Xt.shape and np.isfinite(phi).all()
reconstructed = base_value + phi.sum(axis=1)
np.testing.assert_allclose(reconstructed, prediction, atol=1e-6, rtol=0)

# 只为展示聚合相关派生变量；全模型加和校验仍基于全部 116 个编码列。
group_columns = {
    "Particle size": ["numeric__size_final", "numeric__log_size"],
    "Zeta potential": ["numeric__zeta_final", "numeric__abs_zeta", "numeric__zeta_missing"],
}
group_indices = {group: [list(feature_names).index(name) for name in columns]
                 for group, columns in group_columns.items()}
grouped_phi = np.column_stack([phi[:, indices].sum(axis=1) for indices in group_indices.values()])

if __name__ == "__main__":
    print(json.dumps({"conditions": len(X), "encoded_features": phi.shape[1],
                      "max_additivity_error": float(np.abs(reconstructed - prediction).max()),
                      "model_sha256": audit["model_sha256"]}, indent=2))
