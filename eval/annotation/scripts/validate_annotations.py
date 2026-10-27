#!/usr/bin/env python3
"""Validate annotation shape, case coverage, fixture scope and document ACLs."""
import argparse
import json
from datetime import date
from pathlib import Path

from prepare_blind import CASE_IDS, FIELDS, ROOT, load_jsonl

ACTIONS = ("search", "clarify", "no_result", "refuse")
ANNOTATION_FIELDS = {
    "id", "action", "relevant_doc_ids", "clarify_candidates", "filters", "order_by", "has_more"
}
ORDERS = {"relevance", "uploaded_at_asc", "uploaded_at_desc"}
FILTERS = {"format", "source_type", "doc_type", "filename", "uploaded_at", "content_date"}


def validate_blind(path):
    cases = load_jsonl(path)
    if [row["id"] for row in cases] != CASE_IDS:
        raise ValueError("Blind cases must match the 30 predeclared IDs in order")
    for case in cases:
        if set(case) - set(FIELDS):
            raise ValueError(f"{case['id']}: non-allowlisted blind fields")
        required = {"id", "query", "user_id", "now", "timezone", "fixture_id", "environment_id"}
        if required - case.keys():
            raise ValueError(f"{case['id']}: missing case conditions")
    return {row["id"]: row for row in cases}


def effective_documents(case, manifest, environment, eval_root):
    if case["environment_id"] != environment["id"]:
        raise ValueError(f"{case['id']}: unknown environment")
    fixture = environment["fixtures"][case["fixture_id"]]
    docs = {doc["doc_id"]: dict(doc) for doc in manifest}
    if len(docs) != len(manifest):
        raise ValueError("Duplicate manifest doc_id")
    for doc in fixture.get("additional_documents", []):
        if doc["doc_id"] in docs:
            raise ValueError("Fixture addition reuses a doc_id")
        docs[doc["doc_id"]] = dict(doc)
    for id_, override in fixture.get("document_overrides", {}).items():
        docs[id_].update(override)
    for doc in docs.values():
        path = (eval_root / doc["path"]).resolve()
        if not path.is_relative_to(eval_root.resolve()) or not path.is_file():
            raise ValueError(f"{case['id']}: missing or out-of-scope path for {doc['doc_id']}")
    return docs


def validate_row(row, case, docs):
    id_ = case["id"]
    if set(row) != ANNOTATION_FIELDS or row.get("id") != id_:
        raise ValueError(f"{id_}: expected exactly {sorted(ANNOTATION_FIELDS)}")
    if not isinstance(row["action"], str) or row["action"] not in ACTIONS:
        raise ValueError(f"{id_}: invalid action")
    for field in ("relevant_doc_ids", "clarify_candidates"):
        ids = row[field]
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            raise ValueError(f"{id_}: {field} must be an array of doc IDs")
        if len(set(ids)) != len(ids):
            raise ValueError(f"{id_}: duplicate documents in {field}")
        for doc_id in ids:
            doc = docs.get(doc_id)
            if not doc or doc["owner_id"] != case["user_id"] or not doc.get("searchable", False):
                raise ValueError(f"{id_}: unknown, forbidden or unsearchable document {doc_id}")
    if row["action"] == "search":
        if not row["relevant_doc_ids"] or row["clarify_candidates"]:
            raise ValueError(f"{id_}: search needs results and no clarification candidates")
    elif row["relevant_doc_ids"]:
        raise ValueError(f"{id_}: only search may have results")
    if row["action"] != "clarify" and row["clarify_candidates"]:
        raise ValueError(f"{id_}: only clarify may have candidates")
    if type(row["has_more"]) is not bool or row["has_more"] != (len(row["relevant_doc_ids"]) > 5):
        raise ValueError(f"{id_}: has_more must equal result count > 5")
    if not isinstance(row["order_by"], str) or row["order_by"] not in ORDERS:
        raise ValueError(f"{id_}: invalid order_by")
    filters = row["filters"]
    if not isinstance(filters, dict) or filters.keys() - FILTERS:
        raise ValueError(f"{id_}: invalid filter keys")
    for key, value in filters.items():
        if key not in {"uploaded_at", "content_date"}:
            if not isinstance(value, str) or not value:
                raise ValueError(f"{id_}: {key} must be a nonempty string")
            continue
        allowed = {"gte", "lt", "event"} if key == "content_date" else {"gte", "lt"}
        if not isinstance(value, dict) or value.keys() - allowed or not {"gte", "lt"} <= value.keys():
            raise ValueError(f"{id_}: {key} needs gte/lt date boundaries")
        for bound in ("gte", "lt"):
            if not isinstance(value[bound], str) or date.fromisoformat(value[bound]).isoformat() != value[bound]:
                raise ValueError(f"{id_}: noncanonical date")
        if value["gte"] >= value["lt"]:
            raise ValueError(f"{id_}: invalid date range")
        if "event" in value and (not isinstance(value["event"], str) or not value["event"]):
            raise ValueError(f"{id_}: invalid content event")


def validate_file(path, cases, manifest, environment, eval_root):
    rows = load_jsonl(path)
    if {row["id"] for row in rows} != set(cases):
        raise ValueError(f"{path}: missing/extra case IDs")
    for row in rows:
        case = cases[row["id"]]
        validate_row(row, case, effective_documents(case, manifest, environment, eval_root))
    return {row["id"]: row for row in rows}


def comparable(row):
    return {key: sorted(value) if key in {"relevant_doc_ids", "clarify_candidates"} else value
            for key, value in row.items()}


def validate_adjudication(path, a, b, final):
    rows = load_jsonl(path)
    disputed = {id_ for id_ in a if comparable(a[id_]) != comparable(b[id_])}
    reviewed = {row["id"] for row in rows}
    if not disputed <= reviewed or not reviewed <= a.keys():
        raise ValueError("Adjudication must cover all disputed cases and contain only known IDs")
    for row in rows:
        id_ = row["id"]
        if set(row) != {"id", "annotation_a", "annotation_b", "final", "comment"}:
            raise ValueError(f"{id_}: invalid adjudication fields")
        if row["annotation_a"] != a[id_] or row["annotation_b"] != b[id_]:
            raise ValueError(f"{id_}: adjudication changed an original annotation")
        if row["final"] != final[id_] or not isinstance(row["comment"], str) or not row["comment"].strip():
            raise ValueError(f"{id_}: missing decision or comment")
        if id_ not in disputed and comparable(final[id_]) == comparable(a[id_]):
            raise ValueError(f"{id_}: an agreed case needs an actual correction to enter adjudication")
    for id_ in set(a) - reviewed:
        if comparable(final[id_]) != comparable(a[id_]):
            raise ValueError(f"{id_}: silent change to an agreed annotation")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--eval-root", type=Path, default=ROOT)
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--check-adjudication", action="store_true")
    parser.add_argument("--annotator-a", type=Path, help="Original A for adjudication checks")
    parser.add_argument("--annotator-b", type=Path, help="Original B for adjudication checks")
    args = parser.parse_args()
    root = args.eval_root
    folder = root / "annotation"
    cases = validate_blind(args.blind or folder / "blind_cases.jsonl")
    manifest = [json.loads(line) for line in (root / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    environment = json.loads((root / "fixtures/environment.json").read_text(encoding="utf-8"))
    originals = [args.annotator_a or folder / "annotator_a.jsonl",
                 args.annotator_b or folder / "annotator_b.jsonl", folder / "final_gold.jsonl"]
    files = args.files or originals
    for path in files:
        validate_file(path, cases, manifest, environment, root)
        print(f"Valid: {path.name} ({len(cases)} cases)")
    if args.check_adjudication:
        a, b, final = [validate_file(path, cases, manifest, environment, root) for path in originals]
        rows = validate_adjudication(folder / "adjudication.jsonl", a, b, final)
        disputed = sum(comparable(a[id_]) != comparable(b[id_]) for id_ in a)
        print(f"Valid adjudication: {disputed} disputes, {len(rows) - disputed} agreed-case corrections; original A/B preserved")


if __name__ == "__main__":
    main()
