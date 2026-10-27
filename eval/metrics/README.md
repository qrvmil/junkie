# Поисковые метрики

В `dev.jsonl`: 116 `search`, 6 `clarify`, 9 `no_result`, 9 `refuse`.

| Метрика | Балл кейса | Подвыборка |
| --- | --- | --- |
| HitRate@5 | 1, если в топ-5 есть релевантный документ | 116 search |
| MRR@5 | 1 / позиция первого релевантного документа в топ-5; без попадания — 0 | 116 search |
| Recall@5 | Число разных релевантных ID в топ-5 / размер gold | 116 search |
| Precision@5 | Число разных релевантных ID в топ-5 / 5 | 116 search |
| Action Accuracy | 1 при совпадении действия, иначе 0 | Все 140; также по классам |
| False Refusal Rate | 1 при корректно оформленном action=refuse, иначе 0 | 116 search |

Итог — среднее по подвыборке, заданной gold. Повторы занимают позиции,
но не добавляют попаданий. Ошибки, пропуски и неверные действия дают 0
в ранжировании и Action Accuracy. Технический сбой не считается отказом.
Отчёт содержит `value`, `sum`, `n`; при `n=0` значение — `null`.

## Запуск

Вход — JSONL с фактическим порядком выдачи:

```json
{"id":"E01","status":"ok","action":"search","result_doc_ids":["doc_001"]}
{"id":"E22","status":"ok","action":"clarify","result_doc_ids":[]}
{"id":"E02","status":"timeout"}
```

`status`: ok/error/timeout/missing/invalid. Для ok обязательны `action` и
`result_doc_ids`; у clarify/no_result/refuse список пустой.
Пропущенный кейс считается missing, неверная форма ответа — invalid.
Неизвестные или повторные ID и повреждённый JSON прерывают импорт.

```sh
python eval/annotation/scripts/validate_eval.py
python eval/metrics/score.py --predictions predictions.jsonl
python -m unittest discover -s eval/metrics -p 'test_*.py'
```

По умолчанию используется `eval/queries/dev.jsonl`; другой набор задаётся
через `--cases`. Отчёт выводится в stdout. Скрипт считает метрики из таблицы;
ACL, фильтры, лимит выдачи и вызовы инструментов проверяются отдельно.
