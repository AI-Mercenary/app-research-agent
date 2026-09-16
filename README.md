# Composio API Research Agent

An autonomous research agent that investigates the public API ecosystem of 100 apps
(auth method, access model, API quality, and whether Composio could build a connector
today) and reports the results as a single HTML dashboard.

## Why

Before Composio builds a connector for an app, someone has to answer: how do you
authenticate with its API, can anyone get access or is it gated behind sales, and how
good/complete is the API surface. Doing this by hand for 100 apps is slow — this project
automates the research with an LLM agent instead.

## Architecture

```
search_web -> scrape_docs -> extract_info -> validate --retry(low confidence)--> search_web
                                                  |
                                              save_result
```

- **LangGraph** — state machine orchestrating the pipeline above, with a bounded retry
  loop (max 2 retries) when the extraction confidence is below 0.6.
- **Groq (Llama 3.3 70B)** — extraction step uses real **tool calling**: the model is
  forced to call `save_app_research(...)` with structured arguments (not free-text JSON
  parsing).
- **DuckDuckGo search + httpx/BeautifulSoup** — find and scrape documentation pages.
- **Langfuse** — every app's run is traced end-to-end (search latency, scrape
  success/failure, LLM tokens/cost, retries, confidence).

## Project layout

```
data/apps.py              100 target apps, grouped into 10 categories
data/results.json         agent output (one entry per app)
data/verified.json        manually-checked ground truth for a 15-20 app sample
data/verification_report.json  accuracy report comparing agent vs. verified
data/patterns.json        aggregated statistics + headline insights

src/agent/                LangGraph nodes, tools (search/scrape/extract), prompts
src/analysis/patterns.py  aggregation + insight generation
src/verification/verify.py  diffs verified.json against results.json
src/html/generate.py      builds output/index.html from the three JSON files

run.py                    entry point: research all 100 apps
output/index.html         the final deliverable page
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY and (optionally) LANGFUSE keys
```

Groq: https://console.groq.com/keys (free tier).
Langfuse: https://cloud.langfuse.com (free tier) — optional, but recommended for
observability. Without keys set, the agent still runs, just untraced.

## Running it

```bash
# Research all 100 apps (resumable — skips apps already in results.json)
python run.py

# Research a single app, for debugging
python run.py --app Slack

# Force re-research everything
python run.py --force

# Aggregate patterns/insights
python -m src.analysis.patterns

# Verification: fill in data/verified.json by hand for ~15-20 apps you spot-checked
# against their real docs, then:
python -m src.verification.verify

# Build the final HTML page
python -m src.html.generate
```

Open `output/index.html` directly, or deploy it (e.g. `vercel output` / drag-and-drop
onto Netlify / GitHub Pages) for a hosted link.

## Accuracy / verification methodology

15-20 apps were manually checked against their real developer documentation
(see `data/verified.json`). `src/verification/verify.py` diffs the agent's
`auth_methods`, `access_model`, `api_quality`, and `buildable_today` fields against
what was actually observed, and reports per-field and overall accuracy — including
where the agent got it wrong and why. See the "Verification Report" section of
`output/index.html` for the numbers.

## Known limitations

- Search/scrape quality depends on how well an app's docs rank in DuckDuckGo results
  and whether the docs site allows scraping (some block bots / require JS rendering).
- The agent reads only the top 3 search results per query — apps with fragmented or
  poorly-indexed docs will show lower confidence and may need a manual look.
- `access_model` and `buildable_today` are judgment calls the LLM makes from prose;
  ambiguous pricing pages can be misclassified (see verification report for examples).
