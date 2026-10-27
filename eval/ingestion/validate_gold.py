#!/usr/bin/env python3
"""Validate ingestion evidence, metadata rubrics and links to the seven valid inputs."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from source_text import contains_quote, locate, normalize, units

ROOT = Path(__file__).resolve().parents[1]


def load_rows(path):
    rows, seen = [], set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in seen:
            raise ValueError(f"{path}:{number}: invalid or duplicate id")
        seen.add(row["id"])
        rows.append(row)
    return rows


def strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def validate_row(row, case, root):
    id_ = row["id"]
    if row.get("schema_version") != 1 or row.get("annotation_status") != "agent_annotated" or row.get("human_review_status") != "pending":
        raise ValueError(f"{id_}: unknown gold schema or annotation provenance")
    source = row["source"]
    if source["path"] != case["input"]["path"] or source["source_type"] != case["input"]["source_type"]:
        raise ValueError(f"{id_}: gold source differs from input")
    if source.get("source_url") != case["input"].get("source_url"):
        raise ValueError(f"{id_}: URL snapshot identity differs")
    path = (root / source["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"{id_}: missing or out-of-scope source")
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(f"{id_}: source SHA-256 mismatch")
    source_units = units(path)
    fragments = row["fragments"]
    if not isinstance(fragments, list) or not fragments:
        raise ValueError(f"{id_}: missing extraction fragments")
    seen, quotes = set(), set()
    for fragment in fragments:
        fid, quote = fragment["id"], fragment["quote"]
        if not isinstance(fid, str) or not fid or fid in seen or not isinstance(quote, str) or not normalize(quote):
            raise ValueError(f"{id_}: invalid fragment")
        if normalize(quote) in quotes:
            raise ValueError(f"{id_}: duplicate extraction evidence")
        if not contains_quote(locate(source_units, fragment["locator"]), quote):
            raise ValueError(f"{id_}/{fid}: quote not found at source locator")
        if not isinstance(fragment.get("purpose"), str) or not fragment["purpose"].strip():
            raise ValueError(f"{id_}/{fid}: missing selection rationale")
        seen.add(fid)
        quotes.add(normalize(quote))
    def evidence(value):
        if not strings(value) or set(value) - seen - {"source_format"}:
            raise ValueError(f"{id_}: invalid rubric evidence reference")
    for field in ("title", "description", "topic"):
        rubric = row["metadata"][field]
        if not isinstance(rubric.get("example"), str) or not rubric["example"].strip() or not strings(rubric.get("must_convey")) or not strings(rubric.get("must_not_claim")):
            raise ValueError(f"{id_}: incomplete {field} rubric")
        evidence(rubric["evidence"])
    added = row["metadata"]["uploaded_at"]
    if added != {"expected_local_date": datetime.fromisoformat(case["now"]).date().isoformat(),
                 "timezone": case["timezone"], "basis": "case.now"}:
        raise ValueError(f"{id_}: ingestion date must come from the fixed request clock")
    tags = row["tags"]
    aliases = {}
    for index, concept in enumerate(tags["accepted_concepts"]):
        if not isinstance(concept.get("label"), str) or not concept["label"].strip() or not strings(concept.get("aliases")):
            raise ValueError(f"{id_}: incomplete tag concept")
        evidence(concept["evidence"])
        for alias in concept["aliases"] + [concept["label"]]:
            key = normalize(alias)
            if key in aliases and aliases[key] != index:
                raise ValueError(f"{id_}: ambiguous tag alias")
            aliases[key] = index
    examples = tags["examples"]
    if (not strings(examples) or not 3 <= len(examples) <= 7
            or len({normalize(s) for s in examples}) != len(examples)
            or any(normalize(s) not in aliases for s in examples)
            or len({aliases[normalize(s)] for s in examples}) != len(examples)
            or not strings(tags.get("rejected_examples"))):
        raise ValueError(f"{id_}: invalid tag examples")
    return len(fragments)


def validate(root=ROOT):
    cases = load_rows(root / "queries/ingestion.jsonl")
    valid = {c["id"]: c for c in cases if c["expected"]["action"] == "ingest"}
    gold = load_rows(root / "ingestion/gold.jsonl")
    if {row["id"] for row in gold} != set(valid):
        raise ValueError("Gold must cover exactly all valid ingestion cases")
    fragments = 0
    for row in gold:
        case = valid[row["id"]]
        if (case["expected"].get("gold_ref") != f"ingestion/gold.jsonl#{row['id']}"
                or case["expected"].get("evidence_status") != "source_grounded_gold_available"
                or case.get("annotation_status") != "agent_annotated"):
            raise ValueError(f"{row['id']}: case gold link/status mismatch")
        fragments += validate_row(row, case, root)
    return len(gold), fragments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        count, fragments = validate(args.eval_root)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Invalid ingestion gold: {exc}\n")
    print(f"Valid: {count} inputs, {fragments} source-verified fragments; metadata/tag rubrics present; human review pending")


if __name__ == "__main__":
    main()
