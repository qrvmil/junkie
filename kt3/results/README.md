# Сохранённые прогоны

- `full-01.zip` — исходный артефакт полного сравнения из Actions: B0, B1,
  Junkie, ответы, трейсы, судья, формы проверки и отчёты.
- `full-01-summary.json` — агрегаты, расход, commit и SHA256 архива.
- `smoke-01.json` — проверка API и контрольные примеры судьи до полного прогона.
- [Таблицы сравнения](../RESULTS.md) и [разбор результата](../FINDINGS.md).
- [Заполненные оценки метаданных и пересчитанные отчёты](reviewed/README.md)
  для B0/B1/Junkie `full-01` и Junkie `full-02`.

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
оценка судьи: нового сетевого запроса нет. Завершённые формы оценивания и
полная команда с дополнительным `--reviews` находятся в
[пересчёте](reviewed/README.md). При изменении исходных ответов сохранённые
оценки перестают проходить проверку хеша и требуют нового оценивания.

Для точного воспроизведения кода использовать commit из `run.json`. Изменения
оценщика после замера оформлять отдельным отчётом, сохраняя оригинальный.

## Повторный эксперимент

`full-02.zip` содержит только новый запуск Junkie. B0/B1 и первая версия
Junkie остаются в `full-01.zip`. Для сравнения распаковать оба архива:

```sh
python -m zipfile -e kt3/results/full-02.zip runs/full-02
python -m kt3.compare_runs --before runs/full-01/junkie --after runs/full-02/junkie --output runs/change.json
```

В `increased` и `decreased` — направления численного изменения, поэтому для
метрик ошибок рост означает ухудшение. Изменение применимости вынесено отдельно.
Незавершённые оценки не заменяются нулями.
