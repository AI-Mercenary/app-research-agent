# API Research Agent — 100 Apps

An agent that researches the public API ecosystem of 100 apps across 10 categories and
publishes the findings as a single self-explanatory HTML page.

For each app it answers: **how do you authenticate**, **can a developer self-serve access
or is it gated**, **how good is the API surface**, **does an MCP server already exist**, and
**could a connector be built today** — each backed by an evidence URL.

Live page: `output/index.html` (deployable as a static file, no server or build step).

## What makes this more than a scraper

- **Composio's own MCP is the primary research surface.** The agent calls Composio's hosted
  MCP endpoint over JSON-RPC 2.0 (`COMPOSIO_SEARCH_WEB` for search, `COMPOSIO_SEARCH_FETCH_URL_CONTENT`
  for page text). Fetching server-side also sidesteps vendors that 403 a local scraper.
- **Real tool calling, not JSON-in-prose.** The extraction step forces the model to call
  `save_app_research(...)`; the arguments are validated by a Pydantic schema, so a malformed
  extraction fails loudly instead of silently producing junk.
- **The agent critiques itself.** It reports its own confidence; below 0.6 the graph loops
  back and re-searches with a different query shape (max 2 retries).
- **Honest output.** Apps it could not establish are surfaced as low-confidence rather than
  filled in with plausible guesses.

## Architecture

```
two searches (Composio MCP) -> fetch docs -> extract (forced tool call) -> validate
        ^   docs query + MCP query                                            |
        └────────────── retry with refined query (confidence < 0.6) ──────────┘
                                                                              |
                                                                         save result
```

The two searches are deliberate. Folding "MCP server" into a single docs query made search
return MCP landing pages instead of API reference pages — the extractor then had no evidence
for `access_model` or `api_quality` and returned `unknown`, and GitHub was classified
`no_public_api`. Sources are now labelled `[API DOCS]` / `[MCP SEARCH RESULT]` in the prompt,
and each source gets its own character budget so appending MCP evidence last can't truncate it
away.

- **LangGraph** — state machine with a conditional edge implementing the retry loop.
- **Groq** (`gpt-oss-20b`, rotating to `qwen3.8-27b` / `gpt-oss-120b`) — extraction.
- **Composio MCP** — search + page fetching, with DuckDuckGo and LangSearch as independent
  fallbacks so one provider failing can't kill a 100-app run.
- **Langfuse** — end-to-end tracing (latency, tokens, retries, confidence).

### Rate limiting: the part that actually took the work

Groq's free tier enforces **two** quotas that fail in completely different ways, and
conflating them cost several wasted iterations:

| Quota | Scope | Clears in | Correct response |
|---|---|---|---|
| TPM (tokens/minute) | **per model**; shared by all keys in the org | ~60s | pace, and spread across models |
| TPD (tokens/day) | **per model**, 200k on free tier | hours | rotate to another model |

Two traps, each of which cost a wrong fix before being measured properly:

1. **The `x-ratelimit-*` headers only describe TPM.** When the *daily* budget is exhausted they
   keep reporting a perfectly healthy account, and the only signal is the 429 body. A dead
   daily quota is therefore indistinguishable from a transient per-minute blip unless you read
   the error text.
2. **Scope is per model, not per key.** Adding a second API key changed nothing, because keys on
   the same organisation share the same budgets. Conversely, with one model's remaining TPM
   down to 1243, two other models still reported ~7984 — so the throughput ceiling isn't the
   account, it's whichever model you keep hammering.

The fix is three mechanisms:

- `src/agent/ratelimit.py` — a rolling-window token bucket, **one instance per model**. It
  tracks `(timestamp, tokens)` for the last 60s, reserves an estimate before each call, then
  **settles the reservation against the provider's reported usage** so the window self-corrects
  instead of drifting. Waiting threads re-check every 2s rather than sleeping to the window's
  end, because settled reservations usually free capacity early.
- Least-loaded model selection — each call goes to the model with the most free capacity, so
  the per-model windows are used in parallel instead of serially.
- 429 handling that branches on the error body: a *daily* limit parks that model for an hour and
  fails over immediately (waiting is pointless); a *per-minute* limit obeys Groq's `retry-after`.

Because apps are network-bound, `run.py` researches them in parallel with a shared,
lock-guarded limiter. This also fixed a real bug: running one process per app gave each app a
*private* limiter, so they collectively blew the quota with no effective pacing at all.

## Project layout

```
data/apps.py                     100 target apps in 10 categories
data/results.json                agent output, one entry per app
data/verified.json               human ground truth (independent, see below)
data/results_pass1.json          pre-fix pipeline output, for the accuracy comparison
data/verification_report.json    accuracy scored per pass
data/patterns.json               aggregated stats + headline insights

src/agent/graph.py               LangGraph nodes and retry routing
src/agent/tools.py               Composio MCP search/fetch, Groq tool-call extraction
src/agent/ratelimit.py           rolling-window token limiter
src/agent/prompts.py             extraction contract
src/analysis/patterns.py         clustering into patterns + insights
src/verification/ablation.py     re-runs the pre-fix pipeline to measure improvement
src/verification/verify.py       scores every pass against the ground truth
src/html/generate.py             builds output/index.html

run.py                           entry point
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # fill in the keys below
```

- `GROQ_API_KEY` — https://console.groq.com/keys (free tier)
- `COMPOSIO_API_KEY` — Composio dashboard. Note this project uses the **hosted MCP endpoint**
  with the `x-consumer-api-key` header, not the `composio` PyPI SDK's REST client.
- `LANGSEARCH_API_KEY`, `LANGFUSE_*` — optional fallback search and tracing.

Missing optional keys degrade gracefully; the agent falls back rather than failing.

## Running it

```bash
python run.py                        # research all 100 apps (resumable, 6 workers)
python run.py --workers 1            # serial, for debugging
python run.py --app Slack            # one app
python run.py --retry-bad            # re-run only errored / low-confidence apps

python -m src.analysis.patterns      # cluster results into patterns
python -m src.verification.ablation  # produce pass-1 (pre-fix) results
python -m src.verification.verify    # score all passes vs ground truth
python -m src.html.generate          # build output/index.html
```

## Accuracy methodology

The headline accuracy number is meaningless unless the reference is independent, so:

1. **Ground truth is collected blind.** A human opens each vendor's real documentation for a
   20-app sample spanning all 10 categories and records what it actually says — *without*
   reading the agent's answers first. Anchoring on the agent's output would measure agreement
   rather than correctness.
2. **"Unknown" is not graded.** Where the human could not establish a fact from the docs, the
   field is skipped rather than counted against the agent.
3. **Two passes, one reference.** `ablation.py` reverts the three substantive fixes (ad-redirect
   filtering, Composio server-side fetching, the no-MCP-inference prompt rule) and re-runs the
   same apps. Both passes are scored against the same unchanged ground truth, so the delta is
   attributable to the pipeline changes rather than to a moved goalpost.

See the "Verification & How Accuracy Improved" section of the generated page for the numbers
and every individual mismatch.

## Known limitations

- **`has_mcp: false` means "not found in the fetched text", not "does not exist."** The prompt
  forbids inferring an MCP server, which trades recall for trustworthiness. Treat a false as a
  lead to check.
- **Self-reported confidence cannot catch confident wrongness.** An early bug fed search-ad
  landing pages to the extractor, which then described the wrong company at high confidence.
  Only a human reading the row caught it. The ad-redirect filter fixes that instance; the class
  of error remains possible.
- **Gated apps can't be fully verified from docs.** For sales-gated products the public docs may
  describe an API a developer still can't obtain without a sales conversation.
- Judgement fields (`access_model`, `buildable_today`) are inferred from prose; ambiguous
  pricing pages get misclassified. Individual cases are listed in the verification report.
- Free-tier token budgets cap how many apps can be re-researched per day, so some rows remain
  low-confidence and are reported as such rather than hidden.
