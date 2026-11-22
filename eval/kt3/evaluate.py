"""Общий отчёт по сохранённым результатам. Систему и бейзлайны запускает runner."""
import argparse
import hashlib
import json
from pathlib import Path

from .common import aggregate_cases, index_rows, merge_cases, read_jsonl, output_hash
from .contracts import score_contracts, score_scenarios
from .ingestion import manual_review_template, score_ingestion
from .judge import build_tasks, PROMPT_PATH
from .search import score_search, score_typos
from .telemetry import cost, latency

ROOT = Path(__file__).resolve().parents[1]


def check_ids(rows, allowed, label):
    unknown = index_rows(rows, label).keys() - set(allowed)
    if unknown:
        raise ValueError(f"{label}: unknown case ids {sorted(unknown)}")


def cost_for_cases(cases, outputs):
    indexed = index_rows(outputs, "outputs")
    return cost([indexed.get(c["id"], {"id": c["id"]}) for c in cases])


def evaluate(cases, predictions, documents, environment, *, clean_predictions=None,
             ingestion_cases=None, ingestion_outputs=None, ingestion_gold=None,
             reviews=None, ingestion_timeout_s=None, scenarios=None, scenario_outputs=None):
    reviews = reviews or []
    check_ids(predictions, index_rows(cases), "predictions")
    available = index_rows(predictions + (ingestion_outputs or []), "all outputs")
    judge_tasks = {t["id"]: t for t in build_tasks(cases, predictions, documents, environment)} if any(
        r.get("kind") == "messages" for r in reviews) else {}
    prompt_hash = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()
    metadata_gold = index_rows(ingestion_gold or [], "ingestion gold")
    seen_reviews = set()
    for review in reviews:
        key = (review.get("id"), review.get("kind"))
        if not all(isinstance(v, str) for v in key) or key[1] not in {"messages", "metadata"}:
            raise ValueError("review: expected string id and kind messages/metadata")
        if key in seen_reviews:
            raise ValueError(f"Duplicate review {key}")
        seen_reviews.add(key)
        if key[0] not in available or review.get("output_sha256") != output_hash(available[key[0]]):
            raise ValueError(f"{key[0]}: review has no matching current output")
        if key[1] == "messages":
            task = judge_tasks.get(key[0])
            if (task is None or task["judge_input_sha256"] != review.get("judge_input_sha256")
                    or review.get("prompt_sha256") != prompt_hash):
                raise ValueError(f"{key[0]}: judge input or prompt changed; rerun judge")
        elif (key[0] not in metadata_gold
              or review.get("gold_sha256") != output_hash(metadata_gold[key[0]])):
            raise ValueError(f"{key[0]}: metadata criteria changed; repeat review")
    rows = {}
    merge_cases(rows, score_search(cases, predictions, documents, environment, reviews))
    merge_cases(rows, score_contracts(cases, predictions, documents, environment))
    merge_cases(rows, score_typos(cases, predictions, clean_predictions))
    datasets = {case["id"]: "search" for case in cases}
    if ingestion_cases is not None:
        if ingestion_timeout_s is None:
            raise ValueError("--ingestion-timeout-s is required for ingestion evaluation")
        check_ids(ingestion_outputs or [], index_rows(ingestion_cases), "ingestion outputs")
        merge_cases(rows, score_ingestion(ingestion_cases, ingestion_outputs or [], ingestion_gold or [],
                                         reviews, ingestion_timeout_s))
        datasets.update({case["id"]: "ingestion" for case in ingestion_cases})
    if scenarios is not None:
        check_ids(scenario_outputs or [], index_rows(scenarios), "scenario outputs")
        merge_cases(rows, score_scenarios(scenarios, scenario_outputs or []))
        datasets.update({case["id"]: "scenario" for case in scenarios})
    for id_, row in rows.items():
        row["dataset"] = datasets.get(id_, "search")
    categories = sorted({c["category"] for c in cases})
    report = {
        "schema_version": 1,
        **aggregate_cases(rows),
        "by_category": {category: aggregate_cases({c["id"]: rows[c["id"]]
                        for c in cases if c["category"] == category}) for category in categories},
        "by_gold_action": {action: aggregate_cases({c["id"]: rows[c["id"]]
                           for c in cases if c["expected"]["action"] == action})
                           for action in ("search", "clarify", "no_result", "refuse")},
        "cases": rows,
        "latency": {"search": latency(cases, predictions, {"search", "clarify", "no_result", "refuse"})},
        "cost": {"search": cost_for_cases(cases, predictions)},
        "not_run": [],
    }
    if clean_predictions is not None:
        report["cost"]["clean_queries"] = cost_for_cases(
            [c for c in cases if c.get("variant_type") == "typo"], clean_predictions)
    else:
        report["not_run"].append("clean_queries")
    if ingestion_cases is not None:
        valid = [c for c in ingestion_cases if c["expected"]["action"] == "ingest"]
        report["latency"]["ingestion"] = latency(valid, ingestion_outputs or [], {"ingest"})
        report["cost"]["ingestion"] = cost_for_cases(ingestion_cases, ingestion_outputs or [])
        report["ingestion_timeout_s"] = ingestion_timeout_s
    else:
        report["not_run"].append("ingestion")
    if scenarios is None:
        report["not_run"].append("scenarios")
    else:
        # Runner supplies totals covering every step and retry of a scenario.
        report["cost"]["scenarios"] = cost_for_cases(scenarios, scenario_outputs or [])
    judges = [{"id": r["id"], "llm_usage": {"complete": True,
               "calls": [{"model": r.get("actual_model") or r.get("model"), **(r.get("usage") or {})}]}}
              for r in reviews if r.get("kind") == "messages"]
    report["cost"]["judge"] = cost(judges)
    return report


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Run metadata supplied by runner")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "queries/dev.jsonl")
    parser.add_argument("--documents", type=Path, default=ROOT / "documents.jsonl")
    parser.add_argument("--environment", type=Path, default=ROOT / "fixtures/environment.json")
    parser.add_argument("--clean-predictions", type=Path)
    parser.add_argument("--ingestion-outputs", type=Path)
    parser.add_argument("--ingestion-cases", type=Path, default=ROOT / "queries/ingestion.jsonl")
    parser.add_argument("--ingestion-gold", type=Path, default=ROOT / "ingestion/gold.jsonl")
    parser.add_argument("--ingestion-timeout-s", type=float)
    parser.add_argument("--reviews", type=Path, action="append", default=[])
    parser.add_argument("--export-metadata-review", type=Path)
    parser.add_argument("--scenario-outputs", type=Path)
    parser.add_argument("--scenarios", type=Path, default=Path(__file__).with_name("scenarios.json"))
    args = parser.parse_args()
    try:
        run = load_json(args.run)
        for key in ("run_id", "variant", "git_commit"):
            if not isinstance(run.get(key), str) or not run[key].strip():
                raise ValueError(f"run metadata: {key} is required")
        for key in ("model", "temperature", "seed", "prompts"):
            if key not in run:
                raise ValueError(f"run metadata: {key} must be recorded (null if not applicable)")
        if not isinstance(run["prompts"], list) or any(
            not isinstance(p, dict) or not isinstance(p.get("name"), str)
            or not isinstance(p.get("text"), str) for p in run["prompts"]):
            raise ValueError("run metadata: prompts must contain name and exact text")
        cases, predictions = read_jsonl(args.cases), read_jsonl(args.predictions)
        reviews = [row for path in args.reviews for row in read_jsonl(path)]
        ingestion_cases = read_jsonl(args.ingestion_cases) if args.ingestion_outputs else None
        ingestion_outputs = read_jsonl(args.ingestion_outputs) if args.ingestion_outputs else None
        ingestion_gold = read_jsonl(args.ingestion_gold) if args.ingestion_outputs else None
        scenarios_data = load_json(args.scenarios) if args.scenario_outputs else None
        scenarios = scenarios_data.get("scenarios", scenarios_data) if isinstance(scenarios_data, dict) else scenarios_data
        result = evaluate(cases, predictions, read_jsonl(args.documents), load_json(args.environment),
                          clean_predictions=read_jsonl(args.clean_predictions) if args.clean_predictions else None,
                          ingestion_cases=ingestion_cases, ingestion_outputs=ingestion_outputs,
                          ingestion_gold=ingestion_gold, reviews=reviews,
                          ingestion_timeout_s=args.ingestion_timeout_s, scenarios=scenarios,
                          scenario_outputs=read_jsonl(args.scenario_outputs) if args.scenario_outputs else None)
        result["run"] = run
        used = [args.run, args.cases, args.documents, args.environment, args.predictions, *args.reviews]
        used += [p for p in (args.clean_predictions, args.ingestion_outputs, args.scenario_outputs) if p]
        if args.ingestion_outputs:
            used += [args.ingestion_cases, args.ingestion_gold]
        if args.scenario_outputs:
            used += [args.scenarios]
        result["input_sha256"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in used}
        if args.export_metadata_review:
            if ingestion_cases is None:
                raise ValueError("--export-metadata-review needs --ingestion-outputs")
            with args.export_metadata_review.open("x", encoding="utf-8") as stream:
                for row in manual_review_template(ingestion_cases, ingestion_outputs, ingestion_gold):
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Cannot evaluate: {exc}\n")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
