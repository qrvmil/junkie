"""LLM-проверка сообщений; подготовка задач работает без API-ключа."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.request

from eval.metrics.score import outcome
from .common import index_rows, output_hash, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = Path(__file__).with_name("prompts") / "messages.txt"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_tasks(cases, outputs, documents, environment):
    cases = index_rows(cases, "cases")
    outputs = index_rows(outputs, "predictions")
    if outputs.keys() - cases.keys():
        raise ValueError("predictions: unknown case ids")
    tasks = []
    for id_, case in cases.items():
        output = outputs.get(id_)
        action, _ = outcome(output)
        expected = case["expected"]
        checks = []
        if expected.get("has_more") is True and action == "search":
            checks.extend(["mentions_more", "suggests_narrowing"])
        if expected["action"] == "clarify" and action == "clarify":
            checks.append("clarification_useful")
        if not checks:
            continue
        response = output.get("response")
        if not isinstance(response, str):
            raise ValueError(f"{id_}: response must be a string for message judging")
        fixture_id = case.get("fixture_id", "base")
        fixtures = environment.get("fixtures", {})
        if fixture_id not in fixtures:
            raise ValueError(f"{id_}: unknown fixture {fixture_id}")
        fixture = fixtures[fixture_id]
        docs = {doc["doc_id"]: dict(doc) for doc in documents}
        for doc in fixture.get("additional_documents", []):
            docs[doc["doc_id"]] = dict(doc)
        for doc_id, fields in fixture.get("document_overrides", {}).items():
            if doc_id not in docs:
                raise ValueError(f"{id_}: fixture overrides unknown document {doc_id}")
            docs[doc_id].update(fields)
        candidates = []
        for doc_id in expected.get("clarify_candidates", []):
            if doc_id not in docs:
                raise ValueError(f"{id_}: unknown clarification candidate {doc_id}")
            doc = docs[doc_id]
            candidates.append({"doc_id": doc_id,
                               "title": doc.get("title") or Path(doc["path"]).name})
        judge_input = {
            "query": case["query"], "context": case.get("context", []),
            "response": response, "requested_checks": checks,
            "clarify_attribute": expected.get("clarify_attribute"),
            "clarify_candidates": candidates,
        }
        tasks.append({"id": id_, "kind": "messages", "output_sha256": output_hash(output),
                      "judge_input": judge_input, "judge_input_sha256": digest(judge_input)})
    return tasks


def validate_judgment(value, requested_checks):
    if not isinstance(value, dict) or set(value) != {"checks"}:
        raise ValueError("judge must return an object with only checks")
    checks = value["checks"]
    if not isinstance(checks, dict) or set(checks) != set(requested_checks):
        raise ValueError("judge checks differ from requested_checks")
    for name, check in checks.items():
        if (not isinstance(check, dict) or set(check) != {"passed", "reason"}
                or type(check["passed"]) is not bool
                or not isinstance(check["reason"], str) or not check["reason"].strip()):
            raise ValueError(f"invalid judge check {name}")
    return checks


def usage_from_response(response):
    raw = response.get("usage")
    raw = raw if isinstance(raw, dict) else {}
    usage = {}
    for source, target in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        value = raw.get(source)
        usage[target] = value if type(value) is int and value >= 0 else None
    cost = raw.get("cost")
    usage["cost_usd"] = (cost if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 else None)
    return usage


def request_judgment(task, prompt, model, api_key, timeout, max_output_tokens):
    body = {
        "model": model, "temperature": 0, "max_tokens": max_output_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps(task["judge_input"], ensure_ascii=False)}],
    }
    request = urllib.request.Request(
        API_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def judge_task(task, prompt, model, api_key, timeout=60, max_output_tokens=1200):
    record = {key: value for key, value in task.items() if key != "judge_input"}
    record.update({"model": model, "temperature": 0, "max_output_tokens": max_output_tokens,
                   "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                   "status": "error", "usage": {"input_tokens": None, "output_tokens": None, "cost_usd": None}})
    try:
        response = request_judgment(task, prompt, model, api_key, timeout, max_output_tokens)
        if not isinstance(response, dict):
            raise ValueError("API response must be an object")
        record["usage"] = usage_from_response(response)
        record["actual_model"] = response.get("model")
        record["generation_id"] = response.get("id")
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("judge content must be a string")
        record["raw_judgment"] = content
        record["checks"] = validate_judgment(json.loads(content), task["judge_input"]["requested_checks"])
        record["status"] = "ok"
    except urllib.error.HTTPError as exc:
        record["error"] = f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        record["error"] = "judge request failed"
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        record["error"] = f"invalid judge response ({type(exc).__name__})"
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "queries/dev.jsonl")
    parser.add_argument("--documents", type=Path, default=ROOT / "documents.jsonl")
    parser.add_argument("--environment", type=Path, default=ROOT / "fixtures/environment.json")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-output-tokens", type=int, default=1200)
    parser.add_argument("--prepare-only", action="store_true", help="Save requests without calling OpenRouter")
    args = parser.parse_args()
    try:
        if (not args.model.strip() or not math.isfinite(args.timeout) or args.timeout <= 0
                or args.max_output_tokens <= 0 or (args.max_calls is not None and args.max_calls < 0)):
            raise ValueError("model and positive timeout/output limit are required; max-calls must be nonnegative")
        tasks = build_tasks(read_jsonl(args.cases), read_jsonl(args.predictions), read_jsonl(args.documents),
                            json.loads(args.environment.read_text(encoding="utf-8")))
        if args.max_calls is not None:
            tasks = tasks[:args.max_calls]
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not args.prepare_only and tasks and not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        errors = 0
        # Exclusive creation prevents accidentally replacing an earlier evaluation.
        with args.output.open("x", encoding="utf-8") as stream:
            for task in tasks:
                if args.prepare_only:
                    record = dict(task, status="pending", model=args.model, temperature=0,
                                  max_output_tokens=args.max_output_tokens,
                                  prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest())
                else:
                    record = judge_task(task, prompt, args.model, api_key, args.timeout, args.max_output_tokens)
                    errors += record["status"] == "error"
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"Cannot judge: {exc}\n")
    print(json.dumps({"tasks": len(tasks), "errors": errors, "prepared_only": args.prepare_only}))
    if errors:
        parser.exit(1)


if __name__ == "__main__":
    main()
