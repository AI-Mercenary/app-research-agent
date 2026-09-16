"""Builds output/index.html — the single-page deliverable.

Reads data/results.json, data/patterns.json, data/verification_report.json
and embeds them as JSON directly into a static HTML page (Tailwind CDN +
Chart.js CDN, no build step, no server needed).

Run: python -m src.html.generate
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_PATH = Path("output/index.html")


def load(name: str, default):
    path = DATA_DIR / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Composio API Research — 100 Apps</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  body { background:#0b0d12; color:#e6e8ec; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
  .card { background:#12151c; border:1px solid #22262f; border-radius:14px; }
  ::-webkit-scrollbar { height:8px; width:8px; }
  ::-webkit-scrollbar-thumb { background:#2a2f3a; border-radius:8px; }
  table th { position: sticky; top:0; background:#12151c; }
  .badge { padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
</style>
</head>
<body class="min-h-screen px-4 py-10 md:px-10">
<div class="max-w-7xl mx-auto space-y-10">

  <header class="space-y-3">
    <div class="text-sm uppercase tracking-widest text-indigo-400 font-semibold">Composio &middot; API Ecosystem Research</div>
    <h1 class="text-3xl md:text-4xl font-bold">100 Apps: API Access, Auth &amp; Buildability</h1>
    <p class="text-gray-400 max-w-3xl">Automated research agent (LangGraph + Groq, tool-calling, web search &amp; scraping,
    traced with Langfuse) investigated the API surface of 100 apps across 10 categories. Below: headline patterns,
    the full dataset, how the agent works, and an honest accuracy report.</p>
  </header>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-4">Headline Patterns</h2>
    <ul id="insights" class="space-y-2 text-gray-200"></ul>
  </section>

  <section class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="card p-6">
      <h3 class="font-semibold mb-3">Auth Method Distribution</h3>
      <canvas id="authChart" height="220"></canvas>
    </div>
    <div class="card p-6">
      <h3 class="font-semibold mb-3">Access Model Distribution</h3>
      <canvas id="accessChart" height="220"></canvas>
    </div>
    <div class="card p-6">
      <h3 class="font-semibold mb-3">Buildable Today</h3>
      <canvas id="buildableChart" height="220"></canvas>
    </div>
    <div class="card p-6">
      <h3 class="font-semibold mb-3">Gated Rate by Category</h3>
      <canvas id="categoryChart" height="220"></canvas>
    </div>
  </section>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-4">How The Agent Works</h2>
    <div class="grid grid-cols-1 md:grid-cols-5 gap-3 text-center text-sm">
      <div class="card p-4"><div class="text-2xl mb-1">🔎</div>Search Web<br><span class="text-gray-500 text-xs">DuckDuckGo query per app</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">📄</div>Scrape Docs<br><span class="text-gray-500 text-xs">httpx + BeautifulSoup, top 3 URLs</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">🧠</div>Extract (Tool Call)<br><span class="text-gray-500 text-xs">Groq Llama-3.3-70B calls save_app_research()</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">✅</div>Validate<br><span class="text-gray-500 text-xs">Confidence &ge; 0.6? else retry (max 2x) with refined query</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">💾</div>Save<br><span class="text-gray-500 text-xs">Incremental write to results.json</span></div>
    </div>
    <p class="text-gray-500 text-xs mt-4">Every step is traced in Langfuse: search latency, scrape success/failure, LLM token usage &amp; cost, retries, and confidence scores.</p>
  </section>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-4">Verification Report</h2>
    <div id="verification" class="text-gray-200"></div>
  </section>

  <section class="card p-6">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
      <h2 class="text-xl font-bold">All 100 Apps</h2>
      <div class="flex gap-2 flex-wrap">
        <input id="search" placeholder="Filter by name..." class="bg-[#0b0d12] border border-[#22262f] rounded px-3 py-1.5 text-sm">
        <select id="categoryFilter" class="bg-[#0b0d12] border border-[#22262f] rounded px-3 py-1.5 text-sm"><option value="">All categories</option></select>
        <select id="buildableFilter" class="bg-[#0b0d12] border border-[#22262f] rounded px-3 py-1.5 text-sm">
          <option value="">All buildability</option>
          <option value="yes_easy">Easy</option>
          <option value="yes_hard">Hard</option>
          <option value="no_blocked">Blocked</option>
        </select>
      </div>
    </div>
    <div class="overflow-auto max-h-[600px] border border-[#22262f] rounded-lg">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-400 border-b border-[#22262f]">
            <th class="p-3">App</th><th class="p-3">Category</th><th class="p-3">Auth</th>
            <th class="p-3">Access</th><th class="p-3">API Quality</th><th class="p-3">Buildable</th>
            <th class="p-3">Confidence</th><th class="p-3">Source</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </section>

  <footer class="text-gray-600 text-xs pb-8">Generated by src/html/generate.py from data/results.json, data/patterns.json, data/verification_report.json.</footer>
</div>

<script>
const RESULTS = __RESULTS_JSON__;
const PATTERNS = __PATTERNS_JSON__;
const VERIFICATION = __VERIFICATION_JSON__;

const rows = Object.values(RESULTS);

// Insights
const insightsEl = document.getElementById('insights');
(PATTERNS.headline_insights || []).forEach(text => {
  const li = document.createElement('li');
  li.className = 'flex gap-2';
  li.innerHTML = `<span class="text-indigo-400">&#9656;</span><span>${text}</span>`;
  insightsEl.appendChild(li);
});

const palette = ['#6366f1','#22d3ee','#f472b6','#facc15','#4ade80','#fb923c','#a78bfa','#f87171'];
function makeChart(id, labels, data, type='doughnut') {
  new Chart(document.getElementById(id), {
    type,
    data: { labels, datasets: [{ data, backgroundColor: palette, borderWidth: 0 }] },
    options: { plugins: { legend: { position: 'bottom', labels: { color: '#cbd5e1', boxWidth: 12, font: {size: 10} } } } }
  });
}
makeChart('authChart', Object.keys(PATTERNS.auth_distribution||{}), Object.values(PATTERNS.auth_distribution||{}));
makeChart('accessChart', Object.keys(PATTERNS.access_distribution||{}), Object.values(PATTERNS.access_distribution||{}));
makeChart('buildableChart', Object.keys(PATTERNS.buildable_distribution||{}), Object.values(PATTERNS.buildable_distribution||{}));

const catAccess = PATTERNS.category_access || {};
const catLabels = Object.keys(catAccess);
const gatedRates = catLabels.map(cat => {
  const dist = catAccess[cat];
  const total = Object.values(dist).reduce((a,b)=>a+b,0) || 1;
  const gated = (dist.paid_plan_required||0) + (dist.sales_contact_required||0);
  return Math.round(100*gated/total);
});
new Chart(document.getElementById('categoryChart'), {
  type: 'bar',
  data: { labels: catLabels, datasets: [{ label: '% gated (paid/sales)', data: gatedRates, backgroundColor: '#f472b6' }] },
  options: {
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: { x: { ticks: { color:'#94a3b8' } }, y: { ticks: { color:'#94a3b8', font:{size:10} } } }
  }
});

// Verification
const verEl = document.getElementById('verification');
if (VERIFICATION && VERIFICATION.total_apps_checked) {
  verEl.innerHTML = `
    <p class="mb-2">Manually checked <strong>${VERIFICATION.total_apps_checked}</strong> apps against their real docs.
    Fully correct: <strong>${VERIFICATION.fully_correct}/${VERIFICATION.total_apps_checked}</strong>
    (<strong>${VERIFICATION.overall_accuracy_pct}%</strong>).</p>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
      ${Object.entries(VERIFICATION.field_accuracy||{}).map(([f,p]) => `
        <div class="card p-3 text-center">
          <div class="text-2xl font-bold">${p}%</div>
          <div class="text-xs text-gray-500">${f}</div>
        </div>`).join('')}
    </div>`;
} else {
  verEl.innerHTML = `<p class="text-gray-500">No verification report yet — run <code>python -m src.verification.verify</code> after filling in data/verified.json.</p>`;
}

// Table
const cats = [...new Set(rows.map(r => r.category))].sort();
const catSelect = document.getElementById('categoryFilter');
cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; catSelect.appendChild(o); });

function badgeColor(val) {
  const map = { yes_easy:'bg-green-900 text-green-300', yes_hard:'bg-yellow-900 text-yellow-300', no_blocked:'bg-red-900 text-red-300' };
  return map[val] || 'bg-gray-800 text-gray-300';
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  const cat = catSelect.value;
  const build = document.getElementById('buildableFilter').value;
  const body = document.getElementById('tableBody');
  body.innerHTML = '';
  rows.filter(r =>
    r.app_name.toLowerCase().includes(q) &&
    (!cat || r.category === cat) &&
    (!build || r.buildable_today === build)
  ).forEach(r => {
    const tr = document.createElement('tr');
    tr.className = 'border-b border-[#1a1d24] hover:bg-[#171a21]';
    tr.innerHTML = `
      <td class="p-3 font-medium">${r.app_name}</td>
      <td class="p-3 text-gray-400">${r.category||''}</td>
      <td class="p-3 text-gray-400">${(r.auth_methods||[]).join(', ')}</td>
      <td class="p-3 text-gray-400">${r.access_model||''}</td>
      <td class="p-3 text-gray-400">${r.api_quality||''}</td>
      <td class="p-3"><span class="badge ${badgeColor(r.buildable_today)}">${r.buildable_today||''}</span></td>
      <td class="p-3 text-gray-400">${r.confidence!==undefined ? (r.confidence*1).toFixed(2) : ''}</td>
      <td class="p-3">${r.source_url ? `<a href="${r.source_url}" target="_blank" class="text-indigo-400 hover:underline">link</a>` : ''}</td>
    `;
    body.appendChild(tr);
  });
}
document.getElementById('search').addEventListener('input', render);
catSelect.addEventListener('change', render);
document.getElementById('buildableFilter').addEventListener('change', render);
render();
</script>
</body>
</html>
"""


def main():
    results = load("results.json", {})
    patterns = load("patterns.json", {})
    verification = load("verification_report.json", {})

    html = (
        TEMPLATE
        .replace("__RESULTS_JSON__", json.dumps(results))
        .replace("__PATTERNS_JSON__", json.dumps(patterns))
        .replace("__VERIFICATION_JSON__", json.dumps(verification))
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
