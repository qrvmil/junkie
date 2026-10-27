# Поисковый gold

`dev.jsonl` содержит 140 кейсов. Для 30 размеченных кейсов общие поля
`expected` совпадают с `../annotation/final_gold.jsonl`.
Фильтры и сортировка согласованы с `gold_steps` и `expected_calls`.

## Фильтры

`format`, `source_type`, `doc_type` проверяются по метаданным.
`filename` — полное имя или имя без префикса `NNN_`.
Для `content_date` используется `content_events`; поле `event` выбирает тип события.

Даты задаются в формате `YYYY-MM-DD` и часовом поясе кейса:
`gte` включается, `lt` исключается. Достаточно одной границы.

| Запрос | Фильтр uploaded_at |
| --- | --- |
| 15 октября | `{"gte":"2026-10-15","lt":"2026-10-16"}` |
| с 15 по 18 октября включительно | `{"gte":"2026-10-15","lt":"2026-10-19"}` |
| после 17 октября | `{"gte":"2026-10-18"}` |
| по 16 октября включительно | `{"lt":"2026-10-17"}` |

## Проверка

Python 3.10+, стандартная библиотека:

```sh
python eval/annotation/scripts/validate_eval.py
python -m unittest discover -s eval/annotation/scripts -p 'test_*.py'
```

При изменении gold обновляются `final_gold`, арбитраж, `expected`, шаги и вызовы
в dev. История исправлений хранится в `../annotation/gold_corrections.jsonl`.
Исходные A/B сохраняются.
