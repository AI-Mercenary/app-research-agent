"""Manual verification workflow (Part 4 of the task).

Workflow:
1. Pick 15-20 apps (edit SAMPLE_APPS below).
2. Manually open their real docs and fill out data/verified.json by hand,
   one entry per app, matching the AppResearch fields you actually observed.
3. Run `python -m src.verification.verify` to diff verified.json against
   the agent's results.json and print a field-by-field accuracy report.
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS_PATH = Path("data/results.json")
VERIFIED_PATH = Path("data/verified.json")

FIELDS_TO_CHECK = ["auth_methods", "access_model", "api_quality", "buildable_today"]


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def compare_field(agent_val, human_val) -> bool:
    if isinstance(human_val, list):
        return set(agent_val or []) == set(human_val or [])
    return agent_val == human_val


def run_verification():
    results = load(RESULTS_PATH)
    verified = load(VERIFIED_PATH)

    if not verified:
        print("data/verified.json is empty. Fill it in manually first (see docstring).")
        return

    report = []
    field_correct = {f: 0 for f in FIELDS_TO_CHECK}
    field_total = {f: 0 for f in FIELDS_TO_CHECK}
    apps_fully_correct = 0

    for app_name, human in verified.items():
        agent = results.get(app_name)
        if agent is None:
            report.append({"app": app_name, "status": "MISSING_FROM_AGENT_RESULTS"})
            continue

        mismatches = []
        for field in FIELDS_TO_CHECK:
            field_total[field] += 1
            ok = compare_field(agent.get(field), human.get(field))
            if ok:
                field_correct[field] += 1
            else:
                mismatches.append({
                    "field": field,
                    "agent_said": agent.get(field),
                    "actually": human.get(field),
                })

        if not mismatches:
            apps_fully_correct += 1
        report.append({"app": app_name, "mismatches": mismatches})

    total_apps = len(verified)
    overall_accuracy = round(100 * apps_fully_correct / total_apps, 1) if total_apps else 0

    print(f"Verified {total_apps} apps. Fully correct: {apps_fully_correct}/{total_apps} ({overall_accuracy}%)\n")
    print("Per-field accuracy:")
    for field in FIELDS_TO_CHECK:
        pct = round(100 * field_correct[field] / field_total[field], 1) if field_total[field] else 0
        print(f"  {field}: {field_correct[field]}/{field_total[field]} ({pct}%)")

    print("\nApps with mismatches:")
    for entry in report:
        if entry.get("mismatches"):
            print(f"  - {entry['app']}: {entry['mismatches']}")

    out = {
        "total_apps_checked": total_apps,
        "fully_correct": apps_fully_correct,
        "overall_accuracy_pct": overall_accuracy,
        "field_accuracy": {
            f: round(100 * field_correct[f] / field_total[f], 1) if field_total[f] else 0
            for f in FIELDS_TO_CHECK
        },
        "details": report,
    }
    Path("data/verification_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nWritten to data/verification_report.json")


if __name__ == "__main__":
    run_verification()
