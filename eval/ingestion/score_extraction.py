#!/usr/bin/env python3
"""Score preserved source anchors in ingestion outputs; not a semantic metadata judge."""
import argparse
import json
import math
from pathlib import Path

from source_text import contains_quote
from validate_gold import ROOT, load_rows


def indexed(rows):
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in result:
            raise ValueError("Every row needs a unique nonempty string id")
        result[row["id"]] = row
    return result


def score(gold, outputs):
    gold, outputs = indexed(gold), indexed(outputs)
    if not gold or outputs.keys() - gold.keys():
        raise ValueError("Empty gold or unknown output case ids")
    cases = []
    for id_, row in gold.items():
        fragments = row["fragments"]
        if not isinstance(fragments, list) or not fragments:
            raise ValueError(f"{id_}: missing gold fragments")
        fragment_ids = [f["id"] for f in fragments]
        if len(set(fragment_ids)) != len(fragment_ids) or any(not isinstance(f["quote"], str) or not f["quote"].strip() for f in fragments):
            raise ValueError(f"{id_}: invalid fragments")
        output = outputs.get(id_)
        status = output.get("status") if output else "missing"
        text = output.get("extracted_text") if output else None
        if status == "ok" and not isinstance(text, str):
            status = "invalid"
        if not isinstance(status, str) or status not in {"ok", "missing", "error", "timeout", "invalid"}:
            status = "invalid"
        matched = [f["id"] for f in fragments if status == "ok" and contains_quote(text, f["quote"])]
        cases.append({"id": id_, "status": status, "matched": matched,
                      "missing": [id_ for id_ in fragment_ids if id_ not in matched],
                      "fraction": len(matched) / len(fragments), "fragment_count": len(fragments)})
    total = math.fsum(case["fraction"] for case in cases)
    return {"metric": "ExtractionCoverage", "aggregation": "macro_mean_per_valid_input",
            "gold_provenance": {
                "annotation_statuses": sorted({r.get("annotation_status", "unspecified") for r in gold.values()}),
                "human_review_statuses": sorted({r.get("human_review_status", "unspecified") for r in gold.values()}),
            },
            "value": total / len(cases), "sum": total, "n": len(cases), "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = score(load_rows(ROOT / "ingestion/gold.jsonl"), load_rows(args.outputs))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Cannot score extraction: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
