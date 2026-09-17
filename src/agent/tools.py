"""The three tools the agent uses: web search, scraping, and LLM extraction.

Extraction uses real Groq tool-calling (the LLM calls a `save_app_research`
function with structured arguments) rather than plain JSON-mode text, so the
project demonstrates actual tool-calling orchestration.
"""
from __future__ import annotations

import json
import os
import time

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from groq import Groq, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agent.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_user_prompt
from src.agent.ratelimit import estimate_tokens, get_limiter
from src.agent.state import AppResearch

_groq_clients: dict[str, Groq] = {}


def get_groq_client(key_env: str = "GROQ_API_KEY") -> Groq:
    if key_env not in _groq_clients:
        _groq_clients[key_env] = Groq(api_key=os.environ[key_env])
    return _groq_clients[key_env]


# Composio's SDK REST client (composio.tools.execute) rejects this account's key
# with 401 on both production/staging — but the same key works against Composio's
# hosted MCP endpoint via the `x-consumer-api-key` header, which is what this
# account's dashboard ("Connect") actually provisions keys for. So we speak MCP
# (JSON-RPC 2.0 over Streamable HTTP) directly instead of using the `composio`
# PyPI package's REST client.
COMPOSIO_MCP_URL = "https://connect.composio.dev/mcp"


def _composio_mcp_execute(tool_slug: str, arguments: dict) -> dict:
    """Call one Composio tool via the MCP endpoint's COMPOSIO_MULTI_EXECUTE_TOOL
    meta-tool. Returns the tool's own `data` payload (already unwrapped)."""
    key = os.environ["COMPOSIO_API_KEY"]
    resp = httpx.post(
        COMPOSIO_MCP_URL,
        headers={
            "x-consumer-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
                "arguments": {
                    "tools": [{"tool_slug": tool_slug, "arguments": arguments}],
                    "thought": f"API research agent: {tool_slug}",
                },
            },
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data_lines = [l for l in resp.text.splitlines() if l.startswith("data:")]
    envelope = json.loads(data_lines[0][len("data:"):].strip())
    if "error" in envelope and envelope["error"]:
        raise RuntimeError(f"MCP error: {envelope['error']}")
    text = envelope["result"]["content"][0]["text"]
    outer = json.loads(text)
    results = outer.get("data", {}).get("results") or []
    if not results or not results[0].get("response", {}).get("successful"):
        raise RuntimeError(f"Composio tool {tool_slug} failed: {outer}")
    return results[0]["response"]["data"]


def _search_composio(query: str, max_results: int) -> list[dict]:
    """Search via Composio's own MCP (COMPOSIO_SEARCH_WEB, Exa-backed, returns
    a synthesized answer + citations)."""
    data = _composio_mcp_execute("COMPOSIO_SEARCH_WEB", {"query": query})
    citations = data.get("citations") or []
    return [
        {"title": c.get("title") or c.get("url", ""), "href": c.get("url", ""), "body": ""}
        for c in citations[:max_results]
        if c.get("url")
    ]


def _fetch_composio(url: str, max_characters: int = 6000) -> str:
    """Fetch a URL's clean text via Composio's own MCP (COMPOSIO_SEARCH_FETCH_URL_CONTENT)."""
    data = _composio_mcp_execute(
        "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
        {"urls": [url], "text": True, "max_characters": max_characters},
    )
    pages = data.get("results") or []
    if pages:
        return (pages[0].get("text") or "")[:max_characters]
    return ""


LANGSEARCH_URL = "https://api.langsearch.com/v1/web-search"


def _search_langsearch(query: str, max_results: int) -> list[dict]:
    api_key = os.environ["LANGSEARCH_API_KEY"]
    resp = httpx.post(
        LANGSEARCH_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"query": query, "count": max_results, "contents": {"text": {"max_characters": 6000}}},
        timeout=15.0,
    )
    resp.raise_for_status()
    pages = resp.json().get("data", {}).get("webPages", {}).get("value", []) or []
    return [
        {
            "title": p.get("name", ""),
            "href": p.get("url", ""),
            "body": p.get("snippet", ""),
            "text": p.get("text", ""),
        }
        for p in pages
    ]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=20))
def _search_ddgs(query: str, max_results: int) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Web search. Returns [{title, href, body}, ...].

    Composio's own SDK (COMPOSIO_SEARCH_WEB) is primary when COMPOSIO_API_KEY is
    set — this is the agent actually using Composio's product, not just calling
    a generic search API. Falls back to DuckDuckGo, then LangSearch, if Composio
    is unavailable/unauthorized/rate-limited, so a missing/invalid Composio key
    degrades gracefully instead of failing the whole pipeline.
    """
    if os.environ.get("COMPOSIO_API_KEY"):
        try:
            results = _search_composio(query, max_results)
            if results:
                return results
        except Exception:
            pass
    try:
        return _search_ddgs(query, max_results)
    except Exception:
        if os.environ.get("LANGSEARCH_API_KEY"):
            return _search_langsearch(query, max_results)
        raise


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _scrape_url_httpx(url: str, timeout: float = 10.0) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ComposioResearchBot/1.0)"}
    resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "svg"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:6000]


def scrape_url(url: str, timeout: float = 10.0) -> str:
    """Fetch a URL and return cleaned visible text (truncated).

    Composio's SDK (COMPOSIO_SEARCH_FETCH_URL_CONTENT) is tried first when
    COMPOSIO_API_KEY is set — it fetches server-side on Composio's infrastructure,
    which also sidesteps per-IP bot-blocking we hit scraping directly (e.g.
    Salesforce's docs site returning 403 to our own requests). Falls back to a
    direct httpx + BeautifulSoup fetch otherwise.
    """
    if os.environ.get("COMPOSIO_API_KEY"):
        try:
            text = _fetch_composio(url)
            if text:
                return text
        except Exception:
            pass
    return _scrape_url_httpx(url, timeout)


SAVE_RESEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "save_app_research",
        "description": "Save structured research findings about an app's public API.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "auth_methods": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["oauth2", "api_key", "basic_auth", "custom_token", "jwt", "none", "unknown"],
                    },
                },
                "access_model": {
                    "type": "string",
                    "enum": ["free_signup", "freemium", "paid_plan_required", "sales_contact_required", "invite_only", "unknown"],
                },
                "self_serve": {
                    "type": "boolean",
                    "description": "True if a developer can get credentials themselves for free/trial today, without sales/admin/partnership approval",
                },
                "api_quality": {
                    "type": "string",
                    "enum": ["rich_rest", "limited_rest", "graphql", "soap_legacy", "no_public_api", "unknown"],
                },
                "has_mcp": {
                    "type": "boolean",
                    "description": "True if the text mentions an existing/published MCP server for this app",
                },
                "mcp_notes": {
                    "type": "string",
                    "description": "Where an existing MCP was found (name/URL), or brief note that none was found in the given text",
                },
                "buildable_today": {
                    "type": "string",
                    "enum": ["yes_easy", "yes_hard", "no_blocked"],
                },
                "blockers": {"type": "array", "items": {"type": "string"}},
                "source_url": {"type": "string"},
                "confidence": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": [
                "description", "auth_methods", "access_model", "self_serve", "api_quality",
                "has_mcp", "buildable_today", "confidence",
            ],
        },
    },
}


# Groq enforces two independent quotas, and they fail in very different ways:
#   - TPM (tokens/minute) is shared across every key AND model on the account,
#     and clears within a minute -> pace calls, then wait it out.
#   - TPD (tokens/day) is PER MODEL, 200k on the free tier, and does NOT clear
#     for hours -> waiting is useless; rotate to a model with its own budget.
# The TPM response headers never mention TPD, so an exhausted daily budget looks
# like a healthy account right up until the 429. Only the error body says which
# quota was hit, so we branch on it.
MODEL_CHAIN = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]

# One entry per DISTINCT Groq organisation. Keys in the same org share quota, so
# listing a same-org key here would make the limiter assume capacity that isn't
# there and invite 429s. GROQ_API_KEY_FALLBACK is deliberately excluded: it is a
# same-org key, which is exactly why adding it never helped.
ORG_KEY_ENVS = ["GROQ_API_KEY", "GROQ_API_KEY_ORG2"]

_model_cooldown: dict[str, float] = {}


def _is_daily_limit(err: RateLimitError) -> bool:
    return "per day" in str(err).lower() or "tpd" in str(err).lower()


def _retry_after_seconds(err: RateLimitError) -> float:
    """Groq tells us exactly how long to wait — obey it instead of guessing."""
    try:
        val = err.response.headers.get("retry-after")
        if val:
            return min(float(val) + 1.0, 65.0)
    except (AttributeError, TypeError, ValueError):
        pass
    return 20.0


def _model_chain() -> list[str]:
    configured = os.environ.get("GROQ_MODEL")
    return ([configured] if configured else []) + [m for m in MODEL_CHAIN if m != configured]


def _live_slots(key_envs: list[str]) -> list[tuple[str, str]]:
    """(org key, model) pairs not currently parked by a daily-quota 429."""
    now = time.monotonic()
    slots = [(k, m) for k in key_envs for m in _model_chain()]
    live = [s for s in slots if _model_cooldown.get(f"{s[0]}:{s[1]}", 0) < now]
    return live or slots[:1]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_info(app_name: str, category: str, urls: list[str], content: str) -> AppResearch:
    """Call Groq with tool-calling forced, parse the tool call args into AppResearch.

    Paced by a rolling-window token limiter (see src/agent/ratelimit.py) because
    the account's 8000 TPM budget is shared across all keys and models. On a 429
    we wait exactly as long as Groq's own `retry-after` header says.
    """
    key_envs = [k for k in ORG_KEY_ENVS if os.environ.get(k)]
    if not key_envs:
        raise RuntimeError("No GROQ_API_KEY set")

    user_prompt = extraction_user_prompt(app_name, category, urls, content)
    estimate = estimate_tokens(EXTRACTION_SYSTEM_PROMPT + user_prompt)
    # Every (org, model) pair is an independent quota window, so treat them as a
    # pool and always send the call to whichever has the most room right now.
    # That keeps all windows busy instead of queueing on one saturated pair.
    slots = _live_slots(key_envs)
    slots.sort(key=lambda s: -get_limiter(f"{s[0]}:{s[1]}").free_capacity())

    raw = None
    for i, (key_env, model) in enumerate(slots):
        limiter = get_limiter(f"{key_env}:{model}")
        reservation = limiter.acquire(estimate)
        try:
            raw = get_groq_client(key_env).chat.completions.with_raw_response.create(
                model=model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[SAVE_RESEARCH_TOOL],
                tool_choice={"type": "function", "function": {"name": "save_app_research"}},
                temperature=0.1,
            )
            break
        except RateLimitError as err:
            limiter.settle(reservation, 0)
            last_slot = i == len(slots) - 1
            if _is_daily_limit(err):
                # Gone for hours. Park this exact (org, model) pair — not the
                # model globally, since the other org still has its own budget.
                _model_cooldown[f"{key_env}:{model}"] = time.monotonic() + 3600
            else:
                limiter.penalise(_retry_after_seconds(err))
            if not last_slot:
                continue  # another quota window may have room right now
            if not _is_daily_limit(err):
                time.sleep(_retry_after_seconds(err))
            raise

    limiter.observe_headers(raw.headers)
    resp = raw.parse()
    limiter.settle(reservation, getattr(getattr(resp, "usage", None), "total_tokens", None))

    message = resp.choices[0].message
    if not message.tool_calls:
        raise ValueError(f"Model did not call save_app_research for {app_name}")

    args = json.loads(message.tool_calls[0].function.arguments)
    args["app_name"] = app_name
    args["category"] = category
    args.setdefault("source_url", urls[0] if urls else "")
    return AppResearch(**args)
