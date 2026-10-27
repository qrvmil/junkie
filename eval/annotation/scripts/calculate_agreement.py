#!/usr/bin/env python3
"""Reproduce pre-adjudication agreement and the Russian Markdown report (stdlib only)."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from prepare_blind import ROOT, load_jsonl
from validate_annotations import (
    ACTIONS, comparable, validate_adjudication, validate_blind, validate_file,
)


def rate(matched, total):
    return {"matched": matched, "total": total,
            "fraction": matched / total if total else None,
            "percent": 100 * matched / total if total else None}


def calculate(a, b):
    if not a or a.keys() != b.keys():
        raise ValueError("Nonempty A/B must have exactly the same case IDs")
    ids = list(a)
    n = len(ids)
    matrix = {left: {right: 0 for right in ACTIONS} for left in ACTIONS}
    for id_ in ids:
        matrix[a[id_]["action"]][b[id_]["action"]] += 1
    matched = sum(matrix[action][action] for action in ACTIONS)
    p_observed = matched / n
    p_expected = sum(sum(matrix[x].values()) * sum(matrix[y][x] for y in ACTIONS)
                     for x in ACTIONS) / n**2
    # With constant identical labels, kappa is undefined (0/0), not fabricated as 1.
    kappa = (p_observed - p_expected) / (1 - p_expected) if p_expected < 1 else None
    applicable = [id_ for id_ in ids if "search" in (a[id_]["action"], b[id_]["action"])]
    similarities = []
    for id_ in applicable:
        left, right = set(a[id_]["relevant_doc_ids"]), set(b[id_]["relevant_doc_ids"])
        union = left | right
        if not union:
            raise ValueError(f"{id_}: applicable search case cannot have two empty sets")
        similarities.append(len(left & right) / len(union))
    exact = sum(set(a[id_]["relevant_doc_ids"]) == set(b[id_]["relevant_doc_ids"])
                for id_ in applicable)
    differing = {}
    for id_ in ids:
        left, right = comparable(a[id_]), comparable(b[id_])
        fields = [field for field in left if left[field] != right[field]]
        if fields:
            differing[id_] = fields
    candidate_ids = [id_ for id_ in ids if "clarify" in (a[id_]["action"], b[id_]["action"])]
    return {
        "case_count": n,
        "actions": {**rate(matched, n), "cohens_kappa": kappa,
                    "p_observed": p_observed, "p_expected": p_expected,
                    "counts_a": dict(Counter(row["action"] for row in a.values())),
                    "counts_b": dict(Counter(row["action"] for row in b.values())),
                    "confusion_matrix": matrix,
                    "disagreement_matrix": {x: {y: matrix[x][y] if x != y else 0 for y in ACTIONS}
                                            for x in ACTIONS}},
        "documents": {
            "applicability": "At least one annotator chose search; all other pairs excluded",
            "applicable_ids": applicable,
            "excluded_ids": [id_ for id_ in ids if id_ not in applicable],
            "exact_set_agreement": rate(exact, len(applicable)),
            "mean_jaccard": sum(similarities) / len(similarities) if similarities else None,
            "jaccard_by_id": dict(zip(applicable, similarities)),
        },
        "filters": rate(sum(a[id_]["filters"] == b[id_]["filters"] for id_ in ids), n),
        "order_by": rate(sum(a[id_]["order_by"] == b[id_]["order_by"] for id_ in ids), n),
        "has_more": rate(sum(a[id_]["has_more"] == b[id_]["has_more"] for id_ in ids), n),
        "clarify_candidates": {
            **rate(sum(set(a[id_]["clarify_candidates"]) == set(b[id_]["clarify_candidates"])
                       for id_ in candidate_ids), len(candidate_ids)),
            "applicable_ids": candidate_ids,
        },
        "disagreement_count": len(differing),
        "disputed_ids": list(differing),
        "differing_fields": differing,
    }


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percentage(metric):
    if metric["percent"] is None:
        return "N/A (нет применимых кейсов)"
    return f"{metric['percent']:.2f}% ({metric['matched']}/{metric['total']})"


def number(value):
    return "N/A (не определено)" if value is None else f"{value:.6f}"


def render_report(result, a, b, decisions, final, method=None):
    actions, docs = result["actions"], result["documents"]
    lines = ["# Двойная разметка Junkie", "", "## Выборка и метод", "",
             f"Кейсов: **{result['case_count']}**. Категории взяты только из поля `category` исходного набора; "
             "Категории являются основными метками набора, а не полной таксономией покрытия.", "",
             "| Категория | Число |", "| --- | ---: |"]
    lines += [f"| {key} | {count} |" for key, count in sorted(result["categories"].items())]
    lines += ["", method.strip() if method and method.strip() else
              "Способ разметки не указан. Передайте --method-file с фактическим описанием участников, "
              "процедуры, независимости и согласования. По файлам аннотаций эти сведения установить нельзя.", "",
              "## Согласие до согласования", "", "| Метрика | Значение |", "| --- | ---: |",
              f"| Percent Agreement действий | {percentage(actions)} |",
              f"| Cohen's Kappa | {number(actions['cohens_kappa'])} |",
              f"| Exact Set Agreement документов | {percentage(docs['exact_set_agreement'])} |",
              f"| Mean Jaccard документов | {number(docs['mean_jaccard'])} |",
              f"| Exact Match filters | {percentage(result['filters'])} |",
              f"| Agreement order_by | {percentage(result['order_by'])} |",
              f"| Agreement has_more | {percentage(result['has_more'])} |",
              f"| Exact Set Agreement clarify_candidates | {percentage(result['clarify_candidates'])} |", "",
              f"Документы: {len(docs['applicable_ids'])} применимых кейсов, где хотя бы один разметчик выбрал `search`. "
              "Пары search/clarify, search/refuse и search/no_result включаются и сравнивают реальные множества с пустым. "
              "Совместные no_result, clarify и refuse исключаются: пустые множества не повышают оценку. "
              "Jaccard = |A ∩ B| / |A ∪ B|, затем невзвешенное среднее по кейсам. Порядок ID не учитывается. "
              "Фильтры сравниваются как JSON-объекты с точным совпадением значений, без учёта порядка ключей. "
              "Фильтры и сортировка сравниваются на всей выборке.", "",
              "Применимые ID: " + ", ".join(docs["applicable_ids"]) + ".", "",
              "Исключённые ID: " + ", ".join(docs["excluded_ids"]) + ".", "",
              f"Для Kappa: pₒ = {number(actions['p_observed'])}, pₑ = {number(actions['p_expected'])}; "
              "κ = (pₒ − pₑ) / (1 − pₑ). При pₑ = 1 выводится null/N/A.", "",
              "### Матрица действий", "", "Строки — A, столбцы — B. Вне диагонали — несовпадения.", "",
              "| A / B | " + " | ".join(ACTIONS) + " |", "| --- | " + " | ".join(["---:"] * len(ACTIONS)) + " |"]
    lines += ["| " + action + " | " + " | ".join(str(actions["confusion_matrix"][action][right]) for right in ACTIONS) + " |"
              for action in ACTIONS]
    lines += ["", "## Несовпадения и согласование", "",
              f"Кейсов с любым расхождением: **{result['disagreement_count']}**. "
              "Учитываются все поля разметки, включая кандидатов и has_more.", "",
              "| ID | Расходящиеся поля | Действие A → B → final | Итоговое решение |", "| --- | --- | --- | --- |"]
    by_id = {row["id"]: row for row in decisions}
    for id_ in result["disputed_ids"]:
        row = by_id.get(id_)
        decision = row["comment"].replace("|", "\\|").replace("\n", " ") if row else "Ещё не согласовано"
        final_action = row["final"]["action"] if row else "—"
        lines.append(f"| {id_} | {', '.join(result['differing_fields'][id_])} | "
                     f"{a[id_]['action']} → {b[id_]['action']} → {final_action} | {decision} |")
    if final:
        lines += ["", f"Согласование выполнено для всех {len(decisions)} спорных кейсов. `final_gold.jsonl` содержит {len(final)} записей. "
                  "Совпавшие A/B перенесены без смысловых изменений; оригинальные A/B сохранены. "
                  "Полные исходные и итоговые объекты спорных случаев находятся в `adjudication.jsonl`.", "",
                  "Итоговые действия: " + ", ".join(f"{key}: {count}" for key, count in sorted(Counter(r["action"] for r in final.values()).items())) + "."]
    else:
        lines += ["", "Согласование пока не представлено."]
    lines += ["", "## Вывод и воспроизведение", "",
              f"Полное исходное совпадение по всем полям: {result['case_count'] - result['disagreement_count']}/{result['case_count']}. "
              "Спорные случаи перечислены выше; причины решений выводятся при наличии согласования. "
              "Согласие разметчиков само по себе не доказывает корректность и полноту gold. "
              "Правила неоднозначности, широты релевантности и дат следует проверить при согласовании.", "",
              "Все числа в этом отчёте и `agreement.json` вычислены из неизменённых A/B до согласования. "
              "Арбитраж не подменяет входы метрик. Схема фильтров и процедура описаны в README.", "", "```sh",
              "python3 eval/annotation/scripts/prepare_blind.py",
              "python3 eval/annotation/scripts/validate_annotations.py --check-adjudication",
              "python3 eval/annotation/scripts/calculate_agreement.py",
              "python3 -m unittest discover -s eval/annotation/scripts -p 'test_*.py'", "```", "",
              "### SHA-256 исходных входов метрик", "", "| Файл | SHA-256 |", "| --- | --- |"]
    lines += [f"| {name} | `{sha}` |" for name, sha in sorted(result["input_sha256"].items())]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    folder = ROOT / "annotation"
    parser.add_argument("annotator_a", nargs="?", type=Path, default=folder / "annotator_a.jsonl")
    parser.add_argument("annotator_b", nargs="?", type=Path, default=folder / "annotator_b.jsonl")
    parser.add_argument("--output-json", type=Path, default=folder / "agreement.json")
    parser.add_argument("--output-md", type=Path, default=folder / "agreement.md")
    parser.add_argument("--eval-root", type=Path, default=ROOT)
    parser.add_argument("--method-file", type=Path, help="UTF-8 text describing the actual annotation procedure")
    parser.add_argument("--adjudication", type=Path, help="Optional adjudication file to include in report")
    parser.add_argument("--final", type=Path, help="Optional final gold to include in report")
    args = parser.parse_args()
    root = args.eval_root
    outputs = [args.output_json.resolve(), args.output_md.resolve()]
    protected = {args.annotator_a.resolve(), args.annotator_b.resolve()}
    protected.update(path.resolve() for path in root.rglob("*")
                     if path.is_file() and "annotation" not in path.relative_to(root).parts)
    protected.update(path.resolve() for path in (root / "annotation").glob("*.jsonl"))
    protected.update(path.resolve() for path in (args.adjudication, args.final) if path)
    if args.method_file:
        protected.add(args.method_file.resolve())
    if outputs[0] == outputs[1] or any(path in protected for path in outputs):
        raise ValueError("Report outputs must be distinct and must not overwrite source data or annotations")
    cases = validate_blind(root / "annotation/blind_cases.jsonl")
    manifest = [json.loads(line) for line in (root / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    environment = json.loads((root / "fixtures/environment.json").read_text(encoding="utf-8"))
    a, b = [validate_file(path, cases, manifest, environment, root) for path in (args.annotator_a, args.annotator_b)]
    # Select only category metadata; reference labels are never used in metrics or adjudication.
    categories = {row["id"]: row["category"] for row in load_jsonl(root / "queries/dev.jsonl")}
    result = calculate(a, b)
    result["categories"] = dict(sorted(Counter(categories[id_] for id_ in cases).items()))
    result["input_sha256"] = {name: digest(path) for name, path in (
        ("annotator_a", args.annotator_a), ("annotator_b", args.annotator_b),
        ("blind_cases", root / "annotation/blind_cases.jsonl"),
        ("documents", root / "documents.jsonl"), ("environment", root / "fixtures/environment.json"))}
    decisions, final = [], {}
    # Only automatically include repository adjudication when using the repository's A/B.
    default_inputs = args.annotator_a.resolve() == (folder / "annotator_a.jsonl").resolve() and args.annotator_b.resolve() == (folder / "annotator_b.jsonl").resolve()
    adjudication_path = args.adjudication or (folder / "adjudication.jsonl" if default_inputs else None)
    final_path = args.final or (folder / "final_gold.jsonl" if default_inputs else None)
    if bool(args.adjudication) != bool(args.final):
        raise ValueError("Supply --adjudication and --final together")
    if adjudication_path and final_path and adjudication_path.exists() and final_path.exists():
        final = validate_file(final_path, cases, manifest, environment, root)
        decisions = validate_adjudication(adjudication_path, a, b, final)
    elif args.adjudication:
        raise ValueError("Requested adjudication/final file is missing")
    method = args.method_file.read_text(encoding="utf-8") if args.method_file else None
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.output_md.write_text(render_report(result, a, b, decisions, final, method), encoding="utf-8")
    print(f"Calculated {result['case_count']} cases; {result['disagreement_count']} disagreements")
    print(f"Actions: {percentage(result['actions'])}; kappa: {number(result['actions']['cohens_kappa'])}")
    print(f"Documents: {percentage(result['documents']['exact_set_agreement'])}; Jaccard: {number(result['documents']['mean_jaccard'])}")


if __name__ == "__main__":
    main()
