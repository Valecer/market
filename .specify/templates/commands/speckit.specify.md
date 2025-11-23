---
description: Create detailed feature specifications from high-level requirements, ensuring constitutional compliance and technical feasibility.
handoffs:
  - label: Create Implementation Tasks
    agent: speckit.plan
    prompt: Break down this specification into actionable tasks...
---

## User Input

```text
[FEATURE_DESCRIPTION_OR_REQUIREMENTS]
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

You are creating a feature specification document based on the template at `.specify/templates/spec-template.md`. The specification must align with the project constitution at `.specify/memory/constitution.md` and provide comprehensive technical details for implementation.

Follow this execution flow:

1. Load and review:
   - Project constitution (`.specify/memory/constitution.md`)
   - Specification template (`.specify/templates/spec-template.md`)
   - User's feature requirements (from conversation)
   - Existing codebase structure and patterns

2. Constitutional compliance analysis:
   - Identify which principles are most relevant to this feature
   - Ensure the feature design adheres to SOLID, KISS, and DRY
   - Verify separation of concerns (Bun API vs Python processing)
   - Confirm strong typing strategy (TypeScript + Pydantic)
   - Validate design system approach (Tailwind v4.1 CSS-first)

3. Specification development:
   - **Overview:** Clear purpose and scope definition
   - **Functional Requirements:** User-facing capabilities with acceptance criteria
   - **Technical Requirements:**
     - Service responsibilities (Bun vs Python)
     - API endpoints with request/response schemas
     - Database schema and migrations
     - Queue contracts and message formats
     - Frontend components and state management
   - **Algorithm Selection:** Follow KISS (simple first, scalable later)
   - **Type Safety:** Strong TypeScript and Python type definitions
   - **Testing Strategy:** Unit, integration, and E2E test plans

4. Design system integration:
   - Query `mcp 21st-dev/magic` for UI design elements if frontend work is involved
   - Document design decisions and component choices
   - Ensure accessibility requirements are specified

5. Data modeling:
   - Define TypeScript interfaces for Bun service
   - Define Pydantic models for Python service
   - Define PostgreSQL schema with proper normalization
   - Ensure type alignment across all layers

6. Error handling and observability:
   - Define error codes and messages
   - Specify logging requirements
   - Plan monitoring and alerting strategy

7. Non-functional requirements:
   - Performance targets (response times, throughput)
   - Scalability considerations
   - Security requirements
   - Reliability and fault tolerance

8. Validation:
   - All constitutional principles addressed
   - Tech stack alignment verified
   - No undefined placeholders remain
   - All sections complete and detailed

9. Create specification file:
   - File location: `.specify/specs/[feature-name]-spec.md`
   - Use template structure exactly
   - Fill all required sections
   - Add version and date metadata

10. Output summary:
    - List key technical decisions
    - Highlight any risks or open questions
    - Suggest next steps (create task breakdown)
    - Provide suggested commit message

## Guidelines

**Technical Stack Adherence:**

- Bun (Elysia or Express) with TypeScript for API
- Python 3.11+ (Pandas, SQLAlchemy, Pydantic) for data processing
- PostgreSQL for primary storage, Redis for queues/caching
- React + Vite + Tailwind CSS v4.1 for frontend
- Docker & Docker Compose for infrastructure

**Critical Rules:**

1. Bun service ONLY handles API/User logic
2. Python service ONLY handles Data Parsing/Normalization
3. Services communicate ONLY via Redis queues (no direct HTTP)
4. Tailwind v4.1: NO `tailwind.config.js`, USE `@theme` blocks in CSS
5. Use `mcp 21st-dev/magic` for design, `mcp context7` for docs
6. Strong typing mandatory (TypeScript strict, Python mypy strict)
7. Start with simple algorithms (e.g., Levenshtein), scale to complex (embeddings) later

**Documentation Quality:**

- Be specific and actionable
- Include code examples for schemas and types
- Provide SQL for database changes
- Define clear acceptance criteria
- Document all assumptions and constraints

**Open Questions:**

If information is missing or ambiguous:
- List as open questions in the spec
- Propose reasonable defaults with justification
- Flag for stakeholder decision before implementation

**File Naming:**

- Use kebab-case: `user-authentication-spec.md`
- Be descriptive but concise
- Store in `.specify/specs/` directory

--- End Command ---

