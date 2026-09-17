"""Reproduce the PRE-FIX pipeline so the accuracy claim is measured, not asserted.

The final pipeline differs from the first working version in three ways that were
each introduced to fix an observed defect:

  1. ad-redirect filtering  - the first version fed search-ad landing pages
                              (bing.com/aclick/...) straight into the extractor,
                              which produced confident descriptions of the WRONG
                              company.
  2. Composio MCP fetching  - the first version scraped pages from this machine,
                              so vendors that 403 our user-agent yielded no
                              evidence at all.
  3. no-MCP-inference rule  - the first prompt let the model infer that an MCP
                              server "probably exists" for agent-friendly APIs.

This module re-runs a given set of apps with all three reverted, writing
`data/results_pass1.json`. Scoring that file and the current one against the
same human ground truth is what turns "we improved accuracy" into a number.

Run: python -m src.verification.ablation
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.agent import graph as graph_module  # noqa: E402
from src.agent import prompts as prompts_module  # noqa: E402
from src.agent import tools as tools_module  # noqa: E402

OUT_PATH = Path("data/results_pass1.json")
VERIFIED_PATH = Path("data/verified.json")

def _pass1_system_prompt() -> str:
    """Swap the strict no-inference MCP rule back to the permissive original."""
    lines = prompts_module.EXTRACTION_SYSTEM_PROMPT.split("\n")
    out = []
    for line in lines:
        if line.startswith("- has_mcp: true only if"):
            out.append("- has_mcp: true if this app has or likely has an MCP (Model Context Protocol) server.")
        else:
            out.append(line)
    return "\n".join(out)


def apply_pass1_ablation() -> None:
    # 1. no ad-redirect filtering (graph reads this global at call time)
    graph_module.AD_REDIRECT_MARKERS = ()

    # 2. no Composio server-side fetching: scrape from this machine only.
    #    graph.py imported scrape_url by value, so patch it there too.
    graph_module.scrape_url = tools_module._scrape_url_httpx

    # 3. allow the model to infer MCP existence
    tools_module.EXTRACTION_SYSTEM_PROMPT = _pass1_system_prompt()


def main():
    if not VERIFIED_PATH.exists():
        print("data/verified.json not found — build the ground truth first.")
        sys.exit(1)

    target_apps = list(json.loads(VERIFIED_PATH.read_text(encoding="utf-8")).keys())
    apply_pass1_ablation()

    from data.apps import flat_list

    categories = dict((a, c) for a, c in flat_list())
    graph = graph_module.build_graph()

    results = {}
    if OUT_PATH.exists():
        results = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    for i, app in enumerate(target_apps, 1):
        if app in results and not results[app].get("error"):
            print(f"[{i}/{len(target_apps)}] SKIP {app}")
            continue
        print(f"[{i}/{len(target_apps)}] pass1 {app}...")
        try:
            state = graph.invoke(
                {"app_name": app, "category": categories.get(app, "Unknown"), "retry_count": 0},
                config={"recursion_limit": 25},
            )
            extraction = state.get("extraction")
            results[app] = (
                extraction.model_dump()
                if extraction is not None
                else {"app_name": app, "error": state.get("error", "unknown"), "confidence": 0.0}
            )
        except Exception as e:
            results[app] = {"app_name": app, "error": str(e), "confidence": 0.0}
        print(f"   -> confidence={results[app].get('confidence')}")
        OUT_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    print(f"\nWrote {len(results)} pass-1 results to {OUT_PATH}")


if __name__ == "__main__":
    main()
