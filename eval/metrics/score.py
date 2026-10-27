#!/usr/bin/env python3
"""Offline ranking/action metrics. This scores responses; it does not run a search engine."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

ACTIONS = ("search", "clarify", "no_result", "refuse")
FAILURES = ("error", "timeout", "missing", "invalid")
K = 5


def index_rows(rows, label):
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError(f"{label}: every row needs a nonempty string id")
        if row["id"] in indexed:
            raise ValueError(f"{label}: duplicate id {row['id']}")
        indexed[row["id"]] = row
    return indexed


def outcome(prediction):
    """Failures are outcomes, never a fifth model action or silently omitted cases."""
    if prediction is None:
        return "missing", []
    status = prediction.get("status")
    if isinstance(status, str) and status in FAILURES:
        return status, []
    action, results = prediction.get("action"), prediction.get("result_doc_ids")
    if (status != "ok" or not isinstance(action, str) or action not in ACTIONS
            or not isinstance(results, list)
            or any(not isinstance(id_, str) or not id_ for id_ in results)
            or (action != "search" and results)):
        return "invalid", []
    return action, results


def aggregate(values):
    total = math.fsum(values)
    return {"value": total / len(values) if values else None, "sum": total, "n": len(values)}


def score(cases, predictions):
    gold = index_rows(cases, "cases")
    predicted = index_rows(predictions, "predictions")
    if not gold:
        raise ValueError("cases: empty evaluation set")
    unknown = predicted.keys() - gold.keys()
    if unknown:
        raise ValueError(f"predictions: unknown case ids {sorted(unknown)}")
    metrics = {name: [] for name in ("HitRate@5", "MRR@5", "Recall@5", "Precision@5",
                                    "ActionAccuracy", "FalseRefusalRate")}
    per_action = {action: [] for action in ACTIONS}
    confusion = {action: {label: 0 for label in ACTIONS + FAILURES} for action in ACTIONS}
    outcomes = Counter()
    for id_, case in gold.items():
        expected = case.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"{id_}: missing expected object")
        action = expected.get("action")
        relevant = expected.get("relevant_doc_ids")
        if (not isinstance(action, str) or action not in ACTIONS
                or not isinstance(relevant, list)
                or any(not isinstance(doc, str) or not doc for doc in relevant)
                or len(relevant) != len(set(relevant))
                or bool(relevant) != (action == "search")):
            raise ValueError(f"{id_}: invalid action/relevance gold")
        actual, results = outcome(predicted.get(id_))
        outcomes[actual] += 1
        confusion[action][actual] += 1
        correct_action = int(actual == action)
        metrics["ActionAccuracy"].append(correct_action)
        per_action[action].append(correct_action)
        # The cohort is selected by gold, not by model action or available predictions.
        if action != "search":
            continue
        metrics["FalseRefusalRate"].append(int(actual == "refuse"))
        top = results[:K] if actual == "search" else []
        relevant = set(relevant)
        hits = len(set(top) & relevant)
        first_rank = next((rank for rank, doc in enumerate(top, 1) if doc in relevant), None)
        metrics["HitRate@5"].append(int(hits > 0))
        metrics["MRR@5"].append(1 / first_rank if first_rank else 0)
        metrics["Recall@5"].append(hits / len(relevant))
        metrics["Precision@5"].append(hits / K)
    return {
        "schema_version": 1,
        "k": K,
        "case_count": len(gold),
        "prediction_count": len(predicted),
        "gold_action_counts": {action: len(values) for action, values in per_action.items()},
        "outcome_counts": {label: outcomes[label] for label in ACTIONS + FAILURES},
        "metrics": {name: aggregate(values) for name, values in metrics.items()},
        "action_accuracy_by_gold_action": {action: aggregate(values) for action, values in per_action.items()},
        "confusion_matrix": confusion,
    }


def read_jsonl(path):
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{line_number}: blank JSONL row")
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[1] / "queries/dev.jsonl")
    parser.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = score(read_jsonl(args.cases), read_jsonl(args.predictions))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Cannot score: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
