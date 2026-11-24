# Формат результатов

JSONL: один объект на кейс, UTF-8. Повторные/неизвестные ID — ошибка импорта.
Статусы: `ok`, `error`, `timeout`, `missing`, `invalid`.
Контролируемый отказ — `status: "ok"` с соответствующим действием/причиной.

## Поиск

```json
{
  "id": "E01", "status": "ok", "action": "search",
  "result_doc_ids": ["doc_001"], "response": "Нашёл apple.txt.",
  "results": [{"doc_id": "doc_001", "title": "apple.txt", "snippet": "Фрагмент исходника", "source": "saved://doc_001", "uploaded_at": "2026-09-01"}],
  "parsed_query": {"filters": {}, "order_by": "relevance"},
  "trace": {"complete": true, "calls": [{"name": "search_documents", "arguments": {"query": "apple", "filters": {}, "order_by": "relevance", "limit": 5}, "status": "ok", "read_doc_ids": ["doc_001"]}]},
  "observations": {"source_checks": [{"doc_id": "doc_001", "openable": true, "snippet_supported": true}]},
  "elapsed_ms": 120,
  "llm_usage": {"complete": true, "calls": []}
}
```

Это пример формы, не результат запуска. `action`: search/clarify/no_result/refuse.
У трёх последних `result_doc_ids` пуст. Порядок `results` совпадает с ID выдачи.
`parsed_query` — фактический разбор, а не скопированный `gold_steps`.
Gold и смысловые метки корпуса используются оценщиком. Runner не должен
передавать системе `expected`, `gold_steps`, `expected_calls` или сценарные `assert`.

`trace`, `observations`, время и usage записывает адаптер, не модель.
`read_doc_ids` включает внутренний отбор кандидатов, чтение фрагментов и
доступы при ошибках. `complete: true` означает, что записаны все вызовы.
`source_checks` проверяет открытие именно указанного документа и наличие
именно показанного фрагмента. Без наблюдений эти проверки остаются pending.

Вызов инструмента: `name`, `arguments`, `status: ok/error`, `read_doc_ids`.
Для внедрённых сбоев дополнительно `error_code: timeout/unavailable`.
Обязательные аргументы сопоставляются как подмножество, а не буквальная JSON-строка.
Для E132/E133 разрешён прямой `get_document` выбранного документа из предыдущей
выдачи. Другие альтернативы автоматически не угадываются.

## Ingestion

```json
{
  "id": "I01", "status": "ok", "action": "ingest",
  "extracted_text": "Полный извлечённый текст",
  "metadata": {"title": "Название", "description": "Описание", "topic": "Тема", "tags": ["тег1", "тег2", "тег3"], "uploaded_at": "2026-10-24"},
  "observations": {"source_saved": true, "source_openable": true, "searchable": true},
  "elapsed_ms": 1500, "llm_usage": {"complete": true, "calls": []}
}
```

Для невалидного входа: `action: "reject"`, `reason`:
`unsupported_format`, `too_large` или `corrupted`.
Format/Size требуют `llm_usage.complete: true` и пустой список вызовов.
Успех ingestion требует непустого текста и всех трёх наблюдений в пределах
`--ingestion-timeout-s`. Дата — ISO date либо timestamp с часовым поясом.

## Usage и запуск

Один элемент `llm_usage.calls` на каждый оплачиваемый вызов, включая повтор:

```json
{"model": "точный-id-модели", "input_tokens": 2500, "output_tokens": 300, "cost_usd": 0.0015}
```

Числа здесь иллюстративные. Стоимость неизвестна — `null`, не 0.
Пустые `calls` с полной записью означают отсутствие LLM-вызовов.
Обработка корпуса и построение индекса учитываются отдельно от поиска;
их затраты не следует повторно приписывать каждому запросу.

`run.json` сохраняет конфигурацию одного варианта и одного повторения:

```json
{
  "run_id": "b0-dev-01", "variant": "B0", "git_commit": "полный SHA",
  "model": null, "temperature": null, "seed": null, "prompts": [],
  "config": {"fixture_version": "junkie_eval_v3", "cache": "указать режим"}
}
```

Для Junkie записать фактическую модель и параметры, в `prompts` — объекты
`{"name": "query", "text": "полный текст промпта"}`. Не записывать API-ключи.
Оценщик добавляет SHA-256 входных файлов. Каждый повтор сохраняется отдельно.

## Сценарии

`scenarios.json` содержит начальное состояние, пользовательские ходы,
сбой, лимит и эталонные проверки. Передавать системе только входы;
историю собирать из её реальных ответов.

Результат: `id`, `status`, `termination_reason`, `steps` (ответ на каждый
пользовательский ход в указанном выше формате), суммарный `llm_usage`.
Причины завершения: `completed` или `budget_exhausted` согласно сценарию.
В S07 добавить `initial_observations.absent_doc_ids`, а на шаге добавления —
`document_id`. Пример фиксированного ID задан в спецификации сценария.
Один флаг `success: true` не используется для расчёта.
