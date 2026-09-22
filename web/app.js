const DATA_URL = "data/dashboard.json";
const fmt = (value, digits = 2) => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
const featureLabel = (name) => ({ baseline: "baseline", chemistry_no_ic50: "chemistry", ic50_assisted: "IC50 assisted", dose_time_interaction: "dose × time" }[name] || name);
const modelLabel = (name) => ({ random_forest: "Random forest", xgboost: "XGBoost" }[name] || name);
const strategyLabel = (name) => ({ senp_only: "SeNP-only", general_zero_shot: "General zero-shot", general_to_senp: "General → SeNP" }[name] || name);
const rangeLabel = (low, high) => Number.isFinite(Number(low)) && Number.isFinite(Number(high)) ? `[${fmt(low)}, ${fmt(high)}]` : "—";
const intervalLabel = (row) => {
  if (!row) return "—";
  const low = Number(row.group_bootstrap_ci_low);
  const high = Number(row.group_bootstrap_ci_high);
  return Number.isFinite(low) && Number.isFinite(high) ? `[${fmt(low)}, ${fmt(high)}]` : "—";
};

function renderReproduction(data) {
  const reproduction = data.report_reproduction;
  if (!reproduction) return;
  const audit = reproduction.audit || {};
  const rows = reproduction.models || [];
  document.querySelector("#reproduction-status").textContent = reproduction.status === "exact" ? "一致" : "未对齐";
  document.querySelector("#reproduction-rows").textContent = audit.included_rows ?? "—";
  document.querySelector("#report-rows").textContent = audit.report_target_rows ?? "—";
  const computed = rows.filter((row) => row.computed_mae != null).map((row) => Number(row.computed_mae)).filter(Number.isFinite);
  document.querySelector("#reproduction-best-mae").textContent = computed.length ? fmt(Math.min(...computed)) : "—";
  const tbody = document.querySelector("#reproduction-table tbody");
  tbody.replaceChildren(...rows.map((row) => {
    const tr = document.createElement("tr");
    [modelLabel(row.model), featureLabel(row.feature_set), fmt(row.computed_mae), fmt(row.target_mae), fmt(row.computed_r2, 3), fmt(row.target_r2, 3), row.status].forEach((value) => {
      const td = document.createElement("td"); td.textContent = value; tr.append(td);
    });
    return tr;
  }));
}

function renderGeneral(data) {
  const general = data.general_benchmark;
  if (!general) return;
  const metrics = general.metrics || [];
  document.querySelector("#general-rows").textContent = general.data?.rows ?? "—";
  document.querySelector("#general-groups").textContent = general.data?.publication_groups ?? "—";
  const bestMae = metrics.filter((row) => Number.isFinite(Number(row.mae))).reduce((best, row) => !best || Number(row.mae) < Number(best.mae) ? row : best, null);
  const bestR2 = metrics.filter((row) => Number.isFinite(Number(row.r2))).reduce((best, row) => !best || Number(row.r2) > Number(best.r2) ? row : best, null);
  document.querySelector("#general-best-mae").textContent = bestMae ? fmt(bestMae.mae) : "—";
  document.querySelector("#general-best-r2").textContent = bestR2 ? fmt(bestR2.r2, 3) : "—";
  document.querySelector("#general-summary").textContent = `${general.data?.rows ?? "—"} 条通用数据 · ${general.data?.publication_groups ?? "—"} 个文献组 · ${general.design?.outer_splits ?? "—"} 折外层分组验证`;
  const tbody = document.querySelector("#general-table tbody");
  tbody.replaceChildren(...metrics.map((row) => {
    const values = [modelLabel(row.model), fmt(row.mae), fmt(row.rmse), fmt(row.r2, 3), rangeLabel(row.mae_ci_low, row.mae_ci_high), rangeLabel(row.rmse_ci_low, row.rmse_ci_high)];
    const tr = document.createElement("tr");
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    return tr;
  }));
}

function renderImproved(data) {
  const improved = data.improved_434;
  if (!improved) return;
  const metrics = improved.metrics || [];
  const effects = new Map((improved.improvements || []).map((row) => [`${row.model}:${row.feature_set}`, row]));
  document.querySelector("#validation").textContent = `${improved.data?.rows ?? "—"} 条 · ${improved.data?.publication_groups ?? "—"} 个文献组`;
  document.querySelector("#improved-rows").textContent = improved.data?.rows ?? "—";
  document.querySelector("#improved-groups").textContent = improved.data?.publication_groups ?? "—";
  const bestMae = metrics.filter((row) => Number.isFinite(Number(row.mae))).reduce((best, row) => !best || Number(row.mae) < Number(best.mae) ? row : best, null);
  const bestR2 = metrics.filter((row) => Number.isFinite(Number(row.r2))).reduce((best, row) => !best || Number(row.r2) > Number(best.r2) ? row : best, null);
  document.querySelector("#improved-best-mae").textContent = bestMae ? fmt(bestMae.mae) : "—";
  document.querySelector("#improved-best-r2").textContent = bestR2 ? fmt(bestR2.r2, 3) : "—";
  const tbody = document.querySelector("#improved-table tbody");
  tbody.replaceChildren(...metrics.map((row) => {
    const effect = effects.get(`${row.model}:${row.feature_set}`);
    const interval = intervalLabel(effect);
    const values = [modelLabel(row.model), featureLabel(row.feature_set), fmt(row.mae), fmt(row.rmse), fmt(row.r2, 3), effect ? fmt(effect.pooled_mae_delta) : "—", interval];
    const tr = document.createElement("tr");
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    return tr;
  }));
}

function renderDoseTime(data) {
  const doseTime = data.dose_time_interaction;
  if (!doseTime) return;
  const metrics = doseTime.metrics || [];
  const effects = new Map((doseTime.improvements || []).map((row) => [row.model, row]));
  const improved = (doseTime.improvements || []).some((row) => row.improved);
  document.querySelector("#dose-time-summary").textContent = `${doseTime.data?.rows ?? "—"} 条 · ${doseTime.data?.publication_groups ?? "—"} 个文献组 · ${improved ? "观察到改善" : "未观察到改善"}`;
  const tbody = document.querySelector("#dose-time-table tbody");
  tbody.replaceChildren(...metrics.map((row) => {
    const effect = row.feature_set === "dose_time_interaction" ? effects.get(row.model) : null;
    const values = [modelLabel(row.model), featureLabel(row.feature_set), fmt(row.mae), fmt(row.rmse), fmt(row.r2, 3), effect ? fmt(effect.pooled_mae_delta) : "—", intervalLabel(effect)];
    const tr = document.createElement("tr");
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    return tr;
  }));
}

function renderTransfer(data) {
  const transfer = data.transfer_comparison;
  if (!transfer) return;
  const metrics = transfer.metrics || [];
  const effects = new Map((transfer.improvements || []).map((row) => [`${row.model}:${row.strategy}`, row]));
  const transferMetrics = metrics.filter((row) => row.strategy === "general_to_senp");
  const hasImprovement = (transfer.improvements || []).some((row) => row.strategy === "general_to_senp" && row.improved);
  document.querySelector("#transfer-general-rows").textContent = transfer.data?.general_rows ?? "—";
  document.querySelector("#transfer-senp-rows").textContent = transfer.data?.senp_rows ?? "—";
  const best = transferMetrics.filter((row) => Number.isFinite(Number(row.mae))).reduce((bestRow, row) => !bestRow || Number(row.mae) < Number(bestRow.mae) ? row : bestRow, null);
  document.querySelector("#transfer-best-mae").textContent = best ? fmt(best.mae) : "—";
  document.querySelector("#transfer-verdict").textContent = hasImprovement ? "有改善" : "无稳定收益";
  document.querySelector("#transfer-summary").textContent = `${transfer.data?.general_rows ?? "—"} 条通用数据 → ${transfer.data?.senp_rows ?? "—"} 条 SeNP 数据 · ${transfer.data?.senp_publication_groups ?? "—"} 个文献组 · ${hasImprovement ? "观察到改善" : "未观察到稳定迁移收益"}`;
  const tbody = document.querySelector("#transfer-table tbody");
  tbody.replaceChildren(...metrics.map((row) => {
    const effect = row.strategy === "senp_only" ? null : effects.get(`${row.model}:${row.strategy}`);
    const values = [modelLabel(row.model), strategyLabel(row.strategy), fmt(row.mae), fmt(row.rmse), fmt(row.r2, 3), effect ? fmt(effect.pooled_mae_delta) : "—", intervalLabel(effect)];
    const tr = document.createElement("tr");
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    return tr;
  }));
}

async function loadDashboard() { try { const response = await fetch(DATA_URL, { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); renderReproduction(data); renderGeneral(data); renderImproved(data); renderDoseTime(data); renderTransfer(data); } catch (error) { console.error(error); document.querySelector("#error").hidden = false; } }
loadDashboard();
