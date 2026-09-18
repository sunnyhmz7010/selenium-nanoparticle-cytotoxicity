# 报告定向复现 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从仓库现有数据实际计算并审计报告中的310样本模型结果，生成模型、预测、验收和网页数据产物。

**Architecture:** 在现有 `src` 数据与评估模块旁增加独立的历史报告复现模块，保持当前论文嵌套交叉验证不受影响。复现入口先生成带来源行号的数据审计表，再训练模型并从预测生成指标，最后由同一汇总 JSON 驱动网页。

**Tech Stack:** Python、pandas、scikit-learn、XGBoost、PyTorch（仅在可用时运行 TabTransformer）、pytest、原生 HTML/CSS/JavaScript

**Spec:** `docs/superpowers/specs/2026-09-18-report-exact-reproduction-design.md`

## Global Constraints

- 所有展示指标必须从逐样本预测重新计算。
- 目标值只用于验收，不能回填为计算值。
- 固定随机种子；同一环境重复运行必须得到相同文件内容。
- 保留源行号、纳入/排除理由、输入文件哈希和软件版本。
- 不改变现有论文嵌套交叉验证结果文件的语义。

---

### Task 1: 数据审计与310样本候选集

**Files:**
- Create: `src/report_reproduction.py`
- Create: `tests/test_report_reproduction.py`
- Create: `scripts/reproduce_report.py`

**Interfaces:**
- Produces: `load_report_source(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]`
- Produces: `assign_folds(frame: pd.DataFrame, seed: int = 42) -> pd.Series`

- [ ] **Step 1: Write the failing test**：构造含材料、端点和缺失值的最小表，断言筛选结果、源行号、排除理由和稳定折号。
- [ ] **Step 2: Run test to verify it fails**：运行 `pytest tests/test_report_reproduction.py -q`，确认因模块缺失失败。
- [ ] **Step 3: Write minimal implementation**：实现字段别名、历史清洗规则、特征派生、数据指纹和稳定分折。
- [ ] **Step 4: Run test to verify it passes**：运行该测试文件并确认通过。
- [ ] **Step 5: Commit**：提交数据审计入口和测试。

### Task 2: 模型评估与指标来源约束

**Files:**
- Modify: `src/report_reproduction.py`
- Modify: `tests/test_report_reproduction.py`

**Interfaces:**
- Consumes: `assign_folds`
- Produces: `evaluate_predictions(predictions: pd.DataFrame) -> pd.DataFrame`
- Produces: `compare_with_report(computed: pd.DataFrame) -> dict`

- [ ] **Step 1: Write the failing test**：断言指标由 `y_true/y_pred` 计算，目标值只有比较字段，缺预测时拒绝生成 computed 指标。
- [ ] **Step 2: Run test to verify it fails**：确认测试因接口缺失失败。
- [ ] **Step 3: Write minimal implementation**：实现基础/增强特征定义、RF/XGBoost训练、折叠预测、MAE/R²和差异状态。
- [ ] **Step 4: Run test to verify it passes**：运行测试并确认通过。
- [ ] **Step 5: Commit**：提交模型评估实现和测试。

### Task 3: 31种组合、产物和可重复入口

**Files:**
- Modify: `src/report_reproduction.py`
- Modify: `scripts/reproduce_report.py`
- Modify: `tests/test_report_reproduction.py`
- Create: `data/reproduction/README.md`

**Interfaces:**
- Produces: `search_feature_combinations(frame: pd.DataFrame) -> pd.DataFrame`
- Produces: `run_reproduction(input_path: Path, output_root: Path) -> dict`

- [ ] **Step 1: Write the failing test**：断言5个候选特征产生31组唯一组合，运行摘要包含输入哈希、行数、状态和产物路径。
- [ ] **Step 2: Run test to verify it fails**：确认组合搜索接口缺失。
- [ ] **Step 3: Write minimal implementation**：写出清洗表、排除表、折号、预测、指标、组合结果、模型和摘要 JSON。
- [ ] **Step 4: Run test to verify it passes**：运行测试并确认通过。
- [ ] **Step 5: Commit**：提交完整可重复入口。

### Task 4: 网页展示实际复现状态

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_entrypoint.py`

**Interfaces:**
- Consumes: `web/data/dashboard.json`
- Produces: 页面中的样本口径、报告目标、计算结果、差值和复现状态。

- [ ] **Step 1: Write the failing test**：断言网页脚本读取复现状态字段并区分目标值与计算值。
- [ ] **Step 2: Run test to verify it fails**：确认当前网页没有该字段。
- [ ] **Step 3: Write minimal implementation**：在现有简洁布局中替换相关结果卡片和状态图，不增加描述性副标题。
- [ ] **Step 4: Run test to verify it passes**：运行入口测试并在本地浏览器检查页面。
- [ ] **Step 5: Commit**：提交网页与测试。

### Task 5: 完整运行与验收

**Files:**
- Modify: `README.md`
- Modify: `manifest/sha256.csv`
- Create/Modify: `data/reproduction/*`
- Create/Modify: `results/report_reproduction/*`
- Create/Modify: `models/report_reproduction/*`
- Modify: `web/data/dashboard.json`

**Interfaces:**
- Consumes: `scripts/reproduce_report.py`
- Produces: 可审计的完整仓库产物。

- [ ] **Step 1: Run full reproduction**：执行 `python scripts/reproduce_report.py`。
- [ ] **Step 2: Inspect acceptance report**：逐项核对310行、六组指标、31种组合和 `exact/partial` 状态。
- [ ] **Step 3: Update documentation and manifest**：写明运行命令、环境和当前证据边界，刷新哈希清单。
- [ ] **Step 4: Run full verification**：执行 `pytest -q`、复现命令二次运行和 `git diff --check`。
- [ ] **Step 5: Commit**：仅提交本计划相关文件，提交说明使用中文。
