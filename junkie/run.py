"""Один запуск B0, B1 или Junkie на открытом наборе КТ3."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

from eval.kt3.common import read_jsonl
from eval.kt3.evaluate import evaluate
from eval.kt3.ingestion import manual_review_template
from eval.kt3.judge import build_tasks, validate_judgment, PROMPT_PATH
from eval.kt3.telemetry import cost

ROOT = Path(__file__).resolve().parents[1]
SMOKE_IDS = ("E01", "E19", "E22", "E57", "E87", "E89", "E132", "E133")


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_jsonl(path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()


def select_cases(cases, limit=None, case_ids=None):
    """Smoke IDs are fixed before any measurements; full runs preserve dev order."""
    if limit is not None and case_ids:
        raise ValueError("Use either --limit or --case-ids")
    indexed = {case["id"]: case for case in cases}
    if case_ids:
        ids = case_ids.split(",")
        if len(set(ids)) != len(ids) or any(id_ not in indexed for id_ in ids):
            raise ValueError("--case-ids contains duplicate or unknown IDs")
        return [indexed[id_] for id_ in ids]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        preferred = [id_ for id_ in SMOKE_IDS if id_ in indexed]
        preferred.extend(case["id"] for case in cases if case["id"] not in preferred)
        return [indexed[id_] for id_ in preferred[:limit]]
    return list(cases)


def safe_call(call, *, id_, client=None):
    started = time.perf_counter()
    first_call = len(client.calls) if client else 0
    try:
        row = call()
        if not isinstance(row, dict):
            raise ValueError("Service returned a non-object")
        row = copy.deepcopy(row)
    except Exception as exc:
        # Do not serialize exception text: API errors may include request details.
        row = {"status": "error", "error_type": type(exc).__name__,
               "response": "Не удалось выполнить запрос.", "result_doc_ids": []}
    row["id"] = id_
    row.setdefault("elapsed_ms", (time.perf_counter() - started) * 1000)
    row.setdefault("llm_usage", {"complete": True,
                                  "calls": copy.deepcopy(client.calls[first_call:]) if client else []})
    return row


def search_rows(cases, archives, service_factory, variant, client, clean=False, *, ingestion_timeout_s):
    for case in cases:
        if clean and case.get("variant_type") != "typo":
            continue
        service = service_factory(archives[case.get("fixture_id", "base")].clone(), variant, client=client,
                                  ingestion_timeout_s=ingestion_timeout_s)
        query = case["clean_query"] if clean else case["query"]
        # No case ID, expected labels or expected tool calls enter Service.
        yield safe_call(lambda: service.query(query=query, user_id=case["user_id"], now=case["now"],
                         timezone=case["timezone"], context=copy.deepcopy(case.get("context", []))),
                        id_=case["id"], client=client)


def ingestion_rows(cases, archives, service_factory, variant, client, *, ingestion_timeout_s):
    for case in cases:
        service = service_factory(archives[case.get("fixture_id", "base")].clone(), variant, client=client,
                                  ingestion_timeout_s=ingestion_timeout_s)
        yield safe_call(lambda: service.ingest(input=copy.deepcopy(case["input"]), user_id=case["user_id"],
                                               now=case["now"]), id_=case["id"], client=client)


def run_scenario(spec, archive, service_factory, variant, client, *, ingestion_timeout_s):
    archive = archive.clone()
    # A scenario that uploads an assigned ID starts without that ID. This is
    # setup from its input, not a successful observation copied from an assert.
    assigned = [t["input"]["assigned_doc_id"] for t in spec["turns"]
                if "input" in t and "assigned_doc_id" in t["input"]]
    for doc_id in assigned:
        archive = archive.without(doc_id)
    initial = {"absent_doc_ids": [doc_id for doc_id in assigned if doc_id not in archive.documents]}
    fault = copy.deepcopy(spec.get("fault"))
    if spec.get("persistent_fault"):
        fault = dict(spec["persistent_fault"], persistent=True)
    service = service_factory(archive, variant, client=client, max_tool_calls=spec["max_steps"], fault=fault,
                              ingestion_timeout_s=ingestion_timeout_s)
    history, steps = [], []
    started = time.perf_counter()
    for number, turn in enumerate(spec["turns"], 1):
        if "input" in turn:
            input_ = copy.deepcopy(turn["input"])
            doc_id = input_.pop("assigned_doc_id", None)
            row = safe_call(lambda: service.ingest(input=input_, user_id=spec["user_id"],
                            now=spec["now"], doc_id=doc_id), id_=f"{spec['id']}:{number}", client=client)
        else:
            row = safe_call(lambda: service.query(query=turn["user"], user_id=spec["user_id"],
                            now=spec["now"], timezone=spec["timezone"], context=copy.deepcopy(history)),
                            id_=f"{spec['id']}:{number}", client=client)
            history.append({"role": "user", "content": turn["user"]})
        steps.append(row)
        history.append({"role": "assistant", "content": row.get("response", ""),
                        "result_doc_ids": list(row.get("result_doc_ids") or [])})
        if getattr(service, "termination_reason", None) == "budget_exhausted":
            break
    return {"id": spec["id"], "status": "ok", "steps": steps,
            "termination_reason": getattr(service, "termination_reason", "completed"),
            "initial_observations": initial, "elapsed_ms": (time.perf_counter() - started) * 1000,
            "llm_usage": {"complete": all(s.get("llm_usage", {}).get("complete") is True for s in steps),
                          "calls": [call for s in steps for call in s.get("llm_usage", {}).get("calls", [])]}}


def judge_rows(cases, outputs, documents, environment, client):
    from .openrouter import ModelError
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    for task in build_tasks(cases, outputs, documents, environment):
        first_call = len(client.calls)
        row = {key: value for key, value in task.items() if key != "judge_input"}
        row.update(status="error", model=client.model, temperature=0, max_output_tokens=1200,
                   prompt_sha256=prompt_hash)
        try:
            judgment = client.complete_json([
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(task["judge_input"], ensure_ascii=False)}],
                max_tokens=1200, purpose="judge")
            row["raw_judgment"] = json.dumps(judgment, ensure_ascii=False)
            row["checks"] = validate_judgment(judgment, task["judge_input"]["requested_checks"])
            row["status"] = "ok"
        except ModelError as exc:
            row.update(error_type="ModelError", error_code=exc.code)
        except Exception as exc:
            row["error_type"] = type(exc).__name__
        calls = client.calls[first_call:]
        row["usage"] = {key: calls[-1].get(key) if calls else 0
                        for key in ("input_tokens", "output_tokens", "cost_usd")}
        row["generation_id"] = calls[-1].get("generation_id") if calls else None
        row["actual_model"] = (calls[-1].get("actual_model") or calls[-1].get("model")) if calls else client.model
        yield row


def metadata(variant, model, config, repeat):
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    prompts = []
    if variant == "Junkie":
        for path in sorted((ROOT / "junkie/prompts").glob("*.txt")):
            prompts.append({"name": path.stem, "text": path.read_text(encoding="utf-8")})
    return {"run_id": f"{variant.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{repeat}",
            "variant": variant, "git_commit": commit, "model": model if variant == "Junkie" else None,
            "temperature": 0 if variant == "Junkie" else None, "seed": None,
            "prompts": prompts, "config": dict(config, dirty_worktree=dirty, repeat=repeat)}


def run_once(args, directory, repeat, client, *, archive_factory=None, service_factory=None):
    run_started = time.perf_counter()
    if archive_factory is None:
        from .archive import build_archive
        archive_factory = build_archive
    if service_factory is None:
        from .service import Service
        service_factory = Service
    directory.mkdir(parents=True, exist_ok=False)
    root = args.eval_root
    documents_path, environment_path = root / "documents.jsonl", root / "fixtures/environment.json"
    documents = read_jsonl(documents_path)
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    cases = select_cases(read_jsonl(root / "queries/dev.jsonl"), args.limit, args.case_ids)
    ingestion_cases = [] if args.skip_ingestion else read_jsonl(root / "queries/ingestion.jsonl")
    ingestion_gold = [] if args.skip_ingestion else read_jsonl(root / "ingestion/gold.jsonl")
    specs_path = root / "kt3/scenarios.json"
    specs = json.loads(specs_path.read_text(encoding="utf-8"))["scenarios"] if args.scenarios else []
    fixture_ids = {c.get("fixture_id", "base") for c in cases + ingestion_cases + specs}
    started = time.perf_counter()
    archives = {id_: archive_factory(root, documents, environment["fixtures"][id_]) for id_ in sorted(fixture_ids)}
    preparation = {"elapsed_ms": (time.perf_counter() - started) * 1000,
                   "fixtures": {id_: archive.preparation for id_, archive in archives.items()},
                   "llm_usage": {"complete": True, "calls": []}}
    config = {"fixture_version": environment["id"], "cache": "fixture extraction cached within process; ingestion always reparsed",
              "budget_usd": args.budget_usd, "max_calls": args.max_calls,
              "ingestion_timeout_s": args.ingestion_timeout_s,
              "search_case_ids": [c["id"] for c in cases], "judge_model": args.model if args.judge else None,
              "max_tool_calls_per_case": 8, "max_model_calls_per_case": 4, "tool_timeout_s": 10,
              "input_price_per_million": getattr(client, "input_price", None),
              "output_price_per_million": getattr(client, "output_price", None),
              "api_timeout_s": getattr(client, "timeout", None),
              "reasoning_effort": getattr(client, "reasoning_effort", None),
              "scenario_budgets": {s["id"]: s["max_steps"] for s in specs}}
    run = metadata(args.variant, args.model, config, repeat)
    write_json(directory / "run.json", run)
    write_json(directory / "preparation.json", preparation)
    write_jsonl(directory / "cases.jsonl", cases)
    write_jsonl(directory / "search.jsonl", search_rows(cases, archives, service_factory, args.variant, client,
                 ingestion_timeout_s=args.ingestion_timeout_s))
    predictions = read_jsonl(directory / "search.jsonl")
    write_jsonl(directory / "clean.jsonl", search_rows(cases, archives, service_factory, args.variant, client, clean=True,
                 ingestion_timeout_s=args.ingestion_timeout_s))
    clean = read_jsonl(directory / "clean.jsonl")
    write_jsonl(directory / "ingestion.jsonl", ingestion_rows(ingestion_cases, archives, service_factory, args.variant, client,
                 ingestion_timeout_s=args.ingestion_timeout_s))
    ingested = read_jsonl(directory / "ingestion.jsonl")
    write_jsonl(directory / "scenarios.jsonl", (run_scenario(s, archives[s["fixture_id"]], service_factory,
                 args.variant, client, ingestion_timeout_s=args.ingestion_timeout_s) for s in specs))
    scenarios = read_jsonl(directory / "scenarios.jsonl")
    write_jsonl(directory / "messages.jsonl", judge_rows(cases, predictions, documents, environment, client)
                if args.judge else [])
    reviews = read_jsonl(directory / "messages.jsonl")
    write_jsonl(directory / "metadata-review.jsonl", manual_review_template(ingestion_cases, ingested, ingestion_gold)
                if ingestion_cases else [])
    report = evaluate(cases, predictions, documents, environment, clean_predictions=clean,
                      ingestion_cases=ingestion_cases or None, ingestion_outputs=ingested,
                      ingestion_gold=ingestion_gold, ingestion_timeout_s=args.ingestion_timeout_s, reviews=reviews,
                      scenarios=specs or None, scenario_outputs=scenarios)
    report["run"] = run
    report["preparation"] = preparation
    paths = [documents_path, environment_path, root / "queries/dev.jsonl",
             *[directory / name for name in ("run.json", "cases.jsonl", "search.jsonl", "clean.jsonl",
                                             "ingestion.jsonl", "scenarios.jsonl", "messages.jsonl")]]
    if ingestion_cases:
        paths.extend([root / "queries/ingestion.jsonl", root / "ingestion/gold.jsonl"])
    if specs:
        paths.append(specs_path)
    report["input_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    report["run_elapsed_ms"] = (time.perf_counter() - run_started) * 1000
    write_json(directory / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("B0", "B1", "Junkie"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, default=ROOT / "eval")
    parser.add_argument("--model")
    parser.add_argument("--budget-usd", type=float, default=1.0)
    parser.add_argument("--max-calls", type=int, default=300)
    parser.add_argument("--ingestion-timeout-s", type=float, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-ids")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--skip-ingestion", action="store_true")
    parser.add_argument("--scenarios", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--judge-model", help="Must match --model; one shared budget")
    args = parser.parse_args()
    try:
        if (not math.isfinite(args.ingestion_timeout_s) or args.ingestion_timeout_s <= 0
                or not math.isfinite(args.budget_usd) or args.budget_usd <= 0
                or args.max_calls < 1 or args.repeat < 1):
            raise ValueError("Timeout, budget, max-calls and repeat must be positive")
        paid = args.variant == "Junkie" or args.judge
        if paid and (not args.model or not args.model.strip()):
            raise ValueError("--model is required for Junkie or --judge")
        if args.judge_model and args.judge_model != args.model:
            raise ValueError("--judge-model must equal --model to share the spending limit")
        if args.output_dir.exists():
            raise ValueError("Output directory already exists; use a new run directory")
        client = None
        if paid:
            from .openrouter import OpenRouterClient
            client = OpenRouterClient(args.model, args.budget_usd, args.max_calls)
        for repeat in range(1, args.repeat + 1):
            directory = args.output_dir if args.repeat == 1 else args.output_dir / f"repeat-{repeat:02d}"
            report = run_once(args, directory, repeat, client)
            summary = {"variant": args.variant, "repeat": repeat, "report": str(directory / "report.json"),
                       "HitRate@5": report["metrics"]["HitRate@5"]["value"],
                       "ActionAccuracy": report["metrics"]["ActionAccuracy"]["value"]}
            print(json.dumps(summary, ensure_ascii=False), flush=True)
        write_json(args.output_dir / "api-ledger.json", {
            "budget_usd": args.budget_usd,
            "accounted_spend_usd": getattr(client, "accounted_spend_usd", 0),
            "calls": client.calls if client else [],
            "usage": cost([{"id": "run", "llm_usage": {"complete": True, "calls": client.calls if client else []}}])})
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Cannot run: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
