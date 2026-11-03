# Baseline локальной копии для проверки ролей

Снимок production, загруженный локально; проверка 3 ноября 2026 года. Это не разметка и не оценка качества классификатора.

- Событий: 25 435; все 25 435 имеют площадку.
- Событий без связей с RA-профилем промоутера: 5 809.
- Связей, где имена профиля и площадки совпадают после приведения регистра и удаления неалфавитно-цифровых символов: 4 853. Это число связей, а не уникальных событий или подтверждённых ошибочных рекомендаций.
- В 260 сохранённых заданиях с массивом рекомендаций — 26 598 строк рекомендаций; 3 787 строк относятся к профилям, чьё имя совпадает с площадкой хотя бы в одном событии. Хотя бы одно такое совпадение есть в 256 заданиях. Это верхняя оценка кандидатов на проверку, не число неверных рекомендаций: площадка может быть настоящим организатором, а сопоставление не проверяет роль в конкретном событии.

Запросы выполнялись в read-only транзакции. Совпадение имён не доказывает, что профиль не организует событие. Этот baseline не удовлетворяет условию отложенной размеченной выборки из спецификации.

```sql
SELECT count(*), count(*) FILTER (WHERE venue_id IS NOT NULL),
       count(*) FILTER (WHERE NOT EXISTS
         (SELECT 1 FROM event_promoters ep WHERE ep.event_id = e.id))
FROM events e;

SELECT count(*)
FROM event_promoters ep
JOIN promoters p ON p.id = ep.promoter_id
JOIN events e ON e.id = ep.event_id
JOIN venues v ON v.id = e.venue_id
WHERE regexp_replace(lower(p.name), '[^[:alnum:]]', '', 'g') =
      regexp_replace(lower(v.name), '[^[:alnum:]]', '', 'g');

WITH r AS (
  SELECT j.id AS job_id, x->>'id' AS promoter_id
  FROM recommendation_jobs j
  CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(j.result_json::jsonb->'recommendations') = 'array'
      THEN j.result_json::jsonb->'recommendations' ELSE '[]'::jsonb END
  ) x
), matched AS (
  SELECT DISTINCT ep.promoter_id::text AS id
  FROM event_promoters ep JOIN promoters p ON p.id=ep.promoter_id
  JOIN events e ON e.id=ep.event_id JOIN venues v ON v.id=e.venue_id
  WHERE regexp_replace(lower(p.name), '[^[:alnum:]]', '', 'g') =
        regexp_replace(lower(v.name), '[^[:alnum:]]', '', 'g')
)
SELECT count(*), count(*) FILTER (WHERE matched.id IS NOT NULL),
       count(DISTINCT r.job_id),
       count(DISTINCT r.job_id) FILTER (WHERE matched.id IS NOT NULL)
FROM r LEFT JOIN matched ON r.promoter_id=matched.id;
```

Контроль наличия исходных записей в снимке: 1959762, 2010949, 2267598, 2416601, 2458034, 2522655, 2527382 и 2564574. Гипотезы их разметки описаны в `promoter-role-review-sample.md`; проверка по источнику и независимый holdout ещё необходимы.

Две ссылки дополнительно проверены по страницам RA 3 ноября 2026 года:

- [2416601](https://ra.co/events/2416601): площадка 8MM, RA перечисляет 8MM и Romantic Fiction как промоутеров, а название прямо указывает, что они совместно представляют событие. Это контрольный пример для настройки, а не независимая оценка.
- [2522655](https://ra.co/events/2522655): площадка и RA-промоутер — 8MM; текст описывает фестиваль, организованный вокруг 8MM. Это подтверждает допустимость совмещённой роли. Один пример не является достаточной holdout-выборкой.

Ограниченная проверка Kimi `k3-256k` на локальном снимке без записи решений в БД:

- 2416601: `8MM=both`, `Romantic Fiction=organizer`.
- 2522655: `8MM=both`.
- 1959762: `DUALISMBERLIN=unknown`, `://about blank=venue`, `About Blank=unknown`. Профиль DUALISMBERLIN указан на [странице RA](https://ra.co/events/1959762) и как промоутер, и как администратор события; роль организатора остаётся случаем для дополнительной проверки. Текущая модель не дала положительного решения.
- 2267598: первый ответ не прошёл структурную проверку; отдельный повтор дал `saHHara=organizer` и двум профилям Crack Bellmer роль `venue`. На [странице RA](https://ra.co/events/2267598) saHHara приглашает на событие; отсутствие организаторской роли клуба по этому факту отдельно не доказано.

Эти примеры не образуют независимую размеченную выборку; precision и recall по ним не объявляются. Одна структурная ошибка на небольшом числе реальных запросов показывает необходимость проверки устойчивости и не является оценкой частоты ошибок.
