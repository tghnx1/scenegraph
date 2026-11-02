# promoter-role-classification - Work Plan

## TL;DR (For humans)
Рекомендации будут учитывать организаторов конкретного события, а совпадающие профили площадок и их алиасы смогут проверяться отдельно. Роли вводятся в shadow, затем включаются постепенно после проверки качества и затрат.

**Масштаб:** XL. **Риск:** высокий: ошибки классификации могут скрыть настоящего промоутера или повлиять на production-кэш.

## Scope

**Пользователи:** артисты получают релевантные рекомендации; оператор проверяет причины решений, стоимость и статус обработки.

| Цель | Результат | Причина |
| --- | --- | --- |
| IS-1 | Роли определяются по событию и имеют проверяемое основание | Площадка может быть организатором |
| IS-2 | Рекомендации, граф и кэш используют одинаковые актуальные роли | Исключить противоречивую выдачу |
| IS-3 | Историческая обработка ограничена, возобновляется и поддаётся аудиту | Контроль данных и расходов |
| IS-4 | Качество измерено до постепенного включения и доступен откат | Сохранить настоящих организаторов |

**Границы:** исходные RA-связи и ID сохраняются; не выдумывать RA ID, не объединять неподтверждённые алиасы, не включать массовый backfill или enforce без предусмотренных измерений и лимитов. Не затрагивать незакоммиченные изменения supervisor и ingestion, кроме аккуратной интеграции без их перезаписи.

## Verification strategy

Tests-after с pytest и настоящим PostgreSQL для ограничений и транзакций. Внешний LLM в CI заменяется управляемым fake; оценка реальной модели использует ту же конфигурацию Kimi, что ingestion; денежный и токенный потолок не задан. Артефакты складывать в `.omo/evidence/`; отсутствие доступа или неподготовленная разметка не считаются успешной проверкой.

## Execution strategy

Волна 1: задачи 1–2. Волна 2: 3–4. Волна 3: 5–7. Волна 4: 8. Волна 5: 9. Зависимости указаны в каждой задаче; исполнители не должны одновременно изменять общие файлы без согласования.

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Baseline и контрольная выборка
  Recommended task executor category: unspecified-high
  What to do: из production через SSM выполнить только SELECT в read-only транзакции; измерить рекомендации с профилями площадок, сохранить обезличенный baseline и размеченный набор, включая примеры из docs/promoter-role-review-sample.md, события без промоутеров и похожие имена. Гипотезы вручную проверить по исходнику, разделить данные для настройки и отложенной проверки. Не фиксировать секреты или полный production payload.
  Parallelization: Wave 1 | Blocked by: none | Blocks: 3, 8, 10
  References: docs/promoter-classification-spec.md; backend/app/recommendations/services.py; backend/app/recommendations/jobs.py.
  Acceptance/QA: документ содержит SQL, дату, размеры выборок, метрики и спорные случаи; воспроизвести SELECT на тестовой БД; отсутствие production-доступа явно блокирует production-baseline. Evidence: .omo/evidence/task-1-baseline.txt.
  Commit: Y | docs(recommendations): establish promoter role baseline
- [ ] 2. Миграции и хранилище ролей, алиасов и кандидатов
  Recommended task executor category: unspecified-high
  What to do: добавить schema и миграцию в backend/prisma для promoter_event_role, promoter_identity/member, event_organizer_candidate и записей backfill по спецификации; FK ролей к events/promoters, а не к пересоздаваемым event_promoters; уникальные ключи, статусы, confidence, hash и приоритет ручных решений. Не менять исходные RA ID.
  Parallelization: Wave 1 | Blocked by: none | Blocks: 3, 4, 5, 6, 7
  Acceptance/QA: PostgreSQL integration tests применяют миграцию и проверяют ограничения, повторный импорт и ручной override; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_store_db.py`. Evidence: .omo/evidence/task-2-schema.txt.
  Commit: Y | feat(promoters): persist event roles and identities
- [ ] 3. Правила и воспроизводимый hash
  Recommended task executor category: unspecified-high
  What to do: создать backend/app/promoter_roles/ с нормализацией Unicode, типами, входным hash и классификацией по свидетельствам; подтверждённые алиасы считать одной сущностью, неподтверждённые не объединять; unknown при неоднозначности, ручное решение приоритетно.
  Parallelization: Wave 2 | Blocked by: 1, 2 | Blocks: 4, 5, 6
  Acceptance/QA: pytest проверяет 8MM presents, at, похожие названия, двойные алиасы, несколько организаторов, изменение hash и повтор; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_rules.py`. Evidence: .omo/evidence/task-3-rules.txt.
  Commit: Y | feat(promoters): classify event roles deterministically
- [ ] 4. LLM-классификация и кандидаты из текста
  Recommended task executor category: unspecified-high
  What to do: использовать существующий настраиваемый provider клиент; ограниченный JSON по входным ID с ролью, уверенностью и проверяемым фрагментом; проверять schema, ID, источник цитаты; события без RA-промоутера сохранять как кандидаты без фиктивных RA ID. Ограничить размер входа; использовать тот же provider/model из окружения, что ingestion; денежного и токенного потолка нет, ошибки/квоты дают unknown и безопасный retry.
  Parallelization: Wave 2 | Blocked by: 2, 3 | Blocks: 5, 7, 8
  References: backend/app/artist_tag_extraction.py; backend/app/event_tag_extraction.py.
  Acceptance/QA: fake provider тестирует корректный и некорректный JSON, поддельные ID/цитаты, квоту и недоступность; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_llm.py`. Evidence: .omo/evidence/task-4-llm.txt.
  Commit: Y | feat(promoters): classify ambiguous organizer evidence
- [ ] 5. Интеграция с импортом и очередью
  Recommended task executor category: unspecified-high
  What to do: после импорта ставить новые/изменённые события на классификацию, повторно использовать актуальные hash/версию, сохранять прогресс и не останавливать импорт из-за LLM; учитывать удаление и пересоздание event_promoters, гонку с импортом и ручные решения; не перезаписывать существующие изменения supervisor.
  Parallelization: Wave 3 | Blocked by: 2, 3, 4 | Blocks: 7, 8
  References: backend/scripts/import_events.py; backend/scripts/full_pipeline.py.
  Acceptance/QA: integration pytest подтверждает повторный импорт, удаление связи, смену hash, конкурентное изменение, сбой провайдера; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_ingestion.py`. Evidence: .omo/evidence/task-5-import.txt.
  Commit: Y | feat(ingestion): schedule promoter classification
- [ ] 6. Единый фильтр рекомендаций и кэш
  Recommended task executor category: unspecified-high
  What to do: единый слой выбора актуальных organizer/both и подтверждённых канонических ID для services, graph, event_similarity, helpers, scoring, объяснений и feedback; off сохраняет прежнее поведение, shadow отдельно сравнивает, enforce исключает unknown/устаревшие; версия и режим в кэше, затронутые результаты инвалидировать, обеспечить обратный переход.
  Parallelization: Wave 3 | Blocked by: 2, 3 | Blocks: 8, 9
  References: backend/app/recommendations/services.py, promoter_graph.py, event_similarity.py, helpers.py, jobs.py, promoter_feedback.py.
  Acceptance/QA: PostgreSQL и API pytest проверяют все ветви, дедупликацию и объяснения, неизвестные роли, stale cache, смену режима и rollback; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_recommendations.py tests/test_promoter_graph.py tests/test_recommendation_jobs_invalidation.py`. Evidence: .omo/evidence/task-6-recommendations.txt.
  Commit: Y | feat(recommendations): respect event promoter roles
- [ ] 7. Ограниченный возобновляемый backfill
  Recommended task executor category: unspecified-high
  What to do: реализовать CLI с обязательным ограничением scope, dry-run по умолчанию без записи, оценкой токенов, явным apply, без денежного и токенного потолка, с транзакционным прогрессом, advisory lock, bounded retry и проверкой hash перед записью; квоту фиксировать как остановку с продолжением.
  Parallelization: Wave 3 | Blocked by: 2, 4, 5 | Blocks: 8, 9
  Acceptance/QA: pytest доказывает отсутствие изменений в dry-run, гонку, прерывание/resume, лимиты и конкурентную блокировку; `cd backend && PYTHONPATH=. pytest -q tests/test_promoter_role_backfill.py`. Evidence: .omo/evidence/task-7-backfill.txt.
  Commit: Y | feat(promoters): add bounded classification backfill
- [ ] 8. Оценка качества и сравнение shadow
  Recommended task executor category: unspecified-high
  What to do: до rollout прогнать отложенную разметку, измерить precision/recall и ошибки исключения, сравнить старые и shadow рекомендации репрезентативных артистов, вручную проверить примеры, затраты и unknown; применить пороги precision ≥ 80% и recall ≥ 80% на отложенной выборке, считая unknown для реального организатора пропуском; пустой знаменатель блокирует enforce.
  Parallelization: Wave 4 | Blocked by: 1, 4, 5, 6, 7 | Blocks: 9
  Acceptance/QA: воспроизводимый отчёт с командами, размерами, ошибками и затратами; полный backend `cd backend && PYTHONPATH=. pytest -q` на подготовленной тестовой БД; отсутствие доступного LLM или разметки фиксируется как блокер enforce. Evidence: .omo/evidence/task-8-evaluation.txt.
  Commit: Y | test(promoters): evaluate role classification
- [ ] 9. Поэтапный rollout и откат
  Recommended task executor category: unspecified-high
  What to do: подготовить команды миграции, off, shadow, ограниченного backfill, allowlist и enforce, проверки health/cache и rollback; production выполнять лишь после успешных проверок и достижения порогов precision/recall ≥ 80%, сохранить контроль результатов каждого этапа.
  Parallelization: Wave 5 | Blocked by: 6, 7, 8 | Blocks: final verification
  References: docker-compose.prod.yml; docs/production-delivery.md; docs/promoter-classification-spec.md.
  Acceptance/QA: на тестовой среде воспроизвести off → shadow → allowlist → rollback, доказать отсутствие старого кэша; production этапы зафиксировать с реальными результатами или отметить невыполненными. Evidence: .omo/evidence/task-9-rollout.txt.
  Commit: Y | docs(promoters): document safe rollout

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit
- [ ] F2. Code quality review
- [ ] F3. Real manual QA
- [ ] F4. Ideal-state fidelity

## Commit strategy

Атомарные коммиты по задачам после проверки diff; не включать существующие пользовательские изменения. Push/deploy выполнять только в рамках авторизованного rollout.

## Success criteria

| Цель | Задачи | Проверка |
| --- | --- | --- |
| IS-1 | 1–4 | Размеченная выборка, тесты правил и валидации LLM |
| IS-2 | 5–6 | Интеграционные тесты всех веток рекомендаций и инвалидирования кэша |
| IS-3 | 7 | Dry-run без записи, лимиты и возобновление после прерывания |
| IS-4 | 8–9 | Отложенная оценка качества, shadow, allowlist и проверенный откат |
