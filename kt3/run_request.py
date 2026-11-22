"""Запуск заранее записанной конфигурации в Actions, без автоматических повторов."""
import json
import math
from pathlib import Path
import subprocess
import sys


def main():
    request = json.loads(Path("kt3/request.json").read_text())
    if request["mode"] == "connection":
        return
    if request["mode"] not in {"smoke", "full"}:
        raise ValueError("Unknown run mode")
    runs = request["runs"]
    control_budget = request.get("judge_control_budget_usd", 0)
    total_budget = control_budget + sum(r["budget_usd"] for r in runs)
    if not math.isfinite(total_budget) or not 0 < total_budget <= 5:
        raise ValueError("A request must reserve at most $5 across all runs")
    output = Path("runs")
    output.mkdir(exist_ok=True)
    (output / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    model = request["model"]
    if control_budget:
        subprocess.run([sys.executable, "-m", "kt3.calibrate_judge", "--model", model,
                        "--budget-usd", str(control_budget), "--output-dir", "runs/judge-controls"], check=True)
    for run in runs:
        variant = run["variant"]
        if variant not in {"B0", "B1", "Junkie"}:
            raise ValueError("Unknown variant")
        command = [sys.executable, "-m", "junkie.run", "--variant", variant,
                   "--output-dir", f"runs/{variant.lower()}", "--model", model,
                   "--budget-usd", str(run["budget_usd"]), "--max-calls", str(run["max_calls"]),
                   "--ingestion-timeout-s", str(request["ingestion_timeout_s"]),
                   "--repeat", str(request.get("repeat", 1)), "--scenarios", "--judge"]
        if request["mode"] == "smoke":
            command.extend(["--limit", "8"])
        print(f"Starting {variant}; budget ${run['budget_usd']}", flush=True)
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
