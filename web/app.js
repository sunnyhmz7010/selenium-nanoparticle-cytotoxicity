const DATA_URL = "data/dashboard.json";
const fmt = (value, digits = 2) => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
const featureLabel = (name) => ({ baseline: "baseline", chemistry_no_ic50: "chemistry", ic50_assisted: "IC50 assisted" }[name] || name);
const modelLabel = (name) => ({ random_forest: "Random forest", xgboost: "XGBoost" }[name] || name);

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

function renderImproved(data) {
  const improved = data.improved_434;
  if (!improved) return;
  const metrics = improved.metrics || [];
  const effects = new Map((improved.improvements || []).map((row) => [`${row.model}:${row.feature_set}`, row]));
  document.querySelector("#improved-rows").textContent = improved.data?.rows ?? "—";
  document.querySelector("#improved-groups").textContent = improved.data?.publication_groups ?? "—";
  const bestMae = metrics.reduce((best, row) => !best || Number(row.mae) < Number(best.mae) ? row : best, null);
  const bestR2 = metrics.reduce((best, row) => !best || Number(row.r2) > Number(best.r2) ? row : best, null);
  document.querySelector("#improved-best-mae").textContent = bestMae ? fmt(bestMae.mae) : "—";
  document.querySelector("#improved-best-r2").textContent = bestR2 ? fmt(bestR2.r2, 3) : "—";
  const tbody = document.querySelector("#improved-table tbody");
  tbody.replaceChildren(...metrics.map((row) => {
    const effect = effects.get(`${row.model}:${row.feature_set}`);
    const interval = effect ? `[${fmt(effect.group_bootstrap_ci_low)}, ${fmt(effect.group_bootstrap_ci_high)}]` : "—";
    const values = [modelLabel(row.model), featureLabel(row.feature_set), fmt(row.mae), fmt(row.rmse), fmt(row.r2, 3), effect ? fmt(effect.pooled_mae_delta) : "—", interval];
    const tr = document.createElement("tr");
    values.forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    return tr;
  }));
}

async function loadDashboard() { try { const response = await fetch(DATA_URL, { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); renderReproduction(data); renderImproved(data); } catch (error) { console.error(error); document.querySelector("#error").hidden = false; } }
loadDashboard();
