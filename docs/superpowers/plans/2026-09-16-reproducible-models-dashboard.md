# Reproducible Models and Results Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将论文仓库升级为可复现的 SeNP 建模仓库，并交付一个由真实实验结果驱动的简洁可视化网页。

**Architecture:** 使用 Python 脚本完成数据筛选、特征处理、publication-grouped nested CV、OOF 预测、模型保存和 manifest 生成；静态网页只读取导出的 JSON/CSV，不引入后端服务。论文源文件集中到 `paper/`，可复现实验材料集中到 `data/`、`src/`、`scripts/`、`models/` 和 `results/`。

**Tech Stack:** Python 3.11+, pandas, scikit-learn, XGBoost, joblib, HTML/CSS/JavaScript, Plotly CDN, GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-09-16-reproducible-models-dashboard-design.md`

## Global Constraints

- 以 `sunnyhmz7010/selenium-nanoparticle-cytotoxicity` 的 `main` 分支为仓库基线。
- 主模型不得使用 IC50；IC50 模型必须单独标记为辅助基准。
- 不把无法由当前归档逐项复现的论文数字标记为当前结果。
- 不虚构分子量、修饰物分类、9 种新材料或 1296 个前瞻实验结果。
- 所有缺失值处理、编码、调参和特征选择必须位于训练折内。
- 代码、文档和网页默认使用 UTF-8/LF；提交信息使用中文。

---

### Task 1: 整理论文与基线材料

**Files:**
- Create: `paper/github_snapshot/` and copy current LaTeX source tree
- Create: `data/raw/senp_validation_dataset_final.csv`
- Create: `manifest/repository_baseline.json`
- Create: `manifest/sha256.csv`
- Modify: `README.md`

**Interfaces:**
- Consumes: remote repository at commit `2e4b970e35893faf950c03ca11720c0c0e97087e`
- Produces: stable repository layout and baseline manifest for all later tasks

- [ ] **Step 1: Copy the existing manuscript and archive data without changing content.**
- [ ] **Step 2: Record source commit, source paths, row counts and known paper/data discrepancies in JSON and Markdown.**
- [ ] **Step 3: Generate SHA256 entries for every tracked data/model/result artifact.**
- [ ] **Step 4: Check that the copied LaTeX snapshot matches the source commit.**

### Task 2: Implement leakage-safe data preparation

**Files:**
- Create: `src/__init__.py`
- Create: `src/data.py`
- Create: `src/schema.py`
- Create: `tests/test_data_contract.py`

**Interfaces:**
- `load_senp_dataset(path: Path) -> pandas.DataFrame`
- `build_analysis_subset(frame: pandas.DataFrame) -> pandas.DataFrame`
- `feature_groups() -> dict[str, list[str]]`
- `make_group_ids(frame: pandas.DataFrame) -> pandas.Series`

- [ ] **Step 1: Write tests for the Se filter, MTT/core target filter and DOI fallback.**
- [ ] **Step 2: Run the focused tests and confirm the missing implementation fails.**
- [ ] **Step 3: Implement explicit NA normalization and numeric parsing.**
- [ ] **Step 4: Implement derived size, zeta and log exposure features without fitting data-dependent values globally.**
- [ ] **Step 5: Add tests for required columns, row counts and feature availability.**
- [ ] **Step 6: Run the focused tests and confirm they pass.**

### Task 3: Implement grouped nested CV and model export

**Files:**
- Create: `src/evaluation.py`
- Create: `src/models.py`
- Create: `scripts/run_experiments.py`
- Create: `tests/test_evaluation.py`

**Interfaces:**
- `run_nested_grouped_cv(frame, feature_set, target, groups, seed=42) -> EvaluationBundle`
- `fit_final_pipeline(frame, feature_set, target, seed=42) -> sklearn.pipeline.Pipeline`
- `write_evaluation_bundle(bundle, output_dir) -> None`

- [ ] **Step 1: Write tests proving that grouped folds never share a DOI.**
- [ ] **Step 2: Write tests proving that OOF predictions cover every outer-test row exactly once.**
- [ ] **Step 3: Implement fold-local preprocessing with one-hot categorical encoding and median/mode imputation.**
- [ ] **Step 4: Implement inner grouped CV for the fixed feature-set comparison and model parameter selection.**
- [ ] **Step 5: Implement pooled OOF MAE, RMSE, R², fold summaries and bootstrap confidence intervals.**
- [ ] **Step 6: Run baseline, chemistry-without-IC50 and IC50-assisted experiments for Random Forest and XGBoost.**
- [ ] **Step 7: Save final pipelines only after evaluation and write feature metadata.**

### Task 4: Export results and reproducibility metadata

**Files:**
- Create: `results/metrics.json`
- Create: `results/fold_metrics.csv`
- Create: `results/oof_predictions.csv`
- Create: `results/feature_coverage.csv`
- Create: `web/data/dashboard.json`
- Create: `models/*.joblib`
- Create: `models/model_metadata.json`
- Create: `scripts/build_manifest.py`

**Interfaces:**
- `web/data/dashboard.json` contains dataset counts, model metrics, ablation/transfer comparisons and relative artifact paths.

- [ ] **Step 1: Generate feature availability counts before imputation and record the denominator for each feature set.**
- [ ] **Step 2: Export OOF predictions with DOI group, fold, observed value and prediction.**
- [ ] **Step 3: Export model metrics with explicit `validation=publication_grouped_nested_cv`.**
- [ ] **Step 4: Load every saved pipeline and execute a smoke-test prediction.**
- [ ] **Step 5: Generate and verify the SHA256 manifest.**

### Task 5: Build the static results webpage

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Create: `web/data/dashboard.json`
- Create: `web/README.md`

**Interfaces:**
- `index.html` loads `data/dashboard.json` and renders report reproduction, the General benchmark, strict SeNP validation, dose-time ablation and transfer comparison results.
- The page has no backend dependency and runs from a local static server.

- [ ] **Step 1: Add the compact dashboard layout with metric cards, model comparison chart, coverage chart and OOF scatter plot.**
- [ ] **Step 2: Add responsive layout rules for desktop and mobile widths.**
- [ ] **Step 3: Load data asynchronously and render an explicit empty/error state.**
- [ ] **Step 4: Keep visible copy limited to labels, units, model names and validation status.**
- [ ] **Step 5: Run a local static server and verify the page with Playwright at desktop and mobile viewports.**

### Task 6: Update repository documentation and CI

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/main.yml`
- Create: `requirements.txt`
- Create: `LICENSE`
- Create: `SECURITY.md`

**Interfaces:**
- README commands reproduce the result bundle and serve the dashboard.
- CI checks Python syntax, data contracts and dashboard artifact presence.

- [ ] **Step 1: Document the repository structure, data boundaries and exact reproduction commands.**
- [ ] **Step 2: Add a Python verification job without changing the existing LaTeX publish behavior.**
- [ ] **Step 3: Add a Pages-compatible static artifact path for `web/`.**
- [ ] **Step 4: Run CI-equivalent commands locally.**

### Task 7: Verify, commit and push

**Files:**
- Verify all files from Tasks 1-6

- [ ] **Step 1: Run the complete Python test and syntax suite.**
- [ ] **Step 2: Run the experiment pipeline from a clean output directory.**
- [ ] **Step 3: Verify model loading, manifest hashes and dashboard data paths.**
- [ ] **Step 4: Run Playwright checks for desktop and mobile screenshots.**
- [ ] **Step 5: Review `git diff --stat`, `git status` and tracked file list for unrelated artifacts.**
- [ ] **Step 6: Commit with a Chinese message and push to `origin/main`.**
- [ ] **Step 7: Verify the remote commit and GitHub tree after push.**
