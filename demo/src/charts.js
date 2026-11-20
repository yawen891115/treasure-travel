// Bar charts for the offline ranking results (numbers from results/ranking_results.json).

export const RANKING_RESULTS = [
  { label: "Popularity only", val: 0.0216, ndcg: 0.0311, coverage: 0.0059 },
  { label: "Baseline: popularity, rating, TF-IDF", val: 0.0282, ndcg: 0.0334, coverage: 0.1443 },
  { label: "Baseline + ALS", val: 0.0477, ndcg: 0.0441, coverage: 0.2466 },
  { label: "Baseline + residualized ALS", val: 0.048, ndcg: 0.0436, coverage: 0.2385, selected: true },
  { label: "ALS alone", val: 0.0465, ndcg: 0.044, coverage: 0.2534 },
];

const SVG = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}) => {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};

function showTip(tip, value, label, x, y) {
  tip.textContent = "";
  const strong = document.createElement("strong");
  strong.textContent = value;
  tip.append(strong, document.createTextNode(label));
  tip.hidden = false;
  const r = tip.getBoundingClientRect();
  tip.style.left = `${Math.min(window.innerWidth - r.width - 8, Math.max(8, x + 12))}px`;
  tip.style.top = `${Math.max(8, y - r.height - 10)}px`;
}

export function barChart(fig, { title, subtitle, rows, key, format, ticks, max }) {
  fig.textContent = "";
  const cap = document.createElement("figcaption");
  const t = document.createElement("strong"); t.textContent = title;
  const s = document.createElement("span"); s.textContent = subtitle;
  cap.append(t, s);
  fig.append(cap);

  const width = Math.max(300, Math.round(fig.clientWidth || 480));
  const labelW = Math.round(Math.min(220, width * 0.44));
  const valueW = 50;
  const plotW = width - labelW - valueW;
  const barH = 18, gap = 14, top = 6, axisH = 26;
  const plotH = rows.length * (barH + gap) - gap;
  const height = top + plotH + axisH;
  const x = (v) => labelW + (plotW * v) / max;

  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": `${title}. ${subtitle}` });
  for (const tk of ticks) {
    svg.append(svgEl("line", { x1: x(tk), x2: x(tk), y1: top - 4, y2: top + plotH + 4, stroke: "#d7dee2", "stroke-width": 1 }));
    const label = svgEl("text", { x: x(tk), y: top + plotH + 20, "text-anchor": "middle", class: "tick" });
    label.textContent = format(tk, true);
    svg.append(label);
  }
  const tip = document.getElementById("tooltip");
  rows.forEach((row, i) => {
    const y = top + i * (barH + gap);
    const v = row[key];
    const cat = svgEl("text", { x: labelW - 10, y: y + barH / 2 + 4, "text-anchor": "end", class: `cat${row.selected ? " sel" : ""}` });
    cat.textContent = row.label;
    svg.append(cat);

    const x0 = labelW, x1 = Math.max(x0 + 1, x(v));
    const r = Math.min(4, (x1 - x0) / 2);
    const d = `M${x0},${y} H${x1 - r} Q${x1},${y} ${x1},${y + r} V${y + barH - r} Q${x1},${y + barH} ${x1 - r},${y + barH} H${x0} Z`;
    const g = svgEl("g", { class: "bar", tabindex: 0, role: "img", "aria-label": `${row.label}: ${format(v)}` });
    g.append(svgEl("rect", { x: x0, y: y - gap / 2, width: plotW + valueW, height: barH + gap, fill: "transparent" }));
    g.append(svgEl("path", { d, fill: row.selected ? "#b4372a" : "#b8c2c8" }));
    const val = svgEl("text", { x: x1 + 6, y: y + barH / 2 + 4, class: "val" });
    val.textContent = format(v);
    g.append(val);
    const text = row.selected ? `${row.label} (chosen on validation)` : row.label;
    g.addEventListener("pointermove", (e) => showTip(tip, format(v), text, e.clientX, e.clientY));
    g.addEventListener("pointerleave", () => { tip.hidden = true; });
    g.addEventListener("focus", () => { const b = g.getBoundingClientRect(); showTip(tip, format(v), text, b.left + b.width / 2, b.top); });
    g.addEventListener("blur", () => { tip.hidden = true; });
    svg.append(g);
  });
  fig.append(svg);
}

export function resultsTable(container) {
  container.textContent = "";
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  for (const h of ["Model", "Validation NDCG@5", "Test NDCG@5", "Catalog coverage@5"]) {
    const th = document.createElement("th"); th.textContent = h; head.append(th);
  }
  const body = table.createTBody();
  for (const r of RANKING_RESULTS) {
    const tr = body.insertRow();
    for (const v of [r.label + (r.selected ? " (chosen)" : ""), r.val.toFixed(4), r.ndcg.toFixed(4), `${(r.coverage * 100).toFixed(1)}%`]) {
      tr.insertCell().textContent = v;
    }
  }
  container.append(table);
}

export function renderCharts() {
  const ndcg = document.getElementById("chart-ndcg");
  const cov = document.getElementById("chart-coverage");
  if (!ndcg || !cov) return;
  barChart(ndcg, {
    title: "Test NDCG@5",
    subtitle: "Ranking quality on each reviewer's held-out reviews. Higher is better.",
    rows: RANKING_RESULTS, key: "ndcg", max: 0.05, ticks: [0, 0.01, 0.02, 0.03, 0.04, 0.05],
    format: (v, tick) => (tick && v === 0 ? "0" : v.toFixed(tick ? 2 : 4)),
  });
  barChart(cov, {
    title: "Catalog coverage@5",
    subtitle: "Share of all places that appear in someone's top 5.",
    rows: RANKING_RESULTS, key: "coverage", max: 0.3, ticks: [0, 0.1, 0.2, 0.3],
    format: (v, tick) => `${(v * 100).toFixed(tick ? 0 : 1)}%`,
  });
  resultsTable(document.getElementById("results-table"));
}
