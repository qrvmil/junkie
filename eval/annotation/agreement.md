# Двойная разметка Junkie

## Выборка и метод

Кейсов: **30**. Категории взяты только из поля `category` исходного набора; Категории являются основными метками набора, а не полной таксономией покрытия.

| Категория | Число |
| --- | ---: |
| ambiguity | 3 |
| dates | 4 |
| dialogue_continuation | 3 |
| exact_search | 1 |
| filters | 3 |
| more_than_five_results | 1 |
| no_answer_offtopic | 3 |
| security | 3 |
| semantic_search | 7 |
| typos_languages | 2 |

Сравниваются `preannotation.jsonl` (A) и `preannotation_2.jsonl` (B):
30 кейсов, семь полей разметки. Метрики рассчитаны до согласования.

Пять расхождений относятся к filters: E58, E69, E72, E82, E133.
Решения и причины хранятся в `adjudication.jsonl`, итог — в `final_gold.jsonl`.
История последующей коррекции E82 — в `gold_corrections.jsonl`.
SHA-256 исходных входов приведены в отчёте.

## Согласие до согласования

| Метрика | Значение |
| --- | ---: |
| Percent Agreement действий | 100.00% (30/30) |
| Cohen's Kappa | 1.000000 |
| Exact Set Agreement документов | 100.00% (26/26) |
| Mean Jaccard документов | 1.000000 |
| Exact Match filters | 83.33% (25/30) |
| Agreement order_by | 100.00% (30/30) |
| Agreement has_more | 100.00% (30/30) |
| Exact Set Agreement clarify_candidates | N/A (нет применимых кейсов) |

Документы: 26 применимых кейсов, где хотя бы один разметчик выбрал `search`. Пары search/clarify, search/refuse и search/no_result включаются и сравнивают реальные множества с пустым. Совместные no_result, clarify и refuse исключаются: пустые множества не повышают оценку. Jaccard = |A ∩ B| / |A ∪ B|, затем невзвешенное среднее по кейсам. Порядок ID не учитывается. Фильтры сравниваются как JSON-объекты с точным совпадением значений, без учёта порядка ключей. Фильтры и сортировка сравниваются на всей выборке.

Применимые ID: E06, E15, E20, E21, E31, E35, E38, E41, E43, E46, E48, E55, E57, E58, E61, E63, E69, E72, E74, E82, E87, E89, E91, E93, E133, E135.

Исключённые ID: E24, E27, E78, E79.

Для Kappa: pₒ = 1.000000, pₑ = 0.760000; κ = (pₒ − pₑ) / (1 − pₑ). При pₑ = 1 выводится null/N/A.

### Матрица действий

Строки — A, столбцы — B. Вне диагонали — несовпадения.

| A / B | search | clarify | no_result | refuse |
| --- | ---: | ---: | ---: | ---: |
| search | 26 | 0 | 0 | 0 |
| clarify | 0 | 0 | 0 | 0 |
| no_result | 0 | 0 | 2 | 0 |
| refuse | 0 | 0 | 0 | 2 |

## Несовпадения и согласование

Кейсов с любым расхождением: **5**. Учитываются все поля разметки, включая кандидатов и has_more.

| ID | Расходящиеся поля | Действие A → B → final | Итоговое решение |
| --- | --- | --- | --- |
| E58 | filters | search → search → search | Выбран B: явно запрошенный формат pptx сохранён. У doc_028 отсутствует doc_type в манифесте; фильтр presentation предполагал бы недостающие метаданные. Требование слайдов по PCA учитывается при релевантности. |
| E69 | filters | search → search → search | Выбран B: требование презентации о наивном Байесе учтено выбором doc_027. Поле doc_type у документа отсутствует, поэтому presentation не добавляется как точный фильтр по метаданным. Формат файла явно не ограничен. |
| E72 | filters | search → search → search | Выбран B: оба экзамена ML1 сохранены в выдаче. У doc_019 и doc_020 нет doc_type в манифесте; слово «экзамен» ограничивает релевантность без неподтверждённого фильтра exam. |
| E82 | filters | search → search → search | Текущий итог после проверки применимости: doc_020 сохранён, filters пусты. В манифесте отсутствуют doc_type и content_events; год 2026 различает версию в имени файла и контексте, но не задаёт подтверждённую дату события. Первоначально выбран B; прежнее итоговое решение сохранено в gold_corrections.jsonl. Исходные A/B и метрики согласия не изменены. |
| E133 | filters | search → search → search | Выбран A: «второй бланк» однозначно выбирает doc_008 из упорядоченной предыдущей выдачи [doc_007, doc_008]. Значение application_form есть в метаданных, но новый фильтр не требуется для выбора уже показанного документа по номеру. |

### Общие ошибки, исправленные после сравнения

Эти записи совпадали в A/B и не входят в число исходных расхождений. Их исправления записаны отдельно в арбитраже и не меняют метрики согласия.

| ID | Исправление |
| --- | --- |
| E31 | Исправлена общая ошибка после сравнения: A и B совпадают, но фильтр doc_type=seminar несовместим с возвращаемым doc_004, у которого поле doc_type отсутствует. По согласованному правилу точных фильтров doc_type удалён; оба релевантных документа doc_004 и doc_023 сохранены. Этот случай не входит в пять исходных расхождений. |

Согласование выполнено для всех 5 спорных кейсов; дополнительно исправлено совпавших записей: 1. `final_gold.jsonl` содержит 30 записей. Записи, не включённые в арбитраж, перенесены без смысловых изменений; оригинальные A/B сохранены. Полные исходные и итоговые объекты рассмотренных случаев находятся в `adjudication.jsonl`.

Итоговые действия: no_result: 2, refuse: 2, search: 26.

## Вывод и воспроизведение

Полное исходное совпадение по всем полям: 25/30. Решения по спорным случаям перечислены выше.

Все метрики согласия в этом отчёте и `agreement.json` вычислены из неизменённых A/B до согласования. Арбитраж не подменяет входы метрик. Схема фильтров и процедура описаны в README.

```sh
python3 eval/annotation/scripts/validate_annotations.py eval/annotation/preannotation.jsonl eval/annotation/preannotation_2.jsonl eval/annotation/final_gold.jsonl --check-adjudication --annotator-a eval/annotation/preannotation.jsonl --annotator-b eval/annotation/preannotation_2.jsonl
python3 eval/annotation/scripts/calculate_agreement.py eval/annotation/preannotation.jsonl eval/annotation/preannotation_2.jsonl --output-json eval/annotation/agreement.json --output-md eval/annotation/agreement.md --method-file eval/annotation/annotation_method.md --adjudication eval/annotation/adjudication.jsonl --final eval/annotation/final_gold.jsonl
python3 -m unittest discover -s eval/annotation/scripts -p 'test_*.py'
```

### SHA-256 исходных входов метрик

| Файл | SHA-256 |
| --- | --- |
| annotator_a | `e7f579f513c7565b27131962b2e9996da115df6af667ff409590fb7e005ba410` |
| annotator_b | `30d0b0996538e3c6b7e28b254fa769a4bafab96f6ecca47c8268dd22c8355fc4` |
| blind_cases | `1e591f06b5d50fbbf30aabbc90e98cea4a3822b0ad2bc17702d3a4bfdb8397b6` |
| documents | `cc2153ac5a173f29b05c5dda495f06666a755d35844d7ab83ac22cddf0505db7` |
| environment | `7161879afa79d6ca9f8dcff14120ef3f61b8b8ab72993fceb3896c0188e03d39` |
