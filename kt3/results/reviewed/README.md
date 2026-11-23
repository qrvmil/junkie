# Пересчёт после оценки метаданных

Исходные ответы, трейсы и отчёты остались без изменений в
[`full-01.zip`](../full-01.zip) и [`full-02.zip`](../full-02.zip).
Здесь сохранены четыре заполненные формы `metadata-review.jsonl` и
[`reports.zip`](reports.zip) с четырьмя полными `report.json`:
`full01/{b0,b1,junkie}` и `full02/junkie`.
По 7 валидных ingestion-кейсов на каждый запуск, всего **28 оценок**.
Каждая запись содержит `output_sha256`, `gold_sha256`, решение и причину для
title/description/topic, а также решение, `concept_id` и причину для каждого
тега. Исполнитель указан как **Codex, делегированная агентная оценка от имени
Егора Островенко**. Это не независимая человеческая разметка КТ-2.

Оценка выполнена по исходным файлам в `eval/corpus/` и `eval/fixtures/`,
критериям [`eval/ingestion/gold.jsonl`](../../../eval/ingestion/gold.jsonl)
и сохранённым выходам. Выходы показывались в случайном порядке под метками
P/Q/R/S без названия варианта; после фиксации решений метки сопоставлены с
запусками. Для синонимов использован общий `concept_id`; например, `values`
и `weights` у I06 относятся к одному понятию `weighted_values`. Случаи с
общей темой вместо требуемой конкретной темы, обрезанным описанием или
неподтверждённым тегом получили отрицательную оценку с объяснением.
Исходные рубрики `gold.jsonl` имеют `annotation_status=agent_annotated` и
`human_review_status=pending`; оценка выходов по источникам не превращает
эти рубрики в человечески проверенный gold, и их статус не менялся.

## Итог

Главная [таблица КТ-3](../../RESULTS.md) сравнивает B0/B1 из `full-01` с
более свежим Junkie из `full-02`. Для исторического Junkie из `full-01`
сохранён отдельный пересчитанный отчёт и
[парные дельты](full02-vs-full01.json). Показатели метаданных для B0/B1 и
актуального Junkie:

| Метрика | B0 | B1 | Junkie full-02 |
|---|---:|---:|---:|
| MetadataCorrectness/Title | 1/7 | 1/7 | 5/7 |
| MetadataCorrectness/Description | 4/7 | 4/7 | 6/7 |
| MetadataCorrectness/Topic | 0/7 | 0/7 | 3/7 |
| MetadataCompleteness/FullPassRate | 4/7 | 4/7 | 6/7 |
| TagRelevance | 0,7024 | 0,7024 | 1,0000 |

`MetadataCompleteness` проверяет наличие полей и 3–7 разных понятий тегов;
достоверность самих тегов отражает отдельный `TagRelevance`.

Остальные агрегаты, кроме `metadata_present/tags`, совпали с исходными
отчётами. Это новый **пересчёт оценки**, а не новый запуск системы.
`ParsedQuery` для Junkie остаётся диагностическим `pending` по существующей
методике; смысловые показатели метаданных завершены. Исходные прогоны
связаны с коммитами `cc92f4e` (`full-01`) и `7363802` (`full-02`).

## Воспроизведение без API

Из корня репозитория, Python 3.12 и зависимость из
`eval/ingestion/requirements.txt`:

```sh
python -m zipfile -e kt3/results/full-01.zip runs/full-01
python -m zipfile -e kt3/results/full-02.zip runs/full-02
python -m zipfile -e kt3/results/reviewed/reports.zip runs/reviewed
for spec in full01/b0 full01/b1 full01/junkie full02/junkie; do
  run_name=${spec%%/*}
  variant=${spec#*/}
  archive_name=full-${run_name#full}
  input_dir=runs/${archive_name}/${variant}
  python -m eval.kt3.evaluate \
    --run "$input_dir/run.json" --cases "$input_dir/cases.jsonl" \
    --predictions "$input_dir/search.jsonl" \
    --clean-predictions "$input_dir/clean.jsonl" \
    --ingestion-outputs "$input_dir/ingestion.jsonl" \
    --ingestion-timeout-s 120 \
    --scenario-outputs "$input_dir/scenarios.jsonl" \
    --reviews "$input_dir/messages.jsonl" \
    --reviews "kt3/results/metadata-review/${spec}/metadata-review.jsonl" \
    --output "runs/recomputed-${run_name}-${variant}.json"
done
python -m kt3.summarize \
  runs/reviewed/full01/b0 runs/reviewed/full01/b1 runs/reviewed/full02/junkie \
  --output runs/recomputed-results.md \
  --workflow-url https://github.com/qrvmil/junkie/actions/runs/45030212224 \
  --workflow-url https://github.com/qrvmil/junkie/actions/runs/45066928131
python -m kt3.compare_runs \
  --before runs/reviewed/full01/junkie --after runs/reviewed/full02/junkie \
  --output runs/recomputed-change.json
```

`report.json` внутри `reports.zip` дополнительно сохраняет исходные `preparation` и
`run_elapsed_ms`: офлайн-оценщик их не перемеряет. Значения этих двух полей
перенесены без изменений из исходных отчётов; метрики, проверки, задержки, расходы и хеши
входов вычислены оценщиком. Поисковые и сценарные ответы не изменялись.
