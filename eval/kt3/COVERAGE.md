# Покрытие КТ3

«Реализовано» ниже означает наличие оценщика, а не успешный прогон системы.
Проверки наблюдений требуют подключения runner. Gold остаётся из КТ2.

| Контракт / требование | Метрика или проверка | Данные / выборка | Как оцениваем |
|---|---|---|---|
| Нужный материал в выдаче, §2.1 | HitRate@5, MRR@5, Recall@5, Precision@5 | 116 gold=search, порядок ID | Код; правила КТ2 |
| Выбор действия, §2.1–2.3 | ActionAccuracy, FalseRefusalRate | 140 / 116 кейсов | Код; отдельно по gold-действиям |
| Формат материала | ConstraintPrecision@5/Format | 19 search-кейсов | Метаданные корпуса |
| Тип документа | ConstraintPrecision@5/DocType | 6 search-кейсов | Метаданные корпуса, без угадывания |
| Дата добавления | ConstraintPrecision@5/AddedDate | 15 search-кейсов | Даты с учётом fixture |
| Дата события | ConstraintPrecision@5/ContentDate | 3 search-кейса | content_events, вид события и диапазон |
| Все явные фильтры, включая источник | FilterCompliance | Gold filters и фактическая выдача | Проверка атрибутов выданных документов, включая source_type |
| Совпадение разбора с эталоном | ParsedQuery | Gold filters/order_by и фактический разбор | Точное совпадение; эквивалентный разбор тоже может получить 0 |
| Порядок по дате | DateOrderAccuracy@5 | E57, E111 | Сравнимые пары дат |
| Устойчивость к опечаткам | TypoHitRateDrop и оба HitRate | 11 пар query/clean_query | Отдельные парные запуски |
| Более пяти совпадений, §2.1 | OverflowHandling, OverflowFullPassRate | 15 кейсов с has_more | Код: документы; LLM: сообщение и предложение сузить |
| Полезное уточнение, §3.1 | ClarificationUseful | 6 gold=clarify | LLM с запросом, контекстом и кандидатами |
| Достижение цели диалога, §2.3 | DialogueSuccessRate | S01–S04 | Реальные шаги и конечная цель |
| Добавление, §2.1 | IngestionSuccessRate | I01–I07 | Сохранён, открывается, извлечён, доступен поиску |
| Невалидные входы | InvalidInput/Format, /Size, /Corrupted | I08–I10 | Причина отказа, model gate |
| Сохранность текста | ExtractionCoverage | 33 фрагмента, 7 входов | Нормализация и поиск эталонных фрагментов |
| Поля добавленного документа | MetadataCompleteness/mean, /FullPassRate | I01–I07 | Код + ручная проверка разных понятий тегов |
| Смысл метаданных | MetadataCorrectness/Title, /Description, /Topic | I01–I07 | Ручная оценка по must_convey/must_not_claim |
| Дата добавления в ответе | MetadataCorrectness/AddedDate | I01–I07 | Дата case.now в case.timezone |
| Обоснованность тегов | TagRelevance | I01–I07 | Ручная оценка каждого тега |
| Инструкции внутри документов | PromptInjectionSuccessRate | E87 | Canary, выдача, полный трейс прочитанных документов |
| Изоляция архивов | ArchiveAccess | Выдача и все чтения | Проверка владельца с учётом fixture |
| Источники, §3.1 | Sources | Карточки и observations.source_checks | Открытие документа и подтверждение фрагмента |
| Лимит и уникальность выдачи | ResultLimit, ResultUniqueness | Все ответы | Код |
| Контракты инструментов | RequiredCalls, ToolArguments, ToolErrors | expected_calls и trace | Имя, типы аргументов/ошибок, явно разрешённые альтернативы |
| Задержка, §3.2 | Search/Ingestion P50, P95 | elapsed_ms и исходы | Отдельно от числа сбоев |
| Стоимость КТ3 | cost_usd, токены | Полный usage всех попыток | Система и судья отдельно |
| Ошибка инструмента, бюджет, полный цикл | ScenarioSuccess | S05–S07 | Трейсы и заданные условия завершения |
| Качество разметки КТ2 | Agreement, Cohen’s κ | 30 двойных разметок | Существующие annotation/agreement.*; не пересчитываем по ответам системы |

Не измерены: качество/время/стоимость B0, B1 и Junkie, живые сценарии,
согласованность LLM-судьи с человеком. Зашифрованный holdout не используется.
