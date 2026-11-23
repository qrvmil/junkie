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

# Происхождение и согласование A/B-разметки КТ-2

Первоначальную разметку одних и тех же 30 кейсов из
[`blind_cases.jsonl`](blind_cases.jsonl) независимо и с нуля выполнили два
участника команды: **Юрий Степанов** — A
([`preannotation.jsonl`](preannotation.jsonl)) и **Егор Островенко** — B
([`preannotation_2.jsonl`](preannotation_2.jsonl)). Соответствие имён и способ
работы подтверждены Егором, участником команды, 23.11.2026. Названия файлов
`preannotation*` исторические: в данном сравнении это исходные A/B, а не
результат последующего review. A внесён коммитом [`90ddcea`](https://github.com/qrvmil/junkie/commit/90ddcead6ee1c36582d39aab5e53e44e93ab9bd1),
B — [`c5ed58f`](https://github.com/qrvmil/junkie/commit/c5ed58f817993e2f42159e79184ed8499608a8ce).
Автор коммита B сам по себе не доказывает авторство разметки; источник этого
сведения — подтверждение участника.

Оба файла содержат семь полей разметки на кейс. После завершения A и B были
проверены схема, покрытие 30 кейсов, существование документов и доступ по
fixtures. [`calculate_agreement.py`](scripts/calculate_agreement.py) сравнивает
исходные A/B **до согласования**: действия (Percent Agreement и Cohen’s κ),
множества релевантных документов (Exact Set и средний Jaccard на случаях с
хотя бы одним `search`), фильтры, сортировку, `has_more` и кандидатов уточнения.
Порядок ID и ключей JSON-объекта не влияет на сравнение. Результат и SHA-256
входов находятся в [`agreement.md`](agreement.md) и
[`agreement.json`](agreement.json).

Все пять исходных расхождений относятся к `filters`: E58, E69, E72, E82 и
E133. Основной агент по запросам, контексту и полям манифеста разобрал
расхождения; Егор подтвердил выбор B для E58, E69, E72, первоначально E82,
и A для E133. Полные неизменённые A/B, итоговые решения и причины записаны в
[`adjudication.jsonl`](adjudication.jsonl). При применении согласованного
правила обнаружена также общая ошибка E31: A и B совпали, но `doc_type=seminar`
не подтверждался метаданными одного из выбранных документов. Это не шестое
расхождение; исправление сделано только в итоговой записи. Позднее отдельно
проверена применимость фильтра даты для E82, и это решение исправлено; прежний
и новый gold записаны в [`gold_corrections.jsonl`](gold_corrections.jsonl).
Исходные A/B ради согласия не менялись.

Согласованные 30 решений лежат в [`final_gold.jsonl`](final_gold.jsonl).
[`validate_annotations.py`](scripts/validate_annotations.py) сверяет их с
арбитражем, а [`validate_eval.py`](scripts/validate_eval.py) — общие поля с
[`eval/queries/dev.jsonl`](../queries/dev.jsonl). Именно этот dev-набор
использует харнесс КТ-3; закрытая часть в сравнении не использовалась.

Отдельный [`yuri/annotation-review`](https://github.com/qrvmil/junkie/tree/yuri/annotation-review/eval/annotation/reviews)
содержит последующий review одной показанной в viewer предварительной
разметки. Его экспорт не является исходным A или B, не участвует в расчёте
agreement и не заменяет независимую разметку КТ-2. Полное совпадение по
действиям и документам также не доказывает отсутствие общих ошибок gold;
проверка применимости E31 и E82 показывает эту границу.

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
