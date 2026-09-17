"""LangGraph state machine for researching one app.

START -> search_web -> scrape_docs -> extract_info -> validate
                ^                                         |
                └────────── retry (low confidence) ───────┘
                                                            |
                                                       save_result -> END
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agent.prompts import (
    MCP_QUERY_TEMPLATE,
    SEARCH_QUERY_RETRY_TEMPLATE,
    SEARCH_QUERY_TEMPLATE,
)
from src.agent.state import AgentState
from src.agent.tools import extract_info, scrape_url, search_web

MAX_RETRIES = 2
CONFIDENCE_THRESHOLD = 0.6
MAX_SCRAPE_URLS = 3


MAX_MCP_URLS = 2


def node_search_web(state: AgentState) -> AgentState:
    query = state.get("query") or SEARCH_QUERY_TEMPLATE.format(app_name=state["app_name"])
    try:
        results = search_web(query)
    except Exception as e:
        return {**state, "search_results": [], "error": f"search_failed: {e}"}

    # Separate, narrower search for MCP existence. Merged into one evidence pool
    # but kept distinct from the docs query so neither crowds the other out.
    mcp_results = []
    try:
        mcp_results = search_web(MCP_QUERY_TEMPLATE.format(app_name=state["app_name"]), max_results=MAX_MCP_URLS)
    except Exception:
        pass

    return {**state, "search_results": results, "mcp_results": mcp_results, "error": None}


AD_REDIRECT_MARKERS = ("bing.com/aclick", "google.com/aclk", "googleadservices.com")


def _usable(results: list[dict], limit: int) -> list[dict]:
    return [
        r for r in results
        if r.get("href") and not any(m in r["href"] for m in AD_REDIRECT_MARKERS)
    ][:limit]


def node_scrape_docs(state: AgentState) -> AgentState:
    docs = _usable(state.get("search_results") or [], MAX_SCRAPE_URLS)
    mcp = _usable(state.get("mcp_results") or [], MAX_MCP_URLS)
    seen = {r["href"] for r in docs}
    mcp = [r for r in mcp if r["href"] not in seen]

    chunks = []
    ok_urls = []
    # Budget per source rather than truncating the concatenation: MCP evidence is
    # appended last, so a single trailing cut silently discarded it every time and
    # made has_mcp look false for apps that plainly have a server.
    for label, group, budget in (("API DOCS", docs, 1500), ("MCP SEARCH RESULT", mcp, 700)):
        for r in group:
            url = r["href"]
            text = r.get("text")  # pre-fetched server-side; no local scrape needed
            if not text:
                try:
                    text = scrape_url(url)
                except Exception:
                    continue
            if text:
                chunks.append(f"=== [{label}] {url} ===\n{text[:budget]}")
                if label == "API DOCS":
                    ok_urls.append(url)
    return {**state, "scraped_content": "\n\n".join(chunks), "scraped_urls": ok_urls or [r["href"] for r in mcp]}


def node_extract_info(state: AgentState) -> AgentState:
    content = state.get("scraped_content") or ""
    urls = state.get("scraped_urls") or []
    if not content:
        return {**state, "extraction": None, "error": "no_content_scraped"}
    try:
        research = extract_info(state["app_name"], state["category"], urls, content)
    except Exception as e:
        return {**state, "extraction": None, "error": f"extract_failed: {e}"}
    return {**state, "extraction": research, "error": None}


def node_validate(state: AgentState) -> AgentState:
    # pass-through node; branching decided in route_after_validate
    return state


def route_after_validate(state: AgentState) -> str:
    extraction = state.get("extraction")
    retry_count = state.get("retry_count", 0)
    confident_enough = extraction is not None and extraction.confidence >= CONFIDENCE_THRESHOLD
    if confident_enough or retry_count >= MAX_RETRIES:
        return "save_result"
    return "retry"


def node_prepare_retry(state: AgentState) -> AgentState:
    query = SEARCH_QUERY_RETRY_TEMPLATE.format(app_name=state["app_name"])
    return {**state, "query": query, "retry_count": state.get("retry_count", 0) + 1}


def node_save_result(state: AgentState) -> AgentState:
    # Terminal node; the caller (run.py) reads state["extraction"] after invoke().
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("search_web", node_search_web)
    graph.add_node("scrape_docs", node_scrape_docs)
    graph.add_node("extract_info", node_extract_info)
    graph.add_node("validate", node_validate)
    graph.add_node("prepare_retry", node_prepare_retry)
    graph.add_node("save_result", node_save_result)

    graph.set_entry_point("search_web")
    graph.add_edge("search_web", "scrape_docs")
    graph.add_edge("scrape_docs", "extract_info")
    graph.add_edge("extract_info", "validate")
    graph.add_conditional_edges(
        "validate", route_after_validate, {"retry": "prepare_retry", "save_result": "save_result"}
    )
    graph.add_edge("prepare_retry", "search_web")
    graph.add_edge("save_result", END)

    return graph.compile()
