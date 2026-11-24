# Результаты КТ3

[Запуск Actions](https://github.com/qrvmil/junkie/actions/runs/45030212224).
Значения долей приведены от 0 до 1. `pending` — оценка не завершена,
`not_applicable` — проверка неприменима. Это один прогон открытого dev-набора.
Precision@5 всегда делится на 5: один правильный документ даёт 0,2,
даже если других релевантных документов в задаче нет.

## Поиск и действия

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ActionAccuracy | 0.7286 | 0.7286 | 0.8000 |
| DialogueSuccessRate | 0.2500 | 0.2500 | 0.5000 |
| FalseRefusalRate | 0.0000 | 0.0000 | 0.0000 |
| HitRate@5 | 0.6034 | 0.7069 | 0.8017 |
| MRR@5 | 0.4920 | 0.6451 | 0.7565 |
| OverflowFullPassRate | 0.7333 | 0.7333 | 1.0000 |
| OverflowHandling | 0.7333 | 0.7333 | 1.0000 |
| Precision@5 | 0.2017 | 0.2207 | 0.3052 |
| PromptInjectionSuccessRate | 0.0000 | 0.0000 | 0.0000 |
| Recall@5 | 0.5110 | 0.6223 | 0.7109 |
| TypoCleanHitRate@5 | 0.9091 | 1.0000 | 0.9091 |
| TypoHitRateDrop | 0.5455 | 0.6364 | 0.5455 |
| TypoVariantHitRate@5 | 0.3636 | 0.3636 | 0.3636 |

## Условия запроса

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ConstraintPrecision@5/AddedDate | 0.3733 | 0.3333 | 0.8133 |
| ConstraintPrecision@5/ContentDate | 0.1333 | 0.2000 | 0.1333 |
| ConstraintPrecision@5/DocType | 0.2000 | 0.2333 | 0.0667 |
| ConstraintPrecision@5/Format | 0.5053 | 0.5053 | 0.5474 |
| DateOrderAccuracy@5 | 1.0000 | 1.0000 | 1.0000 |

## Добавление и метаданные

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ExtractionCoverage | 1.0000 | 1.0000 | 1.0000 |
| IngestionSuccessRate | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Corrupted | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Format | 1.0000 | 1.0000 | 1.0000 |
| InvalidInput/Size | 1.0000 | 1.0000 | 1.0000 |
| MetadataCompleteness/FullPassRate | pending | pending | pending |
| MetadataCompleteness/mean | pending | pending | pending |
| MetadataCorrectness/AddedDate | 1.0000 | 1.0000 | 1.0000 |
| MetadataCorrectness/Description | pending | pending | pending |
| MetadataCorrectness/Title | pending | pending | pending |
| MetadataCorrectness/Topic | pending | pending | pending |
| TagRelevance | pending | pending | pending |

## Проверки контракта и сценариев

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| ArchiveAccess | 1.0000 | 1.0000 | 1.0000 |
| BudgetExhaustion | 1.0000 | 1.0000 | 1.0000 |
| ClarificationUseful | 0.0000 | 0.0000 | 0.0000 |
| FilterCompliance | 0.5854 | 0.5610 | 0.8537 |
| InitialState | 1.0000 | 1.0000 | 1.0000 |
| ParsedQuery | 0.6308 | 0.6308 | pending |
| RequiredCalls | 0.8429 | 0.8429 | 0.8929 |
| ResultLimit | 1.0000 | 1.0000 | 0.9857 |
| ResultUniqueness | 1.0000 | 1.0000 | 0.9857 |
| RunStatus | 1.0000 | 1.0000 | 1.0000 |
| ScenarioSuccess | 0.2857 | 0.2857 | 0.7143 |
| Sources | 1.0000 | 1.0000 | 0.9828 |
| StepBudget | 1.0000 | 1.0000 | 1.0000 |
| Termination | 1.0000 | 1.0000 | 1.0000 |
| ToolArguments | 1.0000 | 1.0000 | 1.0000 |
| ToolErrorRecovery | 0.0000 | 0.0000 | 1.0000 |
| ToolErrors | 1.0000 | 1.0000 | 1.0000 |
| Trace | 1.0000 | 1.0000 | 1.0000 |
| Turn1 | 0.5714 | 0.5714 | 0.7143 |
| Turn2 | 0.4000 | 0.4000 | 0.6000 |
| Turn3 | 0.0000 | 0.0000 | 1.0000 |
| Turns | 1.0000 | 1.0000 | 1.0000 |
| input_action | 1.0000 | 1.0000 | 1.0000 |
| input_reason | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/description | 1.0000 | 1.0000 | 1.0000 |
| metadata_present/tags | pending | pending | pending |
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
| search P50, мс | 2.9470 | 1.3811 | 877.8998 |
| search P95, мс | 10.2656 | 6.2791 | 1286.3730 |
| ingestion P50, мс | 2.1953 | 2.4717 | 1242.6115 |
| ingestion P95, мс | 111.4829 | 78.0131 | 1345.4638 |
| Подготовка индекса, с | 45.1943 | 46.9251 | 47.0785 |
| Весь прогон с оценщиком, с | 60.4439 | 59.0250 | 221.7993 |

## Расход OpenRouter, USD

| Показатель | B0 | B1 | Junkie |
|---|---:|---:|---:|
| search | 0.0000 | 0.0000 | 0.0401 |
| clean_queries | 0.0000 | 0.0000 | 0.0031 |
| ingestion | 0.0000 | 0.0000 | 0.0062 |
| scenarios | 0.0000 | 0.0000 | 0.0038 |
| judge | 0.0040 | 0.0039 | 0.0050 |

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

- Commit: `cc92f4e0854b919e4067674bddd52fdc3aa4f30a`.
- Модель: `google/gemini-3.5-flash-lite`.
- Ручная оценка смысла метаданных и H0 не выполнены.
- `ParsedQuery` проверяет точное совпадение с gold, включая случаи эквивалентного разбора.
- Поиск измерен на готовом индексе; ingestion заново извлекает текст.
- `saved://` открывается внутри локального архива; HTTP-раздача файлов не реализована.
- PISR проверяет изоляцию: содержимое найденных файлов не передаётся в LLM-планировщик.
- Расход API не включает стоимость компьютера, Actions и ручного труда.
