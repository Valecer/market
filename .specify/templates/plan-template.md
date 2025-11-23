# Feature Plan: [FEATURE_NAME]

**Date:** [YYYY-MM-DD]

**Status:** [Draft | In Progress | Completed]

**Owner:** [TEAM_MEMBER_NAME]

---

## Overview

Brief description of what this feature accomplishes and why it's needed.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **[Principle Name]:** [How this feature upholds or relates to the principle]
- **[Principle Name]:** [How this feature upholds or relates to the principle]

**Violations/Exceptions:** [None | List any justified deviations with rationale]

---

## Goals

- [ ] Goal 1
- [ ] Goal 2
- [ ] Goal 3

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- Non-goal 1
- Non-goal 2

---

## Success Metrics

How will we measure success?

- **Metric 1:** [Description and target value]
- **Metric 2:** [Description and target value]

---

## User Stories

### Story 1: [Title]

**As a** [user type]
**I want** [goal]
**So that** [benefit]

**Acceptance Criteria:**

- [ ] Criterion 1
- [ ] Criterion 2

### Story 2: [Title]

[Repeat pattern above]

---

## Technical Approach

### Architecture

High-level architecture decisions and service interactions.

**Bun Service (API/User Logic):**

- Responsibilities:
- Endpoints:
- Data flow:

**Python Service (Data Processing):**

- Responsibilities:
- Processing logic:
- Data flow:

**Redis Queue Communication:**

- Queue names:
- Message formats (reference Pydantic models):
- Error handling:

**PostgreSQL Schema:**

- Tables affected:
- Migration plan:

**Frontend (React + Vite + Tailwind v4.1):**

- Components:
- State management:
- API integration:

### Design System

- [ ] Consulted `mcp 21st-dev/magic` for UI design elements
- [ ] Collected documentation via `mcp context7`
- [ ] Tailwind v4.1 CSS-first approach confirmed (no `tailwind.config.js`)

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **Initial Implementation:** [e.g., Levenshtein distance for matching]
- **Scalability Path:** [e.g., future embeddings-based matching when scale requires]

### Data Flow

```
[User] → [Bun API] → [Redis Queue] → [Python Worker] → [PostgreSQL]
           ↓                                               ↓
    [API Response]                                  [Result Storage]
```

---

## Type Safety

### TypeScript Types

```typescript
// Define API request/response types
interface FeatureRequest {
  // ...
}

interface FeatureResponse {
  // ...
}
```

### Python Types

```python
from pydantic import BaseModel

class QueueMessage(BaseModel):
    # Define queue message structure
    pass

class ProcessedResult(BaseModel):
    # Define result structure
    pass
```

---

## Testing Strategy

- **Unit Tests:** [What will be unit tested]
- **Integration Tests:** [What service interactions will be tested]
- **E2E Tests:** [What user flows will be tested]
- **Coverage Target:** ≥80% for business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| [Risk description] | High/Med/Low | High/Med/Low | [Mitigation strategy] |

---

## Dependencies

- **Bun Packages:** [List npm packages needed]
- **Python Packages:** [List pip packages needed]
- **External Services:** [List any external APIs or services]
- **Infrastructure:** [Docker changes, env vars, etc.]

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| Phase 1 | [Task list] | [X days] | [YYYY-MM-DD] |
| Phase 2 | [Task list] | [X days] | [YYYY-MM-DD] |

---

## Open Questions

- [ ] Question 1
- [ ] Question 2

---

## References

- [Link to related ADR]
- [Link to design docs]
- [Link to external documentation]

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
