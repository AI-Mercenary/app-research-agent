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

    return {
        "total_apps": len(apps),
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

    blocked = stats["buildable_distribution"].get("no_blocked", 0)
    if blocked:
        insights.append(f"{blocked}/{n} apps are currently blocked from having a connector built.")

    if stats["top_blockers"]:
        top = stats["top_blockers"][0]
        insights.append(f"The most common blocker is \"{top[0]}\" ({top[1]} apps affected).")

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
