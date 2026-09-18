# 历史报告复现数据

运行 `python scripts/reproduce_report.py` 后生成：

- `included_rows.csv`：按历史脚本规则纳入的记录，保留Excel源行号；
- `excluded_rows.csv`：未纳入记录及首个排除理由；
- `audit.json`：输入文件哈希、样本数和标签分布与报告目标的差异。

这些文件用于审计，不会把报告目标值写回原始数据。
