"""Builds output/index.html — the single-page deliverable.

Reads data/results.json, data/patterns.json, data/verification_report.json
and embeds them as JSON directly into a static HTML page (Tailwind CDN +
Chart.js CDN, no build step, no server needed).

Run: python -m src.html.generate
"""
from __future__ import annotations

import base64
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
<title>Which of these 100 apps can we connect to?</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  body { background:#0b0d12; color:#e6e8ec; font-family:'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif; }
  .card { background:#12151c; border:1px solid #22262f; border-radius:14px; }
  ::-webkit-scrollbar { height:8px; width:8px; }
  ::-webkit-scrollbar-thumb { background:#2a2f3a; border-radius:8px; }
  table th { position: sticky; top:0; background:#12151c; }
  .badge { padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
  .chart-box { position:relative; height:170px; }
  .lede { font-size:1.05rem; line-height:1.75; }
  h2 { letter-spacing:-0.01em; }
</style>
</head>
<body class="min-h-screen px-4 py-10 md:px-10">
<div class="max-w-6xl mx-auto space-y-10">

  <header class="space-y-4">
    <div class="text-xs uppercase tracking-[0.2em] text-indigo-400 font-semibold">API ecosystem research &middot; 100 apps</div>
    <h1 class="text-3xl md:text-[2.6rem] font-bold leading-tight">Which of these 100 apps<br class="hidden md:block"> can we actually connect to?</h1>
    <p class="text-gray-400 lede max-w-3xl">Before anyone builds a connector, someone has to find out how an app's API
    works, whether you can get a key without talking to sales, and whether somebody has already built an MCP server for it.
    That is a day of tab-opening per handful of apps. This is what happened when an agent did it for a hundred.</p>
    <p class="text-gray-500 text-sm max-w-3xl">The short version: most of these apps are easier to reach than expected,
    the interesting constraint has moved, and the agent was confidently wrong often enough that the checking mattered more
    than the research.</p>
    <div id="scorecard" class="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2"></div>
  </header>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-1">What the hundred apps look like</h2>
    <p class="text-gray-500 text-sm mb-4">Every figure below counts only rows the agent could support with a fetched source.</p>
    <ul id="insights" class="space-y-2 text-gray-200"></ul>
  </section>

  <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="card p-4">
      <h3 class="text-sm font-semibold mb-2 text-gray-300">How you authenticate</h3>
      <div class="chart-box"><canvas id="authChart"></canvas></div>
    </div>
    <div class="card p-4">
      <h3 class="text-sm font-semibold mb-2 text-gray-300">How you get access</h3>
      <div class="chart-box"><canvas id="accessChart"></canvas></div>
    </div>
    <div class="card p-4">
      <h3 class="text-sm font-semibold mb-2 text-gray-300">Could we build it today</h3>
      <div class="chart-box"><canvas id="buildableChart"></canvas></div>
    </div>
    <div class="card p-4">
      <h3 class="text-sm font-semibold mb-2 text-gray-300">Gated, by category</h3>
      <div class="chart-box"><canvas id="categoryChart"></canvas></div>
    </div>
  </section>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-1">Categories differ by how the business sells, not by technology</h2>
    <p class="text-gray-400 text-sm mb-4">Messaging tools hand you a token in a minute because they want the integrations.
    Anything sold by a salesperson makes you meet a salesperson first. Read this for where connector work is cheap,
    and where it needs a conversation before a single line of code.</p>
    <div class="overflow-auto border border-[#22262f] rounded-lg">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-gray-400 border-b border-[#22262f]">
          <th class="p-3">Category</th><th class="p-3">Apps</th><th class="p-3">Self-serve</th>
          <th class="p-3">Easy to build</th><th class="p-3">Existing MCP</th><th class="p-3">Dominant auth</th>
        </tr></thead>
        <tbody id="matrixBody" class="text-gray-300"></tbody>
      </table>
    </div>
  </section>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-1">How the research actually ran</h2>
    <p class="text-gray-400 text-sm mb-4">One agent, run once per app, allowed to reject its own work and try again.
    Nothing here is a language model recalling what it knows about Stripe — every field is read off a page that was fetched
    during the run, and every row keeps the link it came from.</p>
    <div class="grid grid-cols-1 md:grid-cols-5 gap-3 text-center text-sm">
      <div class="card p-4"><div class="text-2xl mb-1">🔎</div>Two searches<br><span class="text-gray-500 text-xs"><strong class="text-indigo-300">Composio MCP</strong> <code>COMPOSIO_SEARCH_WEB</code> — one query for API docs, a separate one for MCP, so neither crowds the other out</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">📄</div>Fetch Docs<br><span class="text-gray-500 text-xs"><strong class="text-indigo-300">Composio MCP</strong> <code>SEARCH_FETCH_URL_CONTENT</code> (server-side, beats bot-blocks), else httpx + BeautifulSoup</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">🧠</div>Extract<br><span class="text-gray-500 text-xs">Groq <code>gpt-oss-120b</code> forced tool-call into <code>save_app_research()</code> &rarr; Pydantic-validated</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">✅</div>Self-critique<br><span class="text-gray-500 text-xs">Confidence &ge; 0.6? else re-search with a refined query (max 2 retries)</span></div>
      <div class="card p-4"><div class="text-2xl mb-1">💾</div>Save<br><span class="text-gray-500 text-xs">Incremental write, so the run is resumable after any crash</span></div>
    </div>
    <div class="mt-6 border-t border-[#22262f] pt-5">
      <h3 class="font-semibold mb-1">It really ran, and here is the receipt</h3>
      <p class="text-gray-500 text-xs mb-3">Counted from the run's own telemetry, for the 100 apps in scope. The number worth
      noticing is 222: that many extractions were thrown out by the agent's own confidence check and searched again. The retry
      loop earns its place.</p>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-center text-sm">
        <div class="card p-3"><div class="text-xl font-bold text-indigo-300">3,642</div><div class="text-[11px] text-gray-500">node executions traced</div></div>
        <div class="card p-3"><div class="text-xl font-bold text-indigo-300">607</div><div class="text-[11px] text-gray-500">search + fetch + extract cycles</div></div>
        <div class="card p-3"><div class="text-xl font-bold text-amber-300">222</div><div class="text-[11px] text-gray-500">low-confidence retries fired</div></div>
        <div class="card p-3"><div class="text-xl font-bold text-indigo-300">385</div><div class="text-[11px] text-gray-500">results committed</div></div>
        <div class="card p-3"><div class="text-xl font-bold text-indigo-300">5,107</div><div class="text-[11px] text-gray-500">total events in trace</div></div>
      </div>
      <p class="text-gray-500 text-xs mt-3">The trace covers the research pipeline only. Verification runs as a separate
      script, and its evidence is the three committed files — <code>verified.json</code> (blind ground truth),
      <code>results_pass1.json</code> (pre-fix output) and <code>verification_report.json</code> — which regenerate via
      <code>python -m src.verification.verify</code>.</p>

      <figure class="mt-5">
        <img src="__TRACE_IMG__" alt="Langfuse trace for a single app run, showing the search, fetch, extract, validate and save nodes with their latencies"
             class="rounded-lg border border-[#22262f] w-full">
        <figcaption class="text-gray-500 text-xs mt-2">
          One real run (Xero, 1m13s end to end). The left pane is the graph executing node by node —
          <code>search_web</code> 9.77s &rarr; <code>scrape_docs</code> 15.81s &rarr; <code>extract_info</code> 48.20s &rarr;
          <code>validate</code> &rarr; <code>save_result</code>. The right pane is the extractor's actual input: note
          <code>mcp_results</code> carried separately from the docs, and the content prefixed
          <code>=== [API DOCS] ===</code> — the source labelling that fixed the accuracy bug described above.
        </figcaption>
      </figure>
    </div>

    <p class="text-gray-400 text-sm mt-5">Built as a <strong>LangGraph state machine</strong>: nodes for search / fetch / extract / validate, with a
    conditional edge that loops back to search when the model's own confidence is too low. Composio's hosted MCP endpoint is the
    primary research surface — the agent calls Composio tools over JSON-RPC 2.0 to do the searching and page-fetching, with
    independent fallbacks so one provider outage can't kill a 100-app run. Every step is traced in Langfuse.</p>
  </section>

  <section class="card p-6">
    <h2 class="text-xl font-bold mb-1">The first version was wrong a lot</h2>
    <p class="text-gray-400 text-sm mb-5">Not wrong in a way that looked wrong. It produced clean, plausible, well-formatted
    answers that happened to be false. Each fix below came from opening the real documentation and finding a row that did not match it.</p>
    <div class="overflow-auto border border-[#22262f] rounded-lg mb-6">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-gray-400 border-b border-[#22262f]">
          <th class="p-3">Pass</th><th class="p-3">What was wrong</th><th class="p-3">Fix</th><th class="p-3">Result</th>
        </tr></thead>
        <tbody class="text-gray-300">
          <tr class="border-b border-[#1a1d24]"><td class="p-3 font-medium">Pass 1</td>
            <td class="p-3">Search returned <strong>ad-redirect URLs</strong> (<code>bing.com/aclick</code>). The agent scraped an ad landing page and confidently described <em>the wrong company</em> — Ramp's row contained Datadog's API details.</td>
            <td class="p-3">Filter known ad-redirect hosts before selecting URLs to fetch.</td>
            <td class="p-3 text-red-300">Cross-contaminated rows</td></tr>
          <tr class="border-b border-[#1a1d24]"><td class="p-3 font-medium">Pass 2</td>
            <td class="p-3">Direct scraping was <strong>403-blocked</strong> by several vendors (e.g. Salesforce) — those apps silently produced empty evidence.</td>
            <td class="p-3">Route fetches through Composio's MCP <code>SEARCH_FETCH_URL_CONTENT</code>, which fetches server-side.</td>
            <td class="p-3 text-yellow-300">Recovered blocked docs</td></tr>
          <tr class="border-b border-[#1a1d24]"><td class="p-3 font-medium">Pass 3</td>
            <td class="p-3">The model <strong>inferred MCP servers that didn't exist</strong>, reasoning "this API looks agent-friendly, so it probably has one."</td>
            <td class="p-3">Prompt rule: <code>has_mcp</code> may only be true if the fetched text explicitly names one. No inference allowed.</td>
            <td class="p-3 text-green-300">Removed phantom MCPs</td></tr>
          <tr class="border-b border-[#1a1d24]"><td class="p-3 font-medium">Pass 4</td>
            <td class="p-3">Most of the run failed with <code>RateLimitError</code>. I assumed per-key limits and added a second key — <strong>it changed nothing</strong>.</td>
            <td class="p-3">Read the 429 body instead of the headers: the real blocker was a <em>daily</em> per-model quota, invisible to <code>x-ratelimit-*</code>. Added per-(org, model) token limiters and model rotation.</td>
            <td class="p-3 text-green-300">Run completes</td></tr>
          <tr><td class="p-3 font-medium">Pass 5</td>
            <td class="p-3">The first audit scored <code>auth_methods</code> at 55% but <code>access_model</code> and <code>api_quality</code> at just 25%. Cause: the docs query ended with "MCP server", so search returned <strong>MCP landing pages instead of API reference pages</strong> — GitHub came back as <code>no_public_api</code>. The MCP evidence was then truncated away before the model ever saw it.</td>
            <td class="p-3">Split into two searches (docs vs MCP), label each source in the prompt, and budget characters <em>per source</em> instead of truncating the concatenation.</td>
            <td class="p-3 text-green-300">Fixed both directions</td></tr>
        </tbody>
      </table>
    </div>
    <div id="verification" class="text-gray-200"></div>

    <div class="mt-6 border-t border-[#22262f] pt-5 text-sm text-gray-400 space-y-2">
      <div class="font-semibold text-gray-300">How to read these numbers, including where they flatter and where they punish</div>
      <p><strong class="text-gray-300">Scoring is deliberately unforgiving.</strong> A list of auth methods counts as correct only
      if it matches exactly. The agent saying <code>['oauth2']</code> where the docs list <code>['oauth2','jwt']</code> scores zero,
      not half. That single rule is most of why auth sits so far below the other three fields — the agent usually finds the main
      method and misses a secondary one. Partial credit would roughly double that figure, which is precisely why it isn't used here.</p>
      <p><strong class="text-gray-300">Twenty apps, not a hundred.</strong> Ground truth is expensive because a person has to read
      the docs, so the sample is 20 apps spanning all ten categories. It is enough to show a direction and catch a class of bug.
      It is not a precise estimate of accuracy across all 100, and the confidence interval on a 20-app sample is wide.</p>
      <p><strong class="text-gray-300">Unknowns are excluded, not forgiven.</strong> Where the human could not establish a fact from
      the docs, the field is dropped from scoring rather than counted either way — so the agent is never credited for a question
      nobody could answer.</p>
      <p><strong class="text-gray-300">One caveat on provenance.</strong> An early version of this project researched a different,
      self-assembled list of apps before the real scope arrived. That work was discarded and is not in this dataset, but it does
      appear in the raw telemetry, so trace exports contain more app names than the hundred reported here.</p>
    </div>
  </section>

  <section class="card p-6 border-l-4 border-l-amber-500">
    <h2 class="text-xl font-bold mb-2">What the agent could not do on its own</h2>
    <p class="text-gray-400 text-sm mb-5">It saved days of reading. It did not replace the reading. Six places where the work
    only came out right because a person intervened, and the report would be worth less if it pretended otherwise.</p>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">1. Diagnosing the rate limit</div>
        <span class="text-gray-400">The agent's own error message (<code>RateLimitError</code>) pointed at the wrong cause. A human had to
        query the rate-limit headers directly to discover the budget was account-wide, not per-key. Two rounds of "fixes" before that were wasted effort.</span></div>
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">2. Catching confident wrongness</div>
        <span class="text-gray-400">The ad-redirect bug produced <em>plausible, well-formed</em> output for the wrong company. No confidence score
        caught it — only a human reading a row and thinking "that isn't Ramp." Self-reported confidence cannot detect this class of error.</span></div>
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">3. "Has an MCP" needs a human to qualify</div>
        <span class="text-gray-400">The agent finds a <em>cited</em> MCP server for almost every app — but it counts official servers
        (Salesforce, DealCloud), one-person community repos (Twenty &rarr; <code>jezweb/twenty-mcp</code>) and aggregators
        (fanbasis &rarr; Zapier MCP) as the same thing. They are not. Worse, <strong>Sherlock</strong> matched a .NET library that is
        almost certainly a different product entirely — a name-collision only a human would catch. Read this column as
        "something MCP-shaped exists", then verify provenance yourself.</span></div>
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">4. Ground truth for verification</div>
        <span class="text-gray-400">The accuracy numbers below only mean something because a human opened the real docs for a sample of apps and
        recorded what they actually say. An agent grading its own homework measures consistency, not correctness.</span></div>
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">5. Gated apps can't be fully verified</div>
        <span class="text-gray-400">For sales-gated products, the public docs describe an API a developer may still not be able to obtain. Confirming that
        needs a real sales conversation — beyond the reach of any research pipeline.</span></div>
      <div class="card p-4"><div class="font-semibold text-amber-300 mb-1">6. Rows still marked low-confidence</div>
        <span class="text-gray-400">Apps below the 0.6 threshold are surfaced rather than hidden, precisely so a human knows where to look first.
        They are listed explicitly in the table.</span></div>
    </div>
  </section>

  <section class="card p-6">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold">Every app, with the link it came from</h2>
        <p class="text-gray-500 text-sm mt-1">Search or filter. Hover an MCP cell to see where that server was found.</p>
      </div>
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
            <th class="p-3">Access</th><th class="p-3">Self-serve</th><th class="p-3">API Quality</th>
            <th class="p-3">MCP exists</th><th class="p-3">Buildable</th>
            <th class="p-3">Confidence</th><th class="p-3">Evidence</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </section>

  <footer class="card p-6 mb-8">
    <h2 class="text-lg font-bold mb-2">Source code</h2>
    <p class="text-gray-400 text-sm mb-4 max-w-3xl">The agent, the ground-truth data and the scoring script are all in the
    repository. The accuracy figures on this page regenerate with <code>python -m src.verification.verify</code>, so they can
    be checked rather than taken on trust.</p>
    <a href="https://github.com/AI-Mercenary/app-research-agent" target="_blank" rel="noopener"
       class="inline-flex items-center gap-2 bg-[#1b1f28] hover:bg-[#232834] border border-[#2a2f3a] rounded-lg px-4 py-2.5 text-sm font-medium transition-colors">
      <svg height="18" width="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>
      github.com/AI-Mercenary/app-research-agent
    </a>
    <p class="text-gray-600 text-xs mt-4">Static page — the data is embedded, nothing is fetched at view time.</p>
  </footer>
</div>

<script>
const RESULTS = __RESULTS_JSON__;
const PATTERNS = __PATTERNS_JSON__;
const VERIFICATION = __VERIFICATION_JSON__;

const rows = Object.values(RESULTS);

// Scorecard: the five numbers a reader should leave with
const researched = rows.length;
const withData   = rows.filter(r => !r.error && (r.confidence||0) > 0).length;
const easyCount  = rows.filter(r => r.buildable_today === 'yes_easy').length;
const mcpCount   = rows.filter(r => r.has_mcp === true).length;
const selfServe  = rows.filter(r => r.self_serve === true).length;
const scorecard = [
  ['Apps researched', researched, '10 categories, 10 each'],
  ['Backed by a source', withData, 'every row keeps its link'],
  ['Easy to build today', easyCount, 'key in hand, docs usable'],
  ['MCP already exists', mcpCount, 'though not all are official'],
  ['No sales call needed', selfServe, 'you can start this afternoon'],
];
document.getElementById('scorecard').innerHTML = scorecard.map(([label,val,sub]) => `
  <div class="card p-4">
    <div class="text-2xl font-bold text-indigo-300">${val}</div>
    <div class="text-xs text-gray-300 font-medium mt-0.5">${label}</div>
    <div class="text-[11px] text-gray-500">${sub}</div>
  </div>`).join('');

// Category matrix: the clustered view, computed from rows so it always matches the table
const byCat = {};
rows.forEach(r => {
  const c = r.category || 'Unknown';
  byCat[c] = byCat[c] || { n:0, graded:0, selfServe:0, easy:0, mcp:0, auth:{} };
  const b = byCat[c];
  b.n++;
  if (r.error || !(r.confidence > 0)) return;
  b.graded++;
  if (r.self_serve === true) b.selfServe++;
  if (r.buildable_today === 'yes_easy') b.easy++;
  if (r.has_mcp === true) b.mcp++;
  (r.auth_methods || []).forEach(a => { b.auth[a] = (b.auth[a]||0)+1; });
});
function bar(num, den) {
  if (!den) return '<span class="text-gray-600">no data</span>';
  const pct = Math.round(100*num/den);
  const hue = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500';
  return `<div class="flex items-center gap-2">
    <div class="w-16 h-1.5 bg-[#22262f] rounded"><div class="${hue} h-1.5 rounded" style="width:${pct}%"></div></div>
    <span class="text-xs text-gray-400">${num}/${den}</span></div>`;
}
document.getElementById('matrixBody').innerHTML = Object.entries(byCat)
  .sort((a,b) => (b[1].easy/(b[1].graded||1)) - (a[1].easy/(a[1].graded||1)))
  .map(([cat,b]) => {
    const topAuth = Object.entries(b.auth).sort((x,y)=>y[1]-x[1])[0];
    return `<tr class="border-b border-[#1a1d24]">
      <td class="p-3 font-medium">${cat}</td>
      <td class="p-3 text-gray-500">${b.graded}/${b.n}</td>
      <td class="p-3">${bar(b.selfServe, b.graded)}</td>
      <td class="p-3">${bar(b.easy, b.graded)}</td>
      <td class="p-3">${bar(b.mcp, b.graded)}</td>
      <td class="p-3 text-gray-400 text-xs">${topAuth ? topAuth[0]+' ('+topAuth[1]+')' : '—'}</td>
    </tr>`;
  }).join('');

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
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '58%',
      plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 8, padding: 7, font: {size: 9} } } }
    }
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
const shortCat = c => c.replace(/ and .*/,'').replace('Developer, Infra','Dev/Infra').replace('Productivity, Project Management','Productivity').slice(0,18);
new Chart(document.getElementById('categoryChart'), {
  type: 'bar',
  data: { labels: catLabels.map(shortCat), datasets: [{ data: gatedRates, backgroundColor: '#f472b6', borderRadius: 3, barThickness: 8 }] },
  options: {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { title: items => catLabels[items[0].dataIndex], label: v => v.raw + '% gated' } }
    },
    scales: {
      x: { ticks: { color:'#64748b', font:{size:9}, callback: v => v + '%' }, grid: { color:'#1a1d24' } },
      y: { ticks: { color:'#94a3b8', font:{size:9} }, grid: { display:false } }
    }
  }
});

// Verification
const verEl = document.getElementById('verification');
const passes = (VERIFICATION && VERIFICATION.passes) || {};
const finalPass = passes.final;
if (finalPass) {
  const before = passes.pass1_before_fixes;
  const imp = VERIFICATION.improvement;
  const headline = imp
    ? `<div class="flex items-baseline gap-3 flex-wrap mb-3">
         <span class="text-gray-400 text-sm">Field-level accuracy against human ground truth:</span>
         <span class="text-2xl font-bold text-red-400">${imp.before_pct}%</span>
         <span class="text-gray-500">&rarr;</span>
         <span class="text-3xl font-bold text-green-400">${imp.after_pct}%</span>
         <span class="badge bg-green-900 text-green-300">${imp.delta_pct >= 0 ? '+' : ''}${imp.delta_pct} pts</span>
       </div>`
    : `<div class="text-2xl font-bold text-green-400 mb-2">${finalPass.field_level_accuracy_pct}% field-level accuracy</div>`;

  const mismatches = (finalPass.details || []).filter(d => (d.mismatches || []).length);
  verEl.innerHTML = `
    ${headline}
    <p class="text-gray-400 text-sm mb-4">
      A human opened the real docs for <strong>${finalPass.apps_in_ground_truth}</strong> apps spanning all 10 categories
      and recorded what they actually say — without reading the agent's answers first.
      ${finalPass.fields_correct}/${finalPass.fields_graded} fields correct;
      ${finalPass.apps_fully_correct}/${finalPass.apps_scored} apps correct on every field.
      Fields the human could not establish are excluded rather than counted in the agent's favour.
    </p>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
      ${Object.entries(finalPass.field_accuracy || {}).map(([f,p]) => `
        <div class="card p-3 text-center">
          <div class="text-2xl font-bold ${p >= 80 ? 'text-green-400' : p >= 60 ? 'text-yellow-400' : 'text-red-400'}">${p === null ? '—' : p + '%'}</div>
          <div class="text-xs text-gray-500">${f}</div>
          ${before && before.field_accuracy && before.field_accuracy[f] !== null && before.field_accuracy[f] !== undefined
            ? `<div class="text-[11px] text-gray-600 mt-1">was ${before.field_accuracy[f]}%</div>` : ''}
        </div>`).join('')}
    </div>
    ${mismatches.length ? `
      <div class="text-sm">
        <div class="font-semibold mb-2 text-gray-300">Every remaining disagreement, listed in full:</div>
        <div class="space-y-1">
        ${mismatches.map(d => d.mismatches.map(m => `
          <div class="flex flex-wrap gap-2 items-baseline border-b border-[#1a1d24] py-1">
            <span class="font-medium">${d.app}</span>
            <span class="text-gray-500 text-xs">${m.field}</span>
            <span class="text-red-300 text-xs">agent: ${JSON.stringify(m.agent_said)}</span>
            <span class="text-green-300 text-xs">docs: ${JSON.stringify(m.actually)}</span>
          </div>`).join('')).join('')}
        </div>
      </div>` : '<p class="text-green-400 text-sm">No disagreements on any graded field.</p>'}`;
} else {
  verEl.innerHTML = `<p class="text-gray-500">No verification report yet — run <code>python -m src.verification.verify</code>.</p>`;
}

// Table
const cats = [...new Set(rows.map(r => r.category))].sort();
const catSelect = document.getElementById('categoryFilter');
cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; catSelect.appendChild(o); });

function badgeColor(val) {
  const map = { yes_easy:'bg-green-900 text-green-300', yes_hard:'bg-yellow-900 text-yellow-300', no_blocked:'bg-red-900 text-red-300' };
  return map[val] || 'bg-gray-800 text-gray-300';
}
function boolBadge(val, yes, no) {
  if (val === true)  return `<span class="badge bg-green-900 text-green-300">${yes}</span>`;
  if (val === false) return `<span class="badge bg-gray-800 text-gray-400">${no}</span>`;
  return '<span class="text-gray-600">—</span>';
}
function confColor(c) {
  if (c === undefined || c === null) return 'text-gray-600';
  if (c >= 0.8) return 'text-green-400';
  if (c >= 0.6) return 'text-gray-300';
  return 'text-red-400 font-semibold';
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
      <td class="p-3">${boolBadge(r.self_serve, 'self-serve', 'gated')}</td>
      <td class="p-3 text-gray-400">${r.api_quality||''}</td>
      <td class="p-3" title="${(r.mcp_notes||'').replace(/"/g,'&quot;')}">${boolBadge(r.has_mcp, 'yes', 'none found')}</td>
      <td class="p-3"><span class="badge ${badgeColor(r.buildable_today)}">${r.buildable_today||''}</span></td>
      <td class="p-3 ${confColor(r.confidence)}">${r.confidence!==undefined && r.confidence!==null ? (r.confidence*1).toFixed(2) : '—'}</td>
      <td class="p-3">${r.source_url ? `<a href="${r.source_url}" target="_blank" class="text-indigo-400 hover:underline">link</a>` : '<span class="text-gray-600">none</span>'}</td>
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


def trace_image_data_uri() -> str:
    """Inline the Langfuse screenshot so the page stays one self-contained file."""
    path = OUTPUT_PATH.parent / "langfuse_trace.png"
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def main():
    results = load("results.json", {})
    patterns = load("patterns.json", {})
    verification = load("verification_report.json", {})

    html = (
        TEMPLATE
        .replace("__RESULTS_JSON__", json.dumps(results))
        .replace("__PATTERNS_JSON__", json.dumps(patterns))
        .replace("__VERIFICATION_JSON__", json.dumps(verification))
        .replace("__TRACE_IMG__", trace_image_data_uri())
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
