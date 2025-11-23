---
description: Break down feature specifications into actionable, prioritized task lists with clear dependencies and estimates.
handoffs:
  - label: Start Implementation
    agent: developer
    prompt: Begin implementing these tasks starting with TASK-001...
---

## User Input

```text
[SPECIFICATION_REFERENCE_OR_TASK_BREAKDOWN_REQUEST]
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

You are creating a detailed task breakdown based on a feature specification and the task template at `.specify/templates/tasks-template.md`. Tasks must be actionable, properly sequenced, and aligned with constitutional principles.

Follow this execution flow:

1. Load and review:
   - Feature specification (from `.specify/specs/[feature-name]-spec.md`)
   - Task template (`.specify/templates/tasks-template.md`)
   - Project constitution (`.specify/memory/constitution.md`)
   - Current codebase structure

2. Task identification:
   - Break specification into discrete, implementable tasks
   - Organize by technical layer and principle alignment:
     - Setup & Infrastructure
     - Database Layer (Single Responsibility)
     - Backend API (Bun Service)
     - Data Processing (Python Service)
     - Frontend (React + Vite + Tailwind)
     - Testing (Code Quality)
     - Documentation
     - Deployment & Operations
     - Constitutional Compliance Review

3. Task definition for each identified task:
   - **Task ID:** Sequential numbering (TASK-001, TASK-002, etc.)
   - **Category:** Technical domain and principle alignment
   - **Priority:** Critical | High | Medium | Low
   - **Estimate:** Time estimate in hours
   - **Description:** Clear, concise task objective
   - **Subtasks:** Concrete action items (checkboxes)
   - **Acceptance Criteria:** Testable completion conditions
   - **Dependencies:** List of prerequisite task IDs

4. Dependency analysis:
   - Identify task dependencies
   - Create logical execution sequence
   - Flag tasks that can be parallelized
   - Ensure no circular dependencies

5. Principle-specific task validation:
   - **SOLID:** Separate tasks for each responsibility layer
   - **KISS:** Break complex work into simple, understandable units
   - **DRY:** Identify reusable components early
   - **Separation of Concerns:** Clear Bun vs Python task boundaries
   - **Strong Typing:** Explicit type definition tasks
   - **Design System:** UI tasks reference design standards
   - **Code Quality:** Testing tasks for each implementation task

6. Effort estimation:
   - Provide realistic hour estimates
   - Consider complexity, unknowns, and testing time
   - Include documentation and review time
   - Sum total estimated effort

7. Priority assignment:
   - **Critical:** Blocking other work, core functionality
   - **High:** Essential feature components
   - **Medium:** Important but not blocking
   - **Low:** Nice-to-have, polish, optional enhancements

8. Task template population:
   - Use exact template structure
   - Fill all task fields completely
   - Ensure consistency across tasks
   - Add notes for special considerations

9. Create task list file:
   - File location: `.specify/tasks/[feature-name]-tasks.md`
   - Include task summary with counts and totals
   - Add notes section for coordination guidance

10. Output summary:
    - Total task count by priority
    - Estimated timeline
    - Critical path identification
    - Suggested sprint/milestone breakdown
    - Recommended commit message

## Guidelines

**Task Granularity:**

- Each task should be completable in 1-8 hours
- If a task exceeds 8 hours, break it into smaller tasks
- Subtasks should be 15-minute to 2-hour chunks
- Tasks should have clear start and end points

**Acceptance Criteria:**

- Must be testable/verifiable
- Should be specific and measurable
- Use "given-when-then" or checklist format
- Include both functional and quality criteria

**Dependencies:**

- Explicitly list all blocking tasks
- Consider technical dependencies (DB before API)
- Consider logical dependencies (design before implementation)
- Note when tasks can run in parallel

**Testing Integration:**

- Every implementation task should have a corresponding test task
- Test tasks depend on implementation tasks
- Testing includes unit, integration, and E2E where applicable
- Target ≥80% coverage for business logic

**Constitutional Compliance:**

- Final task (TASK-025 or similar) is always compliance audit
- Each task category maps to specific principles
- Tasks should enforce principle adherence
- Flag any necessary deviations with justification

**Estimation Guidelines:**

- Include time for code review and revisions
- Include time for writing tests
- Include time for documentation
- Add buffer for unknowns and debugging
- Be realistic, not optimistic

**File Organization:**

- Tasks file stored in `.specify/tasks/`
- Use kebab-case naming: `user-auth-tasks.md`
- Link back to specification document
- Update task status as work progresses

**Coordination Notes:**

- Identify tasks suitable for junior vs senior developers
- Note tasks that benefit from pair programming
- Flag tasks requiring specific expertise
- Suggest parallelization opportunities

--- End Command ---

