"""The three tools the agent uses: web search, scraping, and LLM extraction.

Extraction uses real Groq tool-calling (the LLM calls a `save_app_research`
function with structured arguments) rather than plain JSON-mode text, so the
project demonstrates actual tool-calling orchestration.
"""
from __future__ import annotations

import json
import os

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agent.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_user_prompt
from src.agent.state import AppResearch

_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo web search. Returns [{title, href, body}, ...]."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def scrape_url(url: str, timeout: float = 10.0) -> str:
    """Fetch a URL and return cleaned visible text (truncated)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ComposioResearchBot/1.0)"}
    resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "svg"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:6000]


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
                "api_quality": {
                    "type": "string",
                    "enum": ["rich_rest", "limited_rest", "graphql", "soap_legacy", "no_public_api", "unknown"],
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
                "description", "auth_methods", "access_model", "api_quality",
                "buildable_today", "confidence",
            ],
        },
    },
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def extract_info(app_name: str, category: str, urls: list[str], content: str) -> AppResearch:
    """Call Groq with tool-calling forced, parse the tool call args into AppResearch."""
    client = get_groq_client()
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": extraction_user_prompt(app_name, category, urls, content)},
        ],
        tools=[SAVE_RESEARCH_TOOL],
        tool_choice={"type": "function", "function": {"name": "save_app_research"}},
        temperature=0.1,
    )

    message = resp.choices[0].message
    if not message.tool_calls:
        raise ValueError(f"Model did not call save_app_research for {app_name}")

    args = json.loads(message.tool_calls[0].function.arguments)
    args["app_name"] = app_name
    args["category"] = category
    args.setdefault("source_url", urls[0] if urls else "")
    return AppResearch(**args)
