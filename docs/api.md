# API Guide

The FastAPI application exposes health, entity lookup, graph, recommendation, and feedback endpoints. When the local stack is running, interactive OpenAPI documentation is available at:

```text
http://localhost:8080/docs
```

Examples below use the NGINX local gateway. IDs and response values are illustrative; use IDs present in your imported database.

## Health

```bash
curl -s http://localhost:8080/health
```

Abbreviated response:

```json
{
  "status": "ok",
  "database": "ok",
  "schema": {
    "status": "ok",
    "missingRequiredTables": []
  }
}
```

Schema-only checks are also available:

```bash
curl -s http://localhost:8080/api/health/schema
```

## Entity lookup and search

```bash
curl -s "http://localhost:8080/api/search?q=artist"
curl -s http://localhost:8080/api/artist/2178
curl -s http://localhost:8080/api/event/100
curl -s http://localhost:8080/api/promoter/50
curl -s http://localhost:8080/api/venue/25
curl -s http://localhost:8080/api/genres
```

## Artist recommendations

Inspect extracted tags:

```bash
curl -s "http://localhost:8080/api/artists/2178/tags?minConfidence=0.7"
```

## Promoter recommendations

```bash
curl -s "http://localhost:8080/api/recommendations/artists/2178/promoters?limit=5"
```

The response includes recommendation scores, reasons, evidence paths, segmented recommendation lists, and a graph payload used by the frontend.

Useful query parameters:

- `limit` - number of recommendations
- `debug` - include additional scoring details

## Graph endpoints

```bash
curl -s http://localhost:8080/api/graph
curl -s "http://localhost:8080/api/graph/ego?type=artist&id=2178"
```

Graph responses contain `nodes` and `links`, with optional evidence and path metadata used to explain recommendations.

## Recommendation feedback

Create or update feedback:

```bash
curl -s -X POST http://localhost:8080/api/recommendation-feedback \
  -H "Content-Type: application/json" \
  -d '{
    "sourceEntityType": "artist",
    "sourceEntityId": 2178,
    "candidateEntityType": "artist",
    "candidateEntityId": 123,
    "feedback": "positive",
    "reason": "Relevant style and promoter overlap"
  }'
```

List feedback:

```bash
curl -s "http://localhost:8080/api/recommendation-feedback?sourceEntityType=artist&sourceEntityId=2178"
```

Supported feedback values are `positive`, `negative`, and `hidden`.

## Error behavior

- Missing entities return HTTP `404` where the endpoint validates entity existence.
- Invalid query parameter ranges return FastAPI validation responses.
- Database or schema readiness is reported through the health endpoints.

Use the generated OpenAPI documentation as the source of truth for complete schemas and current query parameters.
