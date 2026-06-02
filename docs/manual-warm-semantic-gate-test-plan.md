# Manual Warm Semantic Gate: Test Plan

## Цель
- Проверить, что manual-связи (`artist_manual_connections`) продолжают усиливать рекомендации.
- Не допустить жанрового дрейфа, когда нерелевантные manual-друзья вытесняют релевантных промоутеров.

## Область
- Endpoint:
  - `GET /api/recommendations/artists/{artist_id}/promoters`
- Сигналы:
  - `warmConnectionCount`
  - `manualWarmConnectionCount`
  - `scoreBreakdown.warmNetwork`
  - `semanticScore`
- Среда:
  - `scenegraph_check`

## Предпосылки
1. Стек поднят:
```bash
make upd
```
2. Проверочная БД активна:
```bash
docker compose exec -T backend python - <<'PY'
import os
print(os.environ.get("DATABASE_URL"))
PY
```
3. Есть тестовый source artist (по умолчанию `2178`).

## Набор сценариев

### S0 Baseline (без manual-связей)
- Очистить manual-связи для source artist.
- Снять baseline-топ и debug.

### S1 Релевантные manual-связи
- Добавить 3-5 артистов, близких по стилю source.
- Ожидание:
  - ключевые промоутеры поднимаются,
  - semantic релевантность топа не падает.

### S2 Нерелевантные manual-связи (stress)
- Добавить 3-5 артистов с жанрами, далекими от source.
- Ожидание:
  - manual-сигнал не ломает топ-10,
  - нерелевантные промоутеры не доминируют.

### S3 Смешанный набор
- 50/50 релевантные и нерелевантные manual-связи.
- Ожидание:
  - релевантные manual-пути сохраняют влияние,
  - качество топа стабильно.

### S4 Regression на known-case (2178 -> Zee Mon -> K3LLR)
- Проверка, что manual-path реально учитывается как warm.
- Ожидание:
  - `K3LLR` появляется в выдаче,
  - `warmConnectionArtists` содержит `Zee Mon`,
  - `manualWarmConnectionCount >= 1`.

## Метрики
- `Top10/Top20 Semantic Floor`:
  - минимум `semanticScore` в топе.
- `Warm Coverage`:
  - доля рекомендаций с `warmConnectionCount > 0`.
- `Manual Impact`:
  - число рекомендаций, где `manualWarmConnectionCount > 0`.
- `Rank Drift`:
  - смещение позиций целевых промоутеров против baseline.

## Критерии приемки (go/no-go)
- `Top10 semantic floor` не хуже baseline более чем на `0.03`.
- В stress-сценарии доля нерелевантных manual-кандидатов в топ-10 не более `30%`.
- Regression-кейс с `K3LLR` проходит стабильно.

## Подготовка данных (команды)

### 1) Список существующих manual-связей
```bash
docker compose exec -T backend python - <<'PY'
import os, psycopg
SOURCE_ARTIST_ID = 2178
conn = psycopg.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("""
SELECT source_artist_id, connected_artist_id, created_at
FROM artist_manual_connections
WHERE source_artist_id = %s
ORDER BY connected_artist_id
""", (SOURCE_ARTIST_ID,))
for row in cur.fetchall():
    print(row)
conn.close()
PY
```

### 2) Очистить manual-связи (baseline)
```bash
docker compose exec -T backend python - <<'PY'
import os, psycopg
SOURCE_ARTIST_ID = 2178
conn = psycopg.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("DELETE FROM artist_manual_connections WHERE source_artist_id = %s", (SOURCE_ARTIST_ID,))
print("deleted:", cur.rowcount)
conn.close()
PY
```

### 3) Добавить manual-связи (пример)
```bash
curl -s -X POST "http://localhost:8080/api/artists/2178/known-artists" \
  -H "Content-Type: application/json" \
  -d '{"connectedArtistId":1740}' | jq
```

## Снятие snapshot выдачи

### Рекомендации с debug
```bash
curl -s "http://localhost:8080/api/recommendations/artists/2178/promoters?limit=50&exclude_existing=false&debug=true" \
  > /tmp/promoters_2178_debug.json
```

### Короткая сводка
```bash
jq '{
  count: (.recommendations | length),
  warm_count: ([.recommendations[] | select(.warmConnectionCount > 0)] | length),
  manual_count: ([.recommendations[] | select((.debug.rawSignals.manualWarmConnectionCount // 0) > 0)] | length),
  semantic_min: ((.recommendations | map(.semanticScore) | min) // null),
  semantic_max: ((.recommendations | map(.semanticScore) | max) // null)
}' /tmp/promoters_2178_debug.json
```

### Проверка K3LLR regression
```bash
jq '.recommendations
| to_entries
| map(select(.value.id == 227 or .value.name == "K3LLR")
| {rank:(.key+1), id:.value.id, name:.value.name, warm:.value.warmConnectionCount,
   manual:(.value.debug.rawSignals.manualWarmConnectionCount // 0),
   warmArtists:(.value.debug.rawSignals.warmConnectionArtists // [])})' \
/tmp/promoters_2178_debug.json
```

## Сравнение сценариев (baseline vs candidate)

### Сохранить baseline
```bash
cp /tmp/promoters_2178_debug.json /tmp/promoters_2178_baseline.json
```

### Сравнить top-10 по именам и score
```bash
jq -s '{
  baseline_top10: (.[0].recommendations[:10] | map({id,name,score,semanticScore})),
  candidate_top10: (.[1].recommendations[:10] | map({id,name,score,semanticScore}))
}' /tmp/promoters_2178_baseline.json /tmp/promoters_2178_debug.json
```

## Тест-матрица (ручной чеклист)
- [ ] S0 Baseline снят и сохранен.
- [ ] S1 Релевантные manual-связи: warm растет, semantic floor не падает.
- [ ] S2 Нерелевантные manual-связи: топ-10 не деградирует.
- [ ] S3 Смешанный набор: поведение стабильно.
- [ ] S4 `K3LLR` regression проходит.
- [ ] Результаты и артефакты (`/tmp/*.json`) приложены к PR.

## Примечание по feature flag
- Если semantic gate внедряется под флаг, прогонять сценарии в двух режимах:
  - flag `OFF` (baseline behavior)
  - flag `ON` (candidate behavior)
- Для PR обязательно приложить diff метрик между OFF и ON.
