# 论文与本地模型数据对应关系

核对日期：2026-09-15

## 可以确认对应的部分

通用基准数据对应。根目录的 `d0en01240h1.xlsx` 与 `nano-modle/通用数据集.xlsx` SHA-256 均为 `5cbf141f5d55b9c2b411e1e988ec14dc0255fe6e57b0ce87b2eb1884ce0a333f`，形状均为 4111 行、30 列。Cell viability 在 0--200 范围内的记录为 4102 条，与论文描述一致。论文正文写作 3281 条训练、821 条测试，恰好是 80:20；本地 `General Model Comparison.py` 也使用 `test_size=0.2`。论文中的“7:3”文字与实际数量和代码不一致。

## SeNP 数据差异

论文正文声称 SeNP 数据集有 383 条记录、来自 43 篇文献，并报告 2018 年 157 条、2019 年 96 条、2012 年 44 条等统计量。

本地文件表现为多个版本：

| 文件 | 实际情况 |
|---|---|
| `data/senp/senp_validation_dataset_final.csv` | 677 行；含 Se 的记录 384 行；排除 `Na₂SeO₃` 后为 383 行；核心字段完整的 Se 记录为 371 行；有效 MTT 205 行、MTS 42 行，合计 247 行 |
| `data/senp/final_input_training_dataset.csv` | 247 行、48 个 DOI 组，正是当前训练数据 |
| `data/senp/纳米硒毒性预测验证集数据集.xlsx` | 623 行；按 Se + 核心字段完整 + MTT/MTS 筛选可得到 383 行，但年份和字段分布与论文正文不完全一致 |
| `historical_modeling/` | 保存上述 Excel 对应的旧版建模流程和输出 |

因此，383 这个数字在本地历史 Excel 中可以通过筛选得到，也在当前 CSV 中以“排除 Na₂SeO₃ 后的 Se 行数”出现，但这两种 383 不是同一条记录集合，不能直接当作论文模型输入。

## 模型和结果差异

论文报告 SeNP 增强 XGBoost 为 MAE 7.20%、R² 0.957，Random Forest 为 MAE 7.63%、R² 0.915，并称最优增强组合包含 IC50、元素硒含量、稳定性和 Se 3d 结合能。

当前本地复现实验结果中：

- `raw_mtt_chemistry_plus_ic50_random_regression` 使用 205 行、47 个 DOI 组，XGBoost R²=0.5542、MAE=7.3397%。
- `current_regression_grouped_mtt_negative_charge` 使用 121 行、40 个 DOI 组，Random Forest R²=0.2142，XGBoost R²=-0.0303。
- 当前保存的三个 `.joblib` 模型均使用 18 个基础/工程特征，未包含元素硒含量、长期稳定性、Se 3d 结合能或晶型特征。
- 历史 `feature_selection_31.py` 在本地 Excel 上得到 434 条有效记录，最优组合为 `IC50_uM + Stability_weeks`，3 折 MAE 约 10.60%，不是论文中的 7.60%。

这些结果表明 `nano-modle` 是论文工作的历史来源，但不是论文声称结果的可直接复现包。后续改进应以本报告为基线，先固定数据版本和筛选规则，再重新训练和更新论文数字。
