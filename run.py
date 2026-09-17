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
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from data.apps import flat_list  # noqa: E402
from src.agent.graph import build_graph  # noqa: E402

RESULTS_PATH = Path("data/results.json")

USE_LANGFUSE = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
if USE_LANGFUSE:
    from langfuse.langchain import CallbackHandler  # type: ignore

    langfuse_handler = CallbackHandler()


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
    parser.add_argument(
        "--workers", type=int, default=6,
        help="Parallel apps to research at once (default 6). Token pacing is shared across workers.",
    )
    parser.add_argument(
        "--retry-bad",
        action="store_true",
        help="Re-research only apps that errored or scored below 0.6 confidence. "
             "Runs them in one process so the Groq token limiter paces across apps.",
    )
    args = parser.parse_args()

    graph = build_graph()
    results = load_existing()

    targets = flat_list()
    if args.app:
        targets = [(a, c) for a, c in targets if a.lower() == args.app.lower()]
        if not targets:
            print(f"App '{args.app}' not found in data/apps.py")
            sys.exit(1)
    elif args.retry_bad:
        bad = {
            name for name, r in results.items()
            if r.get("error") or r.get("confidence", 0) < 0.6
        }
        targets = [(a, c) for a, c in targets if a in bad]
        args.force = True
        print(f"Retrying {len(targets)} failed/low-confidence apps in a single process.\n")

    pending = [
        (app_name, category)
        for app_name, category in targets
        if args.force or app_name not in results
    ]
    skipped = len(targets) - len(pending)
    if skipped:
        print(f"Skipping {skipped} apps that already have results.")

    # Each app is dominated by network latency (search + 3 page fetches), so the
    # run is I/O-bound and parallelises well. Token pacing stays correct because
    # the rate limiter is shared and lock-guarded — workers queue on it rather
    # than each keeping a private budget (which is what made per-app subprocesses
    # blow the quota).
    lock = threading.Lock()
    done = 0

    def handle(item: tuple[str, str]) -> None:
        nonlocal done
        app_name, category = item
        try:
            result = research_app(graph, app_name, category)
        except Exception as e:
            result = {"app_name": app_name, "category": category, "error": str(e), "confidence": 0.0}

        conf = result.get("confidence", 0) or 0
        status = "ok" if conf >= 0.6 else "low-confidence"
        with lock:
            done += 1
            results[app_name] = result
            save_all(results)
            print(f"[{done}/{len(pending)}] {app_name} -> {status} (confidence={conf})", flush=True)

    if args.workers > 1 and len(pending) > 1:
        print(f"Researching {len(pending)} apps with {args.workers} workers.\n", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(handle, pending))
    else:
        for item in pending:
            handle(item)

    print(f"\nDone. {len(results)} apps in {RESULTS_PATH}")


if __name__ == "__main__":
    main()
