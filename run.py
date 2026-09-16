"""Entry point: research all 100 apps and write data/results.json.

Usage:
    python run.py                 # research all apps not already in results.json
    python run.py --app Slack     # research a single app (for debugging)
    python run.py --force         # re-research everything, ignoring existing results
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from data.apps import flat_list  # noqa: E402
from src.agent.graph import build_graph  # noqa: E402

RESULTS_PATH = Path("data/results.json")

USE_LANGFUSE = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
if USE_LANGFUSE:
    from langfuse.callback import CallbackHandler  # type: ignore

    langfuse_handler = CallbackHandler(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )


def load_existing() -> dict:
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {}


def save_all(results: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def research_app(graph, app_name: str, category: str) -> dict:
    config = {"recursion_limit": 25}
    if USE_LANGFUSE:
        config["callbacks"] = [langfuse_handler]
        config["run_name"] = f"research:{app_name}"

    initial_state = {"app_name": app_name, "category": category, "retry_count": 0}
    final_state = graph.invoke(initial_state, config=config)

    extraction = final_state.get("extraction")
    if extraction is None:
        return {
            "app_name": app_name,
            "category": category,
            "error": final_state.get("error", "unknown_failure"),
            "confidence": 0.0,
        }
    return extraction.model_dump()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", help="Research a single app by name")
    parser.add_argument("--force", action="store_true", help="Re-research apps already in results.json")
    args = parser.parse_args()

    graph = build_graph()
    results = load_existing()

    targets = flat_list()
    if args.app:
        targets = [(a, c) for a, c in targets if a.lower() == args.app.lower()]
        if not targets:
            print(f"App '{args.app}' not found in data/apps.py")
            sys.exit(1)

    for i, (app_name, category) in enumerate(targets, 1):
        if not args.force and app_name in results:
            print(f"[{i}/{len(targets)}] SKIP {app_name} (already have result)")
            continue

        print(f"[{i}/{len(targets)}] Researching {app_name} ({category})...")
        try:
            result = research_app(graph, app_name, category)
        except Exception as e:
            print(f"  !! failed: {e}")
            result = {"app_name": app_name, "category": category, "error": str(e), "confidence": 0.0}

        results[app_name] = result
        save_all(results)

        conf = result.get("confidence", 0)
        status = "ok" if conf >= 0.6 else "low-confidence"
        print(f"  -> {status} (confidence={conf})")
        time.sleep(1)  # be polite to search/scrape targets

    print(f"\nDone. {len(results)} apps in {RESULTS_PATH}")


if __name__ == "__main__":
    main()
