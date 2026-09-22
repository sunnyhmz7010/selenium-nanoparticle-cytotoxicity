# Reproducible Models and Results Dashboard Design

## Goal

将论文仓库整理为一个可复现实验仓库，基于当前可核验的 SeNP 数据重建无 IC50 主模型、IC50 辅助模型和 publication-grouped nested cross-validation 结果，并提供一个简洁的静态结果可视化页面。

## Scope

- 保留论文 LaTeX 源文件和现有 GitHub 版本。
- 新增数据、代码、模型、结果、元数据和网页目录。
- 主模型不得把 IC50 作为输入；IC50 仅作为单独的 response-correlated 辅助基准。
- 不伪造论文报告的 383 条 / R²=0.957 结果，也不生成不存在的 9 种新材料实验结果。
- 当前归档没有分子量、修饰物分类和新材料输入表，因此只预留 schema 和输入模板，不把它们标记为已完成结果。

## Architecture

`src/` 提供数据清洗、特征构造、分组嵌套交叉验证和结果导出；`scripts/` 提供可直接运行的入口；`models/` 保存验证后训练的 pipeline；`results/` 保存机器可读指标、OOF 预测和覆盖率；`web/` 是零构建依赖的静态页面，读取由 `scripts/build_manifest.py` 生成的 `web/data/dashboard.json`。论文源文件集中在 `paper/`，数据与模型通过 manifest 和 SHA256 清单追踪。

## Data Contracts

输入数据固定为归档中的 `senp_validation_dataset_final.csv`。SeNP 行通过 `Material` 包含 Se 且排除 `Na2SeO3/Na₂SeO₃` 筛选；回归分析使用 `Test=MTT`、目标、时间和浓度均非空的行。publication group 使用 DOI，缺失 DOI 时回退到 Article_ID。特征组合固定为：

- `baseline`: 当前可获得的物理化学、暴露、生物和实验字段；
- `chemistry_no_ic50`: baseline 加元素硒含量、长期稳定性、Se 3d 和晶型；
- `ic50_assisted`: chemistry_no_ic50 加 IC50，仅作辅助基准。

所有插补、编码、标准化和特征选择必须在训练折内完成。外层 grouped CV 只用于最终评估，内层 grouped CV 用于选择特征和模型参数。最终指标使用外层 pooled out-of-fold predictions 计算，并同时保存每折指标。

## Dashboard Design

网页展示报告复现、General backbone 独立基准、SeNP 严格验证、剂量-时间交互消融和 General→SeNP 迁移对照。页面使用少量高对比颜色、紧凑网格和明确单位；所有结果表和指标均由 `web/data/dashboard.json` 驱动，不把实验数值硬编码在页面中。

## Validation

- Python 编译检查和数据契约检查。
- 重跑实验入口，确认结果 JSON、OOF CSV、模型文件和 SHA256 清单生成。
- 加载每个 joblib pipeline 并执行一条预测。
- 使用本地静态服务器和 Playwright 检查桌面与移动视口，确认页面非空、图表可见、无水平溢出。
- LaTeX 论文工作流保持可运行；若环境无法完整编译，报告实际阻塞原因。
