"""Aggregate data/results.json into headline patterns for the report.

Run standalone: python -m src.analysis.patterns
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_PATH = Path("data/results.json")


def load_results() -> dict:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def analyze(results: dict) -> dict:
    apps = [r for r in results.values() if "error" not in r or r.get("confidence", 0) > 0]
    n = len(apps) or 1

    auth_counter = Counter()
    for r in apps:
        for m in r.get("auth_methods", []):
            auth_counter[m] += 1

    access_counter = Counter(r.get("access_model", "unknown") for r in apps)
    quality_counter = Counter(r.get("api_quality", "unknown") for r in apps)
    buildable_counter = Counter(r.get("buildable_today", "no_blocked") for r in apps)

    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in apps:
        by_category[r.get("category", "Unknown")].append(r)

    category_access = {}
    category_buildable = {}
    for cat, items in by_category.items():
        cat_n = len(items) or 1
        category_access[cat] = Counter(i.get("access_model", "unknown") for i in items)
        category_buildable[cat] = Counter(i.get("buildable_today", "no_blocked") for i in items)

    blocker_counter = Counter()
    for r in apps:
        for b in r.get("blockers", []):
            blocker_counter[b.lower().strip()] += 1

    easy_wins = sorted(
        [r for r in apps if r.get("buildable_today") == "yes_easy"],
        key=lambda r: -r.get("confidence", 0),
    )

    low_confidence = sorted(
        [r for r in apps if r.get("confidence", 0) < 0.6],
        key=lambda r: r.get("confidence", 0),
    )

    mcp_apps = [r["app_name"] for r in apps if r.get("has_mcp")]
    self_serve_count = sum(1 for r in apps if r.get("self_serve"))

    category_mcp = {
        cat: sum(1 for i in items if i.get("has_mcp")) for cat, items in by_category.items()
    }
    category_self_serve = {
        cat: sum(1 for i in items if i.get("self_serve")) for cat, items in by_category.items()
    }

    # The cluster that matters most for Composio: gated auth *and* no existing MCP
    unserved_gated = [
        r["app_name"]
        for r in apps
        if not r.get("has_mcp") and not r.get("self_serve")
    ]

    return {
        "total_apps": len(apps),
        "researched_apps": len(results),
        "mcp_existing_count": len(mcp_apps),
        "mcp_existing_apps": mcp_apps,
        "self_serve_count": self_serve_count,
        "category_mcp": category_mcp,
        "category_self_serve": category_self_serve,
        "category_counts": {cat: len(items) for cat, items in by_category.items()},
        "unserved_gated_apps": unserved_gated,
        "auth_distribution": dict(auth_counter.most_common()),
        "access_distribution": dict(access_counter.most_common()),
        "api_quality_distribution": dict(quality_counter.most_common()),
        "buildable_distribution": dict(buildable_counter.most_common()),
        "category_access": {k: dict(v) for k, v in category_access.items()},
        "category_buildable": {k: dict(v) for k, v in category_buildable.items()},
        "top_blockers": blocker_counter.most_common(10),
        "easy_wins": [r["app_name"] for r in easy_wins],
        "low_confidence_apps": [(r["app_name"], r.get("confidence", 0)) for r in low_confidence],
    }


def headline_insights(stats: dict) -> list[str]:
    insights = []
    n = stats["total_apps"]

    oauth_pct = round(100 * stats["auth_distribution"].get("oauth2", 0) / n) if n else 0
    if oauth_pct:
        insights.append(f"{oauth_pct}% of apps ({stats['auth_distribution'].get('oauth2', 0)}/{n}) support OAuth2.")

    easy = stats["buildable_distribution"].get("yes_easy", 0)
    insights.append(f"{easy}/{n} apps are buildable today with an easy, self-serve integration path.")

    mcp_n = stats.get("mcp_existing_count", 0)
    insights.append(
        f"An MCP server was discoverable for {mcp_n}/{n} apps ({round(100*mcp_n/n) if n else 0}%) — but this "
        f"counts official, community and aggregator (e.g. Zapier MCP) servers alike. The scarce thing is no "
        f"longer 'an MCP exists', it is a maintained, first-party one."
    )

    ss = stats.get("self_serve_count", 0)
    insights.append(
        f"{ss}/{n} apps let a developer self-serve credentials with no sales call or partner approval "
        f"({n - ss} need a human in the loop before a connector can even be tested)."
    )

    blocked = stats["buildable_distribution"].get("no_blocked", 0)
    if blocked:
        insights.append(f"{blocked}/{n} apps are currently blocked from having a connector built.")

    if stats["top_blockers"]:
        top = stats["top_blockers"][0]
        insights.append(
            f"The most common blocker is \"{top[0]}\" ({top[1]} app{'s' if top[1] != 1 else ''} affected)."
        )

    # Category with highest gated (paid/sales) rate
    gated_rates = {}
    for cat, dist in stats["category_access"].items():
        total = sum(dist.values()) or 1
        gated = dist.get("paid_plan_required", 0) + dist.get("sales_contact_required", 0)
        gated_rates[cat] = gated / total
    if gated_rates:
        most_gated = max(gated_rates, key=gated_rates.get)
        insights.append(f"{most_gated} is the most gated category ({round(gated_rates[most_gated]*100)}% require payment or sales contact).")
        least_gated = min(gated_rates, key=gated_rates.get)
        insights.append(f"{least_gated} is the most open category ({round((1-gated_rates[least_gated])*100)}% freely accessible).")

    return insights


def main():
    results = load_results()
    stats = analyze(results)
    stats["headline_insights"] = headline_insights(stats)
    out_path = Path("data/patterns.json")
    out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
