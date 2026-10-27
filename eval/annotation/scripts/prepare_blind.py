#!/usr/bin/env python3
"""Select the predeclared cases using a strict allowlist; never export gold fields."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_IDS = "E06 E15 E20 E21 E24 E27 E31 E35 E38 E41 E43 E46 E48 E55 E57 E58 E61 E63 E69 E72 E74 E78 E79 E82 E87 E89 E91 E93 E133 E135".split()
FIELDS = "id query context user_id now timezone fixture_id environment_id".split()


def load_jsonl(path):
    rows = []
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{number}: blank line")
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"{path}:{number}: expected object with string id")
        if row["id"] in seen:
            raise ValueError(f"{path}:{number}: duplicate id {row['id']}")
        seen.add(row["id"])
        rows.append(row)
    return rows


def prepare(source, output):
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError("Blind output must not overwrite the source dataset")
    rows = {row["id"]: row for row in load_jsonl(source)}
    missing = set(CASE_IDS) - rows.keys()
    if missing:
        raise ValueError(f"Missing cases: {sorted(missing)}")
    # Absent optional fields stay absent; do not invent context or environment values.
    selected = [{key: rows[id_][key] for key in FIELDS if key in rows[id_]} for id_ in CASE_IDS]
    Path(output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "queries/dev.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "annotation/blind_cases.jsonl")
    args = parser.parse_args()
    print(f"Prepared {len(prepare(args.source, args.output))} blind cases")
