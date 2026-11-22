"""Таблицы из report.json; незавершённые оценки сохраняют статус pending."""
import argparse
import json
from pathlib import Path


def number(value):
    return "—" if value is None else f"{value:.4f}"


def cell(value):
    return number(value.get("value")) if value.get("status") == "ok" else value.get("status", "—")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workflow-url", required=True)
    args = parser.parse_args()
    reports = [json.loads((p / "report.json").read_text()) for p in args.directories]
    names = [r["run"]["variant"] for r in reports]
    lines = ["# Результаты КТ3", "", f"[Запуск Actions]({args.workflow_url}).",
             "Значения долей приведены от 0 до 1. `pending` — оценка не завершена,",
             "`not_applicable` — проверка неприменима. Это один прогон открытого dev-набора.", ""]

    def table(title, rows):
        lines.extend(["## " + title, "", "| Показатель | " + " | ".join(names) + " |",
                      "|---|" + "---:|" * len(names)])
        lines.extend("| " + label + " | " + " | ".join(values) + " |" for label, values in rows)
        lines.append("")

    all_metrics = sorted({k for r in reports for k in r["metrics"]})
    groups = {"Поиск и действия": lambda n: not n.startswith(("Constraint", "DateOrder", "Metadata", "Tag", "Ingestion", "Extraction", "InvalidInput")),
              "Условия запроса": lambda n: n.startswith(("Constraint", "DateOrder")),
              "Добавление и метаданные": lambda n: n.startswith(("Metadata", "Tag", "Ingestion", "Extraction", "InvalidInput"))}
    for title, predicate in groups.items():
        keys = [k for k in all_metrics if predicate(k)]
        table(title, [(k, [cell(r["metrics"].get(k, {})) for r in reports]) for k in keys])
    checks = sorted({k for r in reports for k in r["checks"]})
    table("Проверки контракта и сценариев", [(k, [cell(r["checks"].get(k, {})) for r in reports]) for k in checks])
    table("Время", [(f"{dataset} {p.upper()}, мс", [number(r["latency"][dataset][p]) for r in reports])
                    for dataset in ("search", "ingestion") for p in ("p50", "p95")] +
          [("Подготовка индекса, с", [number(r["preparation"]["elapsed_ms"] / 1000) for r in reports]),
           ("Весь прогон с оценщиком, с", [number(r.get("run_elapsed_ms", 0) / 1000) for r in reports])])
    cost_groups = ("search", "clean_queries", "ingestion", "scenarios", "judge")
    table("Расход OpenRouter, USD", [(k, [number(r["cost"].get(k, {}).get("cost_usd")) for r in reports]) for k in cost_groups])
    scenario_ids = sorted({id_ for r in reports for id_, row in r["cases"].items() if row["dataset"] == "scenario"})
    table("Многошаговые сценарии", [(id_, [cell(r["cases"].get(id_, {}).get("checks", {}).get("ScenarioSuccess", {})) for r in reports]) for id_ in scenario_ids])
    lines.extend(["## Условия", "", "- Commit: " + ", ".join(sorted({"`" + r["run"]["git_commit"] + "`" for r in reports})) + ".",
                  "- Модель: " + ", ".join(sorted({"`" + r["run"]["model"] + "`" for r in reports if r["run"]["model"]})) + ".",
                  "- Ручная оценка смысла метаданных и H0 не выполнены.",
                  "- `ParsedQuery` проверяет точное совпадение с gold, включая случаи эквивалентного разбора.",
                  "- Поиск измерен на готовом индексе; ingestion заново извлекает текст.",
                  "- `saved://` открывается внутри локального архива; HTTP-раздача файлов не реализована.",
                  "- PISR проверяет изоляцию: содержимое найденных файлов не передаётся в LLM-планировщик.",
                  "- Расход API не включает стоимость компьютера, Actions и ручного труда.", ""])
    args.output.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
