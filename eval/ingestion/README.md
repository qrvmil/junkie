# Проверка ingestion

```sh
python -m pip install -r eval/ingestion/requirements.txt
python eval/ingestion/validate_gold.py
python -m unittest discover -s eval/ingestion -p 'test_*.py'
```

`validate_gold.py` сверяет SHA-256 исходников, цитаты, координаты и структуру `gold.jsonl`.
Координаты начинаются с 1: `page:N`, `paragraph:N` (включая пустые абзацы DOCX),
`slide:N`, `line:N-M`. HTML читается из сохранённого файла без head, script и style.

## Extraction Coverage

Формат результатов — JSONL:

```json
{"id":"I01","status":"ok","extracted_text":"Извлечённый текст"}
{"id":"I02","status":"timeout"}
```

```sh
python eval/ingestion/score_extraction.py --outputs ingestion_outputs.jsonl
```

Балл документа — доля найденных gold-фрагментов. Итог — среднее по I01–I07;
ошибки и пропуски дают 0. Повтор цитаты не добавляет баллов.
При сравнении нормализуются регистр, пробелы, Unicode и переносы слов.

## Метаданные и теги

Название, описание и тема проверяются по `must_convey` и `must_not_claim` в gold.
Допустимы перефразы. Дата добавления берётся из `case.now` и `case.timezone`:
для этих кейсов — 2026-10-24, Europe/Moscow.

Для каждого поля фиксируются решение и причина. Доля правильных ответов
считается отдельно по полям на всех семи кейсах; пропуск результата даёт 0.

Тег должен подтверждаться исходником. `accepted_concepts` содержит примеры
и синонимы; другие обоснованные теги тоже допустимы.
Tag Relevance — доля обоснованных тегов, усреднённая по семи кейсам;
отсутствие тегов даёт 0. Для Completeness нужны 3–7 разных понятий.
