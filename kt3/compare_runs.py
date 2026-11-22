"""Парное сравнение двух сохранённых отчётов одного оценщика."""
import argparse
import json
from pathlib import Path


def fixtures(report):
    return {name.split("/eval/", 1)[1]: sha for name, sha in report["input_sha256"].items()
            if "/eval/" in name}


def compare(before, after):
    inputs = fixtures(before)
    if not inputs or inputs != fixtures(after):
        raise ValueError("Изменились корпус, gold или фикстуры")
    left, right = before["run"]["config"], after["run"]["config"]
    for field in ("search_case_ids", "ingestion_timeout_s", "fixture_version", "scenario_budgets"):
        if left[field] != right[field]:
            raise ValueError(f"Различается {field}")
    if before["cases"].keys() != after["cases"].keys() or before["not_run"] != after["not_run"]:
        raise ValueError("Различаются выборки или состав прогона")
    out = {"before": before["run"]["git_commit"], "after": after["run"]["git_commit"],
           "config_changes": {k: [left.get(k), right.get(k)] for k in sorted(left.keys() | right.keys())
                              if left.get(k) != right.get(k)}}
    for group in ("metrics", "checks"):
        if before[group].keys() != after[group].keys():
            raise ValueError("Различаются наборы метрик")
        out[group] = {}
        for name, old in before[group].items():
            new = after[group][name]
            def pairs():
                for case in before["cases"]:
                    a, b = (r["cases"][case][group].get(name, {}).get("value") for r in (before, after))
                    if a != b:
                        yield case, a, b
            changes = list(pairs())
            out[group][name] = {"before":old["value"], "after":new["value"],
                "delta":new["value"]-old["value"] if old["status"] == new["status"] == "ok" else None,
                "increased":[c for c,a,b in changes if None not in (a,b) and b>a],
                "decreased":[c for c,a,b in changes if None not in (a,b) and b<a],
                "changed_availability":[c for c,a,b in changes if None in (a,b)]}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("before", "after", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads((p/"report.json").read_text()) for p in (args.before,args.after)]
    result = compare(*reports)
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
