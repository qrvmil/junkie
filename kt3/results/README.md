# Сохранённые прогоны

- `full-01.zip` — исходный артефакт полного сравнения из Actions: B0, B1,
  Junkie, ответы, трейсы, судья, формы проверки и отчёты.
- `full-01-summary.json` — агрегаты, расход, commit и SHA256 архива.
- `smoke-01.json` — проверка API и контрольные примеры судьи до полного прогона.
- [Таблицы сравнения](../RESULTS.md) и [разбор результата](../FINDINGS.md).

Архив сохранён в Git, поэтому его доступность не зависит от срока хранения
артефакта Actions. В нём нет API-ключа. Закрытая выборка не использовалась.

## Пересчитать без OpenRouter

Из корня репозитория:

```sh
python -m zipfile -e kt3/results/full-01.zip runs/full-01
python -m eval.kt3.evaluate \
  --run runs/full-01/junkie/run.json \
  --cases runs/full-01/junkie/cases.jsonl \
  --predictions runs/full-01/junkie/search.jsonl \
  --clean-predictions runs/full-01/junkie/clean.jsonl \
  --ingestion-outputs runs/full-01/junkie/ingestion.jsonl \
  --ingestion-timeout-s 120 \
  --scenario-outputs runs/full-01/junkie/scenarios.jsonl \
  --reviews runs/full-01/junkie/messages.jsonl \
  --output runs/recomputed-junkie.json
```

Для B0/B1 заменить `junkie` в путях на `b0`/`b1`. Используется уже записанная
оценка судьи: нового сетевого запроса нет. Для ручной оценки метаданных заполнить
соответствующий `metadata-review.jsonl` и передать его дополнительным `--reviews`.
При изменении исходных ответов сохранённые оценки перестают проходить проверку
хеша и требуют повторной проверки.

Для точного воспроизведения кода использовать commit из `run.json`. Изменения
оценщика после замера оформлять отдельным отчётом, сохраняя оригинальный.
