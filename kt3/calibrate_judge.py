"""Контрольные примеры судьи. Ожидания авторские, не независимая разметка людей."""
import argparse
import hashlib
import json
from pathlib import Path

from eval.kt3.common import read_jsonl
from eval.kt3.judge import PROMPT_PATH, validate_judgment
from junkie.openrouter import ModelError, OpenRouterClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--budget-usd", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    client = OpenRouterClient(args.model, args.budget_usd, 12)
    prompt = PROMPT_PATH.read_text()
    controls = read_jsonl(Path(__file__).with_name("judge_controls.jsonl"))
    results = []
    for control in controls:
        task = {"query": control["query"], "context": [], "response": control["response"],
                "clarify_attribute": control.get("clarify_attribute"),
                "clarify_candidates": control.get("clarify_candidates", []),
                "requested_checks": list(control["labels"])}
        row = {"id": control["id"], "expected": control["labels"], "status": "error"}
        try:
            actual = client.complete_json([{"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(task, ensure_ascii=False)}], max_tokens=512, purpose="judge_control")
            checks = validate_judgment(actual, task["requested_checks"])
            row.update(status="ok", checks=checks,
                       matched=sum(checks[k]["passed"] == v for k, v in control["labels"].items()),
                       total=len(control["labels"]))
        except (ModelError, ValueError, RuntimeError, OSError) as exc:
            row["error"] = type(exc).__name__
        results.append(row)
        (args.output_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    total = sum(len(c["labels"]) for c in controls)
    correct = sum(r.get("matched", 0) for r in results)
    summary = {"model": args.model, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
               "label_source": "authored control examples, not independent human annotation",
               "correct": correct, "total": total, "accuracy": correct / total,
               "errors": sum(r["status"] != "ok" for r in results), "usage": client.calls}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "usage"}))


if __name__ == "__main__":
    main()
