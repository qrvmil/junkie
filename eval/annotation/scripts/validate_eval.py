#!/usr/bin/env python3
"""Read-only validation of search gold, step expectations and adjudicated labels."""
import argparse
import json
import re
from pathlib import Path

from prepare_blind import FIELDS, ROOT, load_jsonl
from validate_annotations import (
    ANNOTATION_FIELDS, comparable, effective_documents, validate_adjudication,
    validate_blind, validate_file, validate_row,
)


def project_gold(case):
    """The seven shared annotation fields; case-specific evaluation checks stay in dev."""
    return {"id": case["id"], **{key: case["expected"][key]
                               for key in ANNOTATION_FIELDS - {"id"}}}


def in_range(value, bounds):
    return ("gte" not in bounds or value >= bounds["gte"]) and (
        "lt" not in bounds or value < bounds["lt"])


def matches_filters(doc, filters):
    """Test exact metadata conditions after applying fixture overrides, without guessing."""
    for key, value in filters.items():
        if key == "filename":
            name = Path(doc["path"]).name
            # Corpus numbering is a transport prefix, not part of the original filename.
            if value not in {name, re.sub(r"^\d{3}_", "", name)}:
                return False
        elif key == "uploaded_at":
            if not doc.get(key) or not in_range(doc[key], value):
                return False
        elif key == "content_date":
            if not any(event.get("date") and in_range(event["date"], value)
                       and ("event" not in value or event.get("kind") == value["event"])
                       for event in doc.get("content_events", [])):
                return False
        elif doc.get(key) != value:
            return False
    return True


def validate_case(case, docs, max_results=5):
    id_ = case["id"]
    row = project_gold(case)
    validate_row(row, case, docs)
    expected, steps = case["expected"], case["gold_steps"]
    if type(expected.get("all_results_required")) is not bool:
        raise ValueError(f"{id_}: all_results_required must be boolean")
    for key in ("filters", "order_by"):
        if steps.get(key) != row[key]:
            raise ValueError(f"{id_}: gold_steps.{key} differs from expected")
    for doc_id in row["relevant_doc_ids"] + row["clarify_candidates"]:
        if not matches_filters(docs[doc_id], row["filters"]):
            raise ValueError(f"{id_}: {doc_id} cannot satisfy gold metadata filters")
    checks = case["checks"]
    if not isinstance(checks, list) or not {"action", "results", "filters", "order", "parse", "calls", "access"} <= set(checks):
        raise ValueError(f"{id_}: missing mandatory evaluation checks")
    if ("clarification" in checks) != (row["action"] == "clarify"):
        raise ValueError(f"{id_}: clarification check disagrees with action")
    calls = case["expected_calls"]
    if not isinstance(calls, list):
        raise ValueError(f"{id_}: expected_calls must be a list")
    if row["action"] in {"search", "no_result"} and not calls:
        raise ValueError(f"{id_}: missing retrieval call")
    if row["action"] == "refuse" and calls:
        raise ValueError(f"{id_}: refusal must not require document access")
    for call in calls:
        args = call["arguments_subset"]
        if call["tool"] == "search_documents":
            if any(args.get(key) != row[key] for key in ("filters", "order_by")):
                raise ValueError(f"{id_}: search call filters/order differ from expected")
            if type(args.get("limit")) is not int or args["limit"] != max_results:
                raise ValueError(f"{id_}: search call limit differs from environment")
            if call.get("query_contains") != steps.get("search_text_contains"):
                raise ValueError(f"{id_}: query constraint differs between steps and calls")
        elif call["tool"] == "get_document":
            if args.get("doc_id") not in row["relevant_doc_ids"]:
                raise ValueError(f"{id_}: get_document must target an expected accessible document")
        else:
            raise ValueError(f"{id_}: unknown expected tool")


def validate_dataset(root=ROOT):
    cases = load_jsonl(root / "queries/dev.jsonl")
    manifest = [json.loads(line) for line in (root / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    environment = json.loads((root / "fixtures/environment.json").read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in cases}
    fixtures = {}
    for case in cases:
        key = (case["environment_id"], case["fixture_id"])
        if key not in fixtures:
            fixtures[key] = effective_documents(case, manifest, environment, root)
        docs = fixtures[key]
        validate_case(case, docs, environment["max_results"])
    folder = root / "annotation"
    blind = validate_blind(folder / "blind_cases.jsonl")
    final = validate_file(folder / "final_gold.jsonl", blind, manifest, environment, root)
    for id_, row in final.items():
        if id_ not in by_id:
            raise ValueError(f"{id_}: final gold missing from dev")
        case = by_id[id_]
        if comparable(project_gold(case)) != comparable(row):
            raise ValueError(f"{id_}: dev expected differs from final_gold")
        if {key: case[key] for key in FIELDS if key in case} != blind[id_]:
            raise ValueError(f"{id_}: dev input differs from annotated blind case")
    a, b = [validate_file(folder / name, blind, manifest, environment, root)
            for name in ("preannotation.jsonl", "preannotation_2.jsonl")]
    validate_adjudication(folder / "adjudication.jsonl", a, b, final)
    for correction in load_jsonl(folder / "gold_corrections.jsonl"):
        id_ = correction["id"]
        if correction["final"] != final.get(id_) or correction["previous"].get("id") != id_:
            raise ValueError(f"{id_}: correction history differs from final gold")
        if comparable(correction["previous"]) == comparable(correction["final"]) or not correction.get("reason"):
            raise ValueError(f"{id_}: correction needs an actual change and reason")
        validate_row(correction["previous"], blind[id_], fixtures[(blind[id_]["environment_id"], blind[id_]["fixture_id"])])
    return len(cases), len(final)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        cases, annotated = validate_dataset(args.eval_root)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Invalid eval: {exc}\n")
    print(f"Valid: {cases} search cases; {annotated} final-gold cases; steps, calls, filters and adjudication agree")


if __name__ == "__main__":
    main()
