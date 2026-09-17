"""Accuracy audit against human-collected ground truth.

`data/verified.json` is built by a human opening each vendor's real docs, WITHOUT
looking at the agent's answers first (anchoring on the agent's output would make
the audit measure agreement rather than correctness).

This script scores every available pass against that same ground truth:
  - data/results_pass1.json  the pipeline BEFORE the fixes (ablation, if present)
  - data/results.json        the current pipeline

Scoring both against one ground truth is what makes the improvement claim real:
the reference never moved, so the delta is attributable to the pipeline changes.

Run: python -m src.verification.verify
"""
from __future__ import annotations

import json
from pathlib import Path

VERIFIED_PATH = Path("data/verified.json")
PASSES = [
    ("pass1_before_fixes", Path("data/results_pass1.json")),
    ("final", Path("data/results.json")),
]

FIELDS_TO_CHECK = ["auth_methods", "access_model", "api_quality", "buildable_today"]


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def compare_field(agent_val, human_val) -> bool:
    if isinstance(human_val, list):
        return set(agent_val or []) == set(human_val or [])
    return agent_val == human_val


def score_pass(results: dict, verified: dict) -> dict:
    field_correct = {f: 0 for f in FIELDS_TO_CHECK}
    field_total = {f: 0 for f in FIELDS_TO_CHECK}
    apps_fully_correct = 0
    details = []

    for app_name, human in verified.items():
        agent = results.get(app_name)
        if agent is None or agent.get("error"):
            details.append({"app": app_name, "status": "NO_AGENT_RESULT", "mismatches": []})
            continue

        mismatches = []
        for field in FIELDS_TO_CHECK:
            # An "unknown" ground truth means the human couldn't establish a fact,
            # so there is nothing to grade against — skip rather than punish.
            if human.get(field) in (None, "unknown", ["unknown"]):
                continue
            field_total[field] += 1
            if compare_field(agent.get(field), human.get(field)):
                field_correct[field] += 1
            else:
                mismatches.append({
                    "field": field,
                    "agent_said": agent.get(field),
                    "actually": human.get(field),
                })

        if not mismatches:
            apps_fully_correct += 1
        details.append({"app": app_name, "mismatches": mismatches})

    graded_fields = sum(field_total.values())
    correct_fields = sum(field_correct.values())
    scored_apps = sum(1 for d in details if d.get("status") != "NO_AGENT_RESULT")

    return {
        "apps_in_ground_truth": len(verified),
        "apps_scored": scored_apps,
        "apps_fully_correct": apps_fully_correct,
        "app_level_accuracy_pct": round(100 * apps_fully_correct / scored_apps, 1) if scored_apps else 0,
        "field_level_accuracy_pct": round(100 * correct_fields / graded_fields, 1) if graded_fields else 0,
        "fields_graded": graded_fields,
        "fields_correct": correct_fields,
        "field_accuracy": {
            f: round(100 * field_correct[f] / field_total[f], 1) if field_total[f] else None
            for f in FIELDS_TO_CHECK
        },
        "details": details,
    }


def run_verification():
    verified = load(VERIFIED_PATH)
    if not verified:
        print("data/verified.json is empty. Build the human ground truth first.")
        return

    report = {"ground_truth_apps": sorted(verified.keys()), "passes": {}}

    for label, path in PASSES:
        results = load(path)
        if not results:
            continue
        report["passes"][label] = score_pass(results, verified)

    for label, score in report["passes"].items():
        print(f"\n=== {label} ===")
        print(f"  field-level accuracy: {score['field_level_accuracy_pct']}% "
              f"({score['fields_correct']}/{score['fields_graded']} fields)")
        print(f"  apps fully correct:   {score['apps_fully_correct']}/{score['apps_scored']} "
              f"({score['app_level_accuracy_pct']}%)")
        for f, pct in score["field_accuracy"].items():
            print(f"    {f}: {pct}%")
        bad = [d for d in score["details"] if d.get("mismatches")]
        if bad:
            print("  mismatches:")
            for d in bad:
                for m in d["mismatches"]:
                    print(f"    - {d['app']}.{m['field']}: agent={m['agent_said']!r} actual={m['actually']!r}")

    if "pass1_before_fixes" in report["passes"] and "final" in report["passes"]:
        before = report["passes"]["pass1_before_fixes"]["field_level_accuracy_pct"]
        after = report["passes"]["final"]["field_level_accuracy_pct"]
        report["improvement"] = {
            "before_pct": before,
            "after_pct": after,
            "delta_pct": round(after - before, 1),
        }
        print(f"\nAccuracy improvement: {before}% -> {after}% ({after - before:+.1f} points)")

    Path("data/verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nWritten to data/verification_report.json")


if __name__ == "__main__":
    run_verification()
