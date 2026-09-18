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

function renderBars(selector, rows) {
  const target = document.querySelector(selector); target.replaceChildren();
  rows.forEach((row) => {
    const line = document.createElement("div"); line.className = "bar-row";
    const label = document.createElement("span"); label.className = "bar-label"; label.textContent = row.label;
    const track = document.createElement("div"); track.className = "bar-track";
    const fill = document.createElement("div"); fill.className = "bar-fill"; fill.style.width = `${Math.max(2, row.value / row.max * 100)}%`; track.append(fill);
    const value = document.createElement("span"); value.className = "bar-value"; value.textContent = fmt(row.value);
    line.append(label, track, value); target.append(line);
  });
}

function renderMetrics(data) {
  const metrics = data.metrics || [];
  document.querySelector("#curated-rows").textContent = data.data.curated_senp_rows;
  document.querySelector("#analysis-rows").textContent = data.data.analysis_mtt_rows;
  document.querySelector("#groups").textContent = data.data.publication_groups;
  const best = metrics.reduce((a, b) => Number(a.mae) < Number(b.mae) ? a : b, metrics[0]);
  document.querySelector("#best-mae").textContent = best ? fmt(best.mae) : "—";
  document.querySelector("#validation").textContent = (data.validation || "").replaceAll("_", " ");
  const tbody = document.querySelector("#metrics-table tbody");
  tbody.replaceChildren(...metrics.map((row) => { const tr = document.createElement("tr"); [featureLabel(row.feature_set), modelLabel(row.model), fmt(row.mae), fmt(row.rmse), fmt(row.r2), row.n_groups].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); }); return tr; }));
  const max = Math.max(...metrics.map((row) => Number(row.mae)));
  renderBars("#metric-chart", metrics.map((row) => ({ label: `${featureLabel(row.feature_set)} · ${modelLabel(row.model)}`, value: Number(row.mae), max })));
}

function renderCoverage(rows) {
  const grouped = new Map();
  rows.filter((row) => row.dataset === "mtt_analysis").forEach((row) => { if (["Elemental_Se_wt", "Stability_weeks", "Binding_Energy_Se3d", "Crystal_Code", "IC50_uM"].includes(row.feature)) grouped.set(row.feature, 100 - Number(row.missing_pct)); });
  renderBars("#coverage-chart", [...grouped.entries()].map(([label, value]) => ({ label, value, max: 100 })));
}

function renderScatter(data) {
  const rows = (data.oof || []).filter((row) => row.feature_set === "baseline" && row.model === "random_forest");
  const svg = document.querySelector("#scatter"); const width = 900, height = 300, pad = 34; svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.replaceChildren(); if (!rows.length) return;
  const values = rows.flatMap((row) => [Number(row.observed), Number(row.prediction)]).filter(Number.isFinite); const lo = Math.min(...values), hi = Math.max(...values), span = Math.max(hi - lo, 1); const x = (v) => pad + ((v - lo) / span) * (width - pad * 2); const y = (v) => height - pad - ((v - lo) / span) * (height - pad * 2);
  const makeLine = (cls, x1, y1, x2, y2) => { const item = document.createElementNS("http://www.w3.org/2000/svg", "line"); item.setAttribute("class", cls); item.setAttribute("x1", x1); item.setAttribute("y1", y1); item.setAttribute("x2", x2); item.setAttribute("y2", y2); return item; };
  svg.append(makeLine("identity", x(lo), y(lo), x(hi), y(hi)), makeLine("axis", pad, height - pad, width - pad, height - pad), makeLine("axis", pad, pad, pad, height - pad));
  rows.forEach((row) => { const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle"); dot.setAttribute("class", "point"); dot.setAttribute("cx", x(Number(row.observed))); dot.setAttribute("cy", y(Number(row.prediction))); dot.setAttribute("r", "2.6"); svg.append(dot); });
}

async function loadDashboard() { try { const response = await fetch(DATA_URL, { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); renderReproduction(data); renderImproved(data); renderMetrics(data); renderCoverage(data.coverage || []); renderScatter(data); } catch (error) { console.error(error); document.querySelector("#error").hidden = false; } }
loadDashboard();
