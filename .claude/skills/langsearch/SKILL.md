---
name: langsearch
description: Web search with inline full-page-text extraction, using the LangSearch API. Use when you need current information, source URLs, or documentation content from the web — an alternative to WebFetch/WebSearch when you want a single call that returns both search results and full page text.
---

# LangSearch web search

LangSearch is a web search API that returns search results *and* (optionally) full
extracted page text in one call — useful for research/RAG-style tasks where you'd
otherwise search, then fetch each URL separately.

Used in this project as the search fallback in `src/agent/tools.py::search_web()` —
DuckDuckGo is primary (better relevance in practice), LangSearch kicks in when DDGS
is rate-limited or down.

## Auth

Requires `LANGSEARCH_API_KEY` (see `.env`). Get a free key at
https://langsearch.com/api-keys — free tier, no credit card, 5 requests/sec,
daily token allowance resets 00:00 UTC.

## Call

```bash
curl --request POST 'https://api.langsearch.com/v1/web-search' \
  --header "Authorization: Bearer $LANGSEARCH_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{
    "query": "How do AI agents use web search?",
    "count": 5,
    "contents": { "text": { "max_characters": 5000 } }
  }'
```

**Params:**
- `query` (required)
- `count` — 1–50, default 10
- `freshness` — `noLimit` (default) | `oneDay` | `oneWeek` | `oneMonth` | `oneYear` | exact date (`2026-09-12`) | UTC range (`2026-09-01..2026-09-13`)
- `includeDomains` / `excludeDomains` — array of domain strings
- `contents.text.max_characters` — enables full-text mode; omit `contents` (or set `contents.text: false`) for snippet-only results

**Response:** results are in `data.webPages.value[]`, each with `name` (title),
`url`, `text` (full page text, only when `contents.text` was set) or `snippet`,
and optional `datePublished`. Always keep `url` alongside any text you use, for
citation.

## Gotchas (learned building this project)

- **Result relevance can be noticeably worse than DuckDuckGo/Google** for
  keyword-stuffed queries (e.g. `"AppName API documentation authentication
  developer access"` returned off-topic results — genealogy sites, unrelated
  academic papers). Prefer it as a *fallback* or for short, natural-language
  queries, not as the sole primary search for keyword-heavy queries.
- HTTP 429 (rate limit) — back off and reduce request rate rather than
  retrying immediately; limits are token-based (TPM/TPD), not just per-request.
- `contents.text` is fetched server-side by LangSearch's own infrastructure —
  useful when the target site blocks scraping from your own IP/User-Agent,
  since the fetch doesn't originate from you.
