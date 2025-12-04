# API Contracts

This directory contains API contracts for the Semantic ETL Pipeline (Phase 9).

## Files

### `ml-analyze-api.json`

OpenAPI 3.1.0 specification for the ml-analyze service endpoints.

**Key Endpoints:**

- `POST /analyze/file` - Trigger semantic extraction for a file
- `GET /analyze/status/{job_id}` - Poll extraction job status
- `GET /categories/review` - Get categories pending admin review
- `POST /categories/approve` - Approve or merge a category
- `GET /health` - Service health check

**Usage:**

```bash
# View in Swagger UI
docker run -p 8080:8080 -v $(pwd):/specs swaggerapi/swagger-ui

# Generate TypeScript types
npx openapi-typescript ml-analyze-api.json --output ../types/ml-analyze.d.ts

# Generate Python client
openapi-generator-cli generate -i ml-analyze-api.json -g python -o ../clients/python-ml-analyze
```

## Validation

```bash
# Validate OpenAPI spec
npx @redocly/cli lint ml-analyze-api.json

# Check for breaking changes (compare with previous version)
npx @redocly/cli diff ml-analyze-api-v1.json ml-analyze-api.json
```

## Versioning

API contracts follow semantic versioning:
- **MAJOR:** Breaking changes (removed endpoints, changed required fields)
- **MINOR:** New endpoints or optional fields
- **PATCH:** Documentation updates, example changes

Current version: **2.0.0** (Semantic ETL refactoring)
