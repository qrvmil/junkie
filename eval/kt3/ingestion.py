"""Ingestion metrics from runner observations and hash-bound human reviews."""

import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from eval.ingestion.source_text import contains_quote
from .common import cell, index_rows, output_hash, pending, review_for


FIELD_NAMES = {"title": "Title", "description": "Description", "topic": "Topic"}
VALID_METRICS = (
    "IngestionSuccessRate", "ExtractionCoverage", "MetadataCompleteness/mean",
    "MetadataCompleteness/FullPassRate", "MetadataCorrectness/Title",
    "MetadataCorrectness/Description", "MetadataCorrectness/Topic",
    "MetadataCorrectness/AddedDate", "TagRelevance",
)
INVALID_METRICS = {
    "invalid_format": "InvalidInput/Format",
    "invalid_size": "InvalidInput/Size",
    "corrupted": "InvalidInput/Corrupted",
}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _local_date(value, timezone):
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        if not re.match(r"\d{4}-\d{2}-\d{2}T", value):
            return None
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            return None
        return instant.astimezone(ZoneInfo(timezone)).date()
    except (ValueError, OverflowError):
        return None


def _present(value):
    return isinstance(value, str) and bool(value.strip())


def _and(checks):
    if any(item["status"] == "ok" and item["value"] == 0 for item in checks):
        return cell(0, "At least one required check failed")
    if any(item["status"] != "ok" for item in checks):
        return pending("Required observations or reviews are missing")
    return cell(1)


def _field_review(review, field):
    if review is None:
        return pending("Human metadata review is missing")
    fields = review.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("metadata review: fields must be an object")
    item = fields.get(field)
    if item is None or (isinstance(item, dict) and item.get("passed") is None):
        return pending(f"Human review of {field} is missing")
    if (not isinstance(item, dict) or type(item.get("passed")) is not bool
            or not _present(item.get("reason"))):
        raise ValueError(f"metadata review: {field} needs boolean passed and a reason")
    return cell(int(item["passed"]), item["reason"])


def _tags(tags, review):
    if not isinstance(tags, list) or not tags:
        return cell(0, "No valid tag list"), cell(0, "No tags")
    if any(not _present(tag) for tag in tags):
        return cell(0, "Tags must be nonempty strings"), cell(0, "Invalid tag list")
    count_check = cell(0, "Fewer than three tags") if len(tags) < 3 else None
    if review is None or review.get("tags") is None:
        return count_check or pending("Distinct tag concepts need human review"), pending("Tags need human review")
    judgments = review["tags"]
    if not isinstance(judgments, list):
        raise ValueError("metadata review: tags must be a list")
    indexed = {}
    for judgment in judgments:
        if (not isinstance(judgment, dict) or type(judgment.get("tag_index")) is not int
                or not 0 <= judgment["tag_index"] < len(tags)
                or judgment["tag_index"] in indexed):
            raise ValueError("metadata review: invalid or duplicate tag_index")
        indexed[judgment["tag_index"]] = judgment
    complete = len(indexed) == len(tags)
    for item in indexed.values():
        if item.get("supported") is not None and type(item["supported"]) is not bool:
            raise ValueError("metadata review: supported must be boolean")
        if item.get("concept_id") is not None and not isinstance(item["concept_id"], str):
            raise ValueError("metadata review: concept_id must be a string")
        if item.get("supported") is None or not item.get("concept_id"):
            complete = False
        elif (type(item["supported"]) is not bool or not _present(item["concept_id"])
              or not _present(item.get("reason"))):
            raise ValueError("metadata review: every tag needs supported, concept_id and reason")
    if not complete:
        return count_check or pending("Tag concept review is incomplete"), pending("Tag review is incomplete")
    concepts = {item["concept_id"].strip() for item in indexed.values()}
    return (cell(int(3 <= len(concepts) <= 7), f"{len(concepts)} distinct concepts"),
            cell(sum(item["supported"] for item in indexed.values()) / len(tags)))


def _observations(output, timeout_s):
    observations = output.get("observations", {})
    if not isinstance(observations, dict):
        observations = {}
    checks = {}
    for name in ("source_saved", "source_openable", "searchable"):
        value = observations.get(name)
        checks[name] = cell(int(value)) if type(value) is bool else pending(f"Missing runner observation: {name}")
    checks["text_extracted"] = cell(int(_present(output.get("extracted_text"))))
    elapsed = output.get("elapsed_ms")
    checks["within_ingestion_timeout"] = (
        cell(int(elapsed <= timeout_s * 1000)) if _number(elapsed)
        else pending("Missing or invalid elapsed_ms")
    )
    return checks


def _model_gate(output):
    usage = output.get("llm_usage")
    if not isinstance(usage, dict):
        return pending("Complete runner LLM usage is required")
    calls = usage.get("calls")
    if isinstance(calls, list) and calls:
        return cell(0, f"{len(calls)} model calls observed")
    if usage.get("complete") is not True:
        return pending("Complete runner LLM usage is required")
    if not isinstance(calls, list):
        return pending("Missing LLM call list")
    return cell(int(not calls), f"{len(calls)} model calls")


def score_ingestion(cases, outputs, gold, reviews, ingestion_timeout_s):
    if not _number(ingestion_timeout_s) or ingestion_timeout_s == 0:
        raise ValueError("ingestion_timeout_s must be a positive finite number")
    cases, outputs, gold = (index_rows(rows, label) for rows, label in (
        (cases, "ingestion cases"), (outputs, "ingestion outputs"), (gold, "ingestion gold")))
    if not cases or outputs.keys() - cases.keys():
        raise ValueError("Empty ingestion set or unknown output IDs")
    result = {}
    for id_, case in cases.items():
        output = outputs.get(id_)
        expected = case["expected"]
        valid = expected["action"] == "ingest"
        names = VALID_METRICS if valid else (INVALID_METRICS[case["category"]],)
        if output is None or output.get("status") != "ok":
            reason = "Missing output" if output is None else f"Output status: {output.get('status')}"
            result[id_] = {"metrics": {name: cell(0, reason) for name in names}, "checks": {}}
            continue
        if not valid:
            checks = {
                "input_action": cell(int(output.get("action") == "reject")),
                "input_reason": cell(int(output.get("reason") == expected["reason"])),
            }
            if expected.get("model_calls") == 0:
                checks["model_gate"] = _model_gate(output)
            result[id_] = {"metrics": {names[0]: _and(list(checks.values()))}, "checks": checks}
            continue
        if output.get("action") != "ingest":
            result[id_] = {"metrics": {name: cell(0, "Expected action=ingest") for name in names}, "checks": {}}
            continue
        if id_ not in gold:
            raise ValueError(f"{id_}: missing ingestion gold")
        reference = gold[id_]
        review = review_for(reviews, output, "metadata")
        if review is not None and not _present(review.get("reviewer")):
            raise ValueError(f"{id_}: metadata review requires reviewer")
        checks = _observations(output, ingestion_timeout_s)
        metrics = {"IngestionSuccessRate": _and(list(checks.values()))}
        fragments = reference.get("fragments")
        if (not isinstance(fragments, list) or not fragments
                or any(not isinstance(f, dict) or not _present(f.get("quote")) for f in fragments)):
            raise ValueError(f"{id_}: invalid extraction fragments")
        text = output.get("extracted_text")
        matched = sum(contains_quote(text, fragment["quote"]) for fragment in fragments) if isinstance(text, str) else 0
        metrics["ExtractionCoverage"] = cell(matched / len(fragments))
        metadata = output.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        completeness = []
        for field, metric_name in FIELD_NAMES.items():
            present = _present(metadata.get(field))
            completeness.append(cell(int(present)))
            metrics[f"MetadataCorrectness/{metric_name}"] = (
                _field_review(review, field) if present else cell(0, f"Missing {field}")
            )
        tags_complete, tags_relevant = _tags(metadata.get("tags"), review)
        completeness.append(tags_complete)
        actual_date = _local_date(metadata.get("uploaded_at"), case["timezone"])
        expected_date = _local_date(case["now"], case["timezone"])
        if expected_date is None:
            raise ValueError(f"{id_}: invalid case clock")
        completeness.append(cell(int(actual_date is not None)))
        metrics["MetadataCorrectness/AddedDate"] = cell(int(actual_date == expected_date))
        metrics["MetadataCompleteness/mean"] = (
            cell(sum(item["value"] for item in completeness) / 5)
            if all(item["status"] == "ok" for item in completeness)
            else pending("Tag concept review is required to finish completeness")
        )
        metrics["MetadataCompleteness/FullPassRate"] = _and(completeness)
        metrics["TagRelevance"] = tags_relevant
        for name, value in zip(("title", "description", "topic", "tags", "uploaded_at"), completeness):
            checks[f"metadata_present/{name}"] = value
        result[id_] = {"metrics": metrics, "checks": checks}
    return result


def manual_review_template(cases, outputs, gold):
    cases, outputs, gold = (index_rows(rows, label) for rows, label in (
        (cases, "ingestion cases"), (outputs, "ingestion outputs"), (gold, "ingestion gold")))
    if outputs.keys() - cases.keys():
        raise ValueError("Unknown ingestion output IDs")
    templates = []
    for id_, case in cases.items():
        output = outputs.get(id_)
        if (case["expected"]["action"] != "ingest" or output is None
                or output.get("status") != "ok" or output.get("action") != "ingest"):
            continue
        reference = gold[id_]
        metadata = output.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        templates.append({
            "id": id_, "kind": "metadata", "output_sha256": output_hash(output),
            "status": "pending", "reviewer": "", "source": reference["source"],
            "metadata": metadata,
            "fields": {field: {"passed": None, "reason": "", "criteria": reference["metadata"][field]}
                       for field in FIELD_NAMES if _present(metadata.get(field))},
            "tag_criteria": reference["tags"],
            "tags": [{"tag_index": index, "tag": tag, "supported": None, "concept_id": "", "reason": ""}
                     for index, tag in enumerate(tags)],
        })
    return templates
