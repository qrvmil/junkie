"""JSONL, оценки отдельных кейсов и привязка проверок к ответам."""
import hashlib
import json
import math
from pathlib import Path


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{number}: empty JSONL row")
        try:
            row = json.loads(line, parse_constant=_invalid_constant)
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: expected object")
        rows.append(row)
    return rows


def index_rows(rows, label="rows"):
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError(f"{label}: nonempty string id required")
        if row["id"] in result:
            raise ValueError(f"{label}: duplicate id {row['id']}")
        result[row["id"]] = row
    return result


def output_hash(row):
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cell(value, reason=""):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A scored cell needs a finite number")
    result = {"status": "ok", "value": float(value)}
    if reason:
        result["reason"] = reason
    return result


def pending(reason):
    return {"status": "pending", "value": None, "reason": reason}


def na(reason):
    return {"status": "not_applicable", "value": None, "reason": reason}


def summarize(cells):
    cells = list(cells)
    scored = [c["value"] for c in cells if c["status"] == "ok"]
    waiting = sum(c["status"] == "pending" for c in cells)
    excluded = sum(c["status"] == "not_applicable" for c in cells)
    total = math.fsum(scored)
    return {
        "status": "pending" if waiting else "ok" if scored else "not_applicable",
        "value": None if waiting or not scored else total / len(scored),
        "sum_scored": total, "eligible": len(scored) + waiting,
        "scored": len(scored), "pending": waiting, "not_applicable": excluded,
    }


def review_for(reviews, output, kind):
    if output is None:
        return None
    matched = [r for r in reviews if r.get("id") == output["id"] and r.get("kind") == kind]
    if len(matched) > 1:
        raise ValueError(f"{output['id']}: duplicate {kind} review")
    if not matched:
        return None
    review = matched[0]
    if review.get("output_sha256") != output_hash(output):
        raise ValueError(f"{output['id']}: stale {kind} review; output changed")
    return review if review.get("status") == "ok" else None


def merge_cases(target, source):
    for id_, row in source.items():
        dest = target.setdefault(id_, {"metrics": {}, "checks": {}})
        for group in ("metrics", "checks"):
            overlap = dest[group].keys() & row.get(group, {}).keys()
            if overlap:
                raise ValueError(f"{id_}: duplicate {group}: {sorted(overlap)}")
            dest[group].update(row.get(group, {}))


def aggregate_cases(rows):
    result = {}
    for group in ("metrics", "checks"):
        names = sorted({name for row in rows.values() for name in row[group]})
        result[group] = {
            name: summarize(row[group][name] for row in rows.values() if name in row[group])
            for name in names
        }
    return result
