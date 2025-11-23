# Feature Specification: [FEATURE_NAME]

**Version:** 1.0.0

**Last Updated:** [YYYY-MM-DD]

**Status:** [Draft | Review | Approved | Implemented]

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** [How this spec respects SRP]
- **Separation of Concerns:** [Bun vs Python service responsibilities]
- **Strong Typing:** [TypeScript/Pydantic schema references]
- **KISS:** [Simple algorithm choices and justification]
- **DRY:** [Reused components and avoided duplication]

**Compliance Statement:**

This specification adheres to all constitutional principles. Any deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

[1-2 sentence description of what this feature does]

### Scope

**In Scope:**

- Item 1
- Item 2

**Out of Scope:**

- Item 1
- Item 2

---

## Functional Requirements

### FR-1: [Requirement Name]

**Priority:** [Critical | High | Medium | Low]

**Description:** [Detailed description of the functional requirement]

**Acceptance Criteria:**

- [ ] AC-1: [Testable criterion]
- [ ] AC-2: [Testable criterion]

**Dependencies:** [List any dependent features or services]

### FR-2: [Requirement Name]

[Repeat pattern above for each functional requirement]

---

## Technical Requirements

### TR-1: Service Architecture

**Bun Service Responsibilities:**

- API endpoint(s): `[METHOD] /path/to/endpoint`
- Request validation using Zod/TypeBox
- Enqueue jobs to Redis
- Return response to client

**Python Service Responsibilities:**

- Consume Redis queue: `queue-name`
- Process/normalize data
- Write results to PostgreSQL
- Handle errors and retries

**Communication Contract:**

```typescript
// Queue message schema (TypeScript)
interface QueueMessageContract {
  jobId: string;
  payload: {
    // ...
  };
}
```

```python
# Queue message schema (Python)
class QueueMessageContract(BaseModel):
    job_id: str
    payload: dict
```

### TR-2: Database Schema

**Tables:**

```sql
CREATE TABLE [table_name] (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- columns
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Indexes:**

- Index 1: `CREATE INDEX idx_[name] ON [table]([column]);`

**Migrations:**

- Migration file: `[timestamp]_[description].sql`
- Rollback strategy: [Description]

### TR-3: API Specification

**Endpoint:** `[METHOD] /api/v1/resource`

**Request:**

```typescript
interface RequestBody {
  field1: string;
  field2: number;
}
```

**Response:**

```typescript
interface ResponseBody {
  success: boolean;
  data: {
    // ...
  };
}
```

**Status Codes:**

- `200 OK`: Success
- `400 Bad Request`: Validation error
- `500 Internal Server Error`: Server error

**Authentication:** [Required/Optional] - [Method]

### TR-4: Frontend Components

**Components:**

- `ComponentName.tsx`: [Description and responsibility]

**State Management:**

- [Describe state approach: Context, Zustand, React Query, etc.]

**Styling:**

- Tailwind CSS v4.1 with CSS-first configuration
- Use `@theme` blocks for customization
- Design system reference: [Link to mcp 21st-dev/magic results]

### TR-5: Type Safety

**TypeScript Configuration:**

- Strict mode enabled
- No `any` types without explicit `@ts-expect-error` justification

**Python Configuration:**

- Type hints on all functions
- Mypy strict mode compliance

---

## Non-Functional Requirements

### NFR-1: Performance

- API response time: < [X]ms at p95
- Queue processing throughput: > [X] messages/second
- Database query performance: < [X]ms for key queries

### NFR-2: Scalability

- Support [X] concurrent users
- Horizontal scaling via additional Python workers
- Queue-based architecture enables work distribution

### NFR-3: Security

- Input validation at all system boundaries
- SQL injection prevention via parameterized queries (SQLAlchemy)
- Environment-based secrets (never hardcoded)
- CORS configuration for production

### NFR-4: Observability

- Structured logging (JSON format)
- Error tracking and alerting
- Request tracing across services
- Metrics for queue depth and processing time

### NFR-5: Reliability

- Queue message retry policy: [X retries with exponential backoff]
- Database connection pooling and retry logic
- Graceful degradation on service failures

---

## Algorithm Specification

Following the KISS principle, we implement the simplest solution first:

**Initial Algorithm:** [e.g., Levenshtein distance]

- **Complexity:** O(n×m) time, O(n×m) space
- **Justification:** Simple, deterministic, no training data required
- **Limitations:** [Known limitations]

**Future Evolution:** [e.g., Embedding-based matching]

- **Trigger:** When dataset size > [X] or accuracy < [Y]%
- **Migration Path:** [How to transition]

---

## Data Models

### Bun Service (TypeScript)

```typescript
// src/types/feature.types.ts
export interface FeatureModel {
  id: string;
  name: string;
  createdAt: Date;
}
```

### Python Service (Pydantic)

```python
# src/models/feature_model.py
from pydantic import BaseModel
from datetime import datetime

class FeatureModel(BaseModel):
    id: str
    name: str
    created_at: datetime
```

### Database (PostgreSQL)

```sql
-- migrations/XXX_feature_table.sql
CREATE TABLE features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## Error Handling

### Bun Service

```typescript
// Standard error response
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
```

**Error Codes:**

- `VALIDATION_ERROR`: Invalid request data
- `QUEUE_ERROR`: Failed to enqueue job
- `INTERNAL_ERROR`: Unexpected server error

### Python Service

```python
# Queue processing error handling
try:
    process_message(message)
except ValidationError as e:
    # Log and move to dead letter queue
except ProcessingError as e:
    # Retry with backoff
except Exception as e:
    # Log and alert
```

---

## Testing Requirements

### Unit Tests

- **Bun:** Test service logic, validation schemas
- **Python:** Test data processing functions, Pydantic models
- **Frontend:** Test component rendering, user interactions

### Integration Tests

- **API:** Test endpoint request/response cycles
- **Queue:** Test message enqueue/dequeue and processing
- **Database:** Test CRUD operations and migrations

### E2E Tests

- Full user flow from frontend action to data persistence
- Error scenarios (validation failures, service unavailability)

**Coverage Target:** ≥80% for all business logic

---

## Deployment

### Environment Variables

```bash
# Bun Service
BUN_PORT=3000
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Python Service
REDIS_URL=redis://...
DATABASE_URL=postgresql://...
QUEUE_NAME=feature-queue
```

### Docker Configuration

- Services defined in `docker-compose.yml`
- Health checks for all services
- Volume mounts for development
- Network isolation for security

### Migration Strategy

1. Run database migrations
2. Deploy Python service (backward compatible workers)
3. Deploy Bun service (new API version)
4. Frontend deployment (feature flag rollout)

---

## Documentation

- [ ] API documentation (OpenAPI/Swagger)
- [ ] README update with feature overview
- [ ] Architecture Decision Record (ADR) if applicable
- [ ] Inline code documentation for complex logic

---

## Rollback Plan

**Trigger Conditions:**

- Error rate > [X]%
- Performance degradation > [X]%
- Data corruption detected

**Rollback Steps:**

1. Revert frontend deployment
2. Revert Bun service
3. Pause Python workers
4. Rollback database migration if necessary
5. Investigate and fix issues before redeployment

---

## Exceptions & Deviations

[Document any intentional deviations from constitutional principles with justification]

**None** or:

**Deviation 1:** [Description]

- **Principle Affected:** [Principle name]
- **Justification:** [Why this deviation is necessary]
- **Remediation Plan:** [How/when this will be fixed]

---

## Appendix

### References

- [Link to plan document]
- [Link to design mockups]
- [Link to external API docs]

### Glossary

- **Term 1:** Definition
- **Term 2:** Definition

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
