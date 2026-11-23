# Результаты КТ3

Сохранённые запуски: [Actions 1](https://github.com/qrvmil/junkie/actions/runs/45030212224), [Actions 2](https://github.com/qrvmil/junkie/actions/runs/45066928131).
Значения долей приведены от 0 до 1. `pending` — оценка не завершена,
`not_applicable` — проверка неприменима. Сравнение на одном открытом dev-наборе; версии запусков указаны ниже.
Precision@5 всегда делится на 5: один правильный документ даёт 0,2,
даже если других релевантных документов в задаче нет.

## Поиск и действия

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ActionAccuracy | 0.7286 | 0.7286 | 0.9000 |
| DialogueSuccessRate | 0.2500 | 0.2500 | 0.5000 |
| FalseRefusalRate | 0.0000 | 0.0000 | 0.0000 |
| HitRate@5 | 0.6034 | 0.7069 | 0.8966 |
| MRR@5 | 0.4920 | 0.6451 | 0.8348 |
| OverflowFullPassRate | 0.7333 | 0.7333 | 1.0000 |
| OverflowHandling | 0.7333 | 0.7333 | 1.0000 |
| Precision@5 | 0.2017 | 0.2207 | 0.3276 |
| PromptInjectionSuccessRate | 0.0000 | 0.0000 | 0.0000 |
| Recall@5 | 0.5110 | 0.6223 | 0.8015 |
| TypoCleanHitRate@5 | 0.9091 | 1.0000 | 0.9091 |
| TypoHitRateDrop | 0.5455 | 0.6364 | 0.0000 |
| TypoVariantHitRate@5 | 0.3636 | 0.3636 | 0.9091 |

## Условия запроса

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ConstraintPrecision@5/AddedDate | 0.3733 | 0.3333 | 0.8133 |
| ConstraintPrecision@5/ContentDate | 0.1333 | 0.2000 | 0.2000 |
| ConstraintPrecision@5/DocType | 0.2000 | 0.2333 | 0.2333 |
| ConstraintPrecision@5/Format | 0.5053 | 0.5053 | 0.5053 |
| DateOrderAccuracy@5 | 1.0000 | 1.0000 | 1.0000 |

## Добавление и метаданные

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ExtractionCoverage | 1.0000 | 1.0000 | 1.0000 |
| IngestionSuccessRate | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Corrupted | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Format | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Size | 1.0000 | 1.0000 | 1.0000 |
| MetadataCompleteness/FullPassRate | 0.5714 | 0.5714 | 0.8571 |
| MetadataCompleteness/mean | 0.9143 | 0.9143 | 0.9714 |
| MetadataCorrectness/AddedDate | 1.0000 | 1.0000 | 1.0000 |
| MetadataCorrectness/Description | 0.5714 | 0.5714 | 0.8571 |
| MetadataCorrectness/Title | 0.1429 | 0.1429 | 0.7143 |
| MetadataCorrectness/Topic | 0.0000 | 0.0000 | 0.4286 |
| TagRelevance | 0.7024 | 0.7024 | 1.0000 |

## Проверки контракта и сценариев

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ArchiveAccess | 1.0000 | 1.0000 | 1.0000 |
| BudgetExhaustion | 1.0000 | 1.0000 | 1.0000 |
| ClarificationUseful | 0.0000 | 0.0000 | 0.5000 |
| FilterCompliance | 0.5854 | 0.5610 | 0.9024 |
| InitialState | 1.0000 | 1.0000 | 1.0000 |
| ParsedQuery | 0.6308 | 0.6308 | pending |
| RequiredCalls | 0.8429 | 0.8429 | 0.8643 |
| ResultLimit | 1.0000 | 1.0000 | 1.0000 |
| ResultUniqueness | 1.0000 | 1.0000 | 1.0000 |
| RunStatus | 1.0000 | 1.0000 | 1.0000 |
| ScenarioSuccess | 0.2857 | 0.2857 | 0.7143 |
| Sources | 1.0000 | 1.0000 | 1.0000 |
| StepBudget | 1.0000 | 1.0000 | 1.0000 |
| Termination | 1.0000 | 1.0000 | 1.0000 |
| ToolArguments | 1.0000 | 1.0000 | 1.0000 |
| ToolErrorRecovery | 0.0000 | 0.0000 | 1.0000 |
| ToolErrors | 1.0000 | 1.0000 | 1.0000 |
| Trace | 1.0000 | 1.0000 | 1.0000 |
| Turn1 | 0.5714 | 0.5714 | 0.8571 |
| Turn2 | 0.4000 | 0.4000 | 0.8000 |
| Turn3 | 0.0000 | 0.0000 | 1.0000 |
| Turns | 1.0000 | 1.0000 | 1.0000 |
| input_action | 1.0000 | 1.0000 | 1.0000 |
| input_reason | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/description | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/tags | 0.5714 | 0.5714 | 0.8571 |
| metadata_present/title | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/topic | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/uploaded_at | 1.0000 | 1.0000 | 1.0000 |
| model_gate | 1.0000 | 1.0000 | 1.0000 |
| searchable | 1.0000 | 1.0000 | 1.0000 |
| source_openable | 1.0000 | 1.0000 | 1.0000 |
| source_saved | 1.0000 | 1.0000 | 1.0000 |
| text_extracted | 1.0000 | 1.0000 | 1.0000 |
| within_ingestion_timeout | 1.0000 | 1.0000 | 1.0000 |

## Время

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| search P50, мс | 2.9470 | 1.3811 | 840.5014 |
| search P95, мс | 10.2656 | 6.2791 | 6829.4738 |
| ingestion P50, мс | 2.1953 | 2.4717 | 1278.8447 |
| ingestion P95, мс | 111.4829 | 78.0131 | 1440.7092 |
| Подготовка индекса, с | 45.1943 | 46.9251 | 73.2525 |
| Весь прогон с оценщиком, с | 60.4439 | 59.0250 | 341.6340 |

## Расход OpenRouter, USD

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| search | 0.0000 | 0.0000 | 0.0507 |
| clean_queries | 0.0000 | 0.0000 | 0.0038 |
| ingestion | 0.0000 | 0.0000 | 0.0110 |
| scenarios | 0.0000 | 0.0000 | 0.0048 |
| judge | 0.0040 | 0.0039 | 0.0058 |

## Многошаговые сценарии

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| S01 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 0.0000 | 0.0000 | 0.0000 |
| S03 | 0.0000 | 0.0000 | 1.0000 |
| S04 | 1.0000 | 1.0000 | 1.0000 |
| S05 | 0.0000 | 0.0000 | 1.0000 |
| S06 | 1.0000 | 1.0000 | 1.0000 |
| S07 | 0.0000 | 0.0000 | 1.0000 |

## Условия

| Вариант | Run ID | Commit замера | Модель |
|---|---|---|---|
| B0 | `b0-20261122T135842Z-1` | `cc92f4e0854b919e4067674bddd52fdc3aa4f30a` | `без модели` |
| B1 | `b1-20261122T135945Z-1` | `cc92f4e0854b919e4067674bddd52fdc3aa4f30a` | `без модели` |
| Junkie | `junkie-20261122T203305Z-1` | `73638022aa5c53a38137cfa95ca4efa3eaba7026` | `google/gemini-3.5-flash-lite` |

- Состояние смысловой оценки метаданных видно в таблице; H0 не проводился.
- `ParsedQuery` проверяет точное совпадение с gold, включая случаи эквивалентного разбора.
- Поиск измерен на готовом индексе; ingestion заново извлекает текст.
- `saved://` открывается внутри локального архива; HTTP-раздача файлов не реализована.
- PISR проверяет изоляцию: содержимое найденных файлов не передаётся в LLM-планировщик.
- Расход API не включает стоимость компьютера, Actions и ручного труда.

- Незавершённые наблюдения Junkie: E26 `ParsedQuery` — Parsed query was not recorded.
