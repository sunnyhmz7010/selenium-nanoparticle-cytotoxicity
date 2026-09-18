# 434条数据严格改进实验

本目录由 `python scripts/run_improved_434.py` 生成。

- `metrics.csv`：六组模型的汇总OOF指标和置信区间；
- `fold_metrics.csv`：五个外层文献分组折的指标；
- `oof_predictions.csv`：逐样本折外预测；
- `selection_log.csv`：每个外层折内部的特征和参数选择；
- `improvement_analysis.csv`：相对同模型基础特征的配对MAE差值及文献组bootstrap区间；
- `group_assignments.csv`：样本源行号与文献分组；
- `summary.json`：网页使用的结构化摘要。

`pooled_mae_delta < 0` 表示误差下降。只有文献组bootstrap 95%区间完全低于0时，`improved` 才为 `true`。
