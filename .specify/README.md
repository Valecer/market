# SpecKit System

This directory contains the **SpecKit** framework for managing project governance, specifications, and development workflows.

## Directory Structure

```
.specify/
├── memory/
│   └── constitution.md          # Project constitution (principles & governance)
├── specs/                       # Feature specifications
│   └── [feature-name]-spec.md
├── tasks/                       # Task breakdowns
│   └── [feature-name]-tasks.md
└── templates/
    ├── plan-template.md         # Feature planning template
    ├── spec-template.md         # Specification template
    ├── tasks-template.md        # Task list template
    └── commands/
        ├── speckit.constitution.md  # Constitution command
        ├── speckit.specify.md       # Specification command
        └── speckit.plan.md          # Task planning command
```

## Core Components

### Constitution (`memory/constitution.md`)

The project constitution establishes:

- **Core Principles:** SOLID, KISS, DRY, and project-specific principles
- **Technical Standards:** Tech stack requirements, coding standards
- **Governance:** Amendment procedures, versioning, compliance

**Key Principles:**

1. Single Responsibility Principle (SOLID-S)
2. Open/Closed Principle (SOLID-O)
3. Liskov Substitution Principle (SOLID-L)
4. Interface Segregation Principle (SOLID-I)
5. Dependency Inversion Principle (SOLID-D)
6. Keep It Simple, Stupid (KISS)
7. Don't Repeat Yourself (DRY)
8. Separation of Concerns (Bun API vs Python Processing)
9. Strong Typing (TypeScript strict, Python mypy strict)
10. Design System Consistency

All code and architecture decisions must align with these principles.

### Specifications (`specs/`)

Detailed feature specifications created using `speckit.specify`:

- Functional and technical requirements
- Constitutional compliance statements
- API contracts and data models
- Testing strategies
- Deployment plans

### Tasks (`tasks/`)

Actionable task breakdowns created using `speckit.plan`:

- Organized by technical layer
- Dependencies and priorities
- Time estimates
- Acceptance criteria

### Templates (`templates/`)

Reusable templates for consistent documentation:

- `plan-template.md`: Feature planning structure
- `spec-template.md`: Specification format
- `tasks-template.md`: Task organization

### Commands (`templates/commands/`)

Agent command definitions for the SpecKit workflow:

1. **`speckit.constitution`**: Create/update constitution
2. **`speckit.specify`**: Generate feature specifications
3. **`speckit.plan`**: Create task breakdowns

## Workflow

### 1. Establish Constitution

```bash
# Create or update project principles
/speckit.constitution Create project principles adhering to SOLID, KISS, and DRY
```

### 2. Specify Features

```bash
# Create detailed specification
/speckit.specify I want to build a user authentication system with JWT tokens
```

### 3. Plan Implementation

```bash
# Break down into tasks
/speckit.plan Create task breakdown for user-authentication-spec.md
```

### 4. Implement

Follow the generated task list in `.specify/tasks/`, ensuring constitutional compliance throughout.

## Constitutional Compliance

Every feature must include:

- **Compliance Statement:** How it adheres to principles
- **Deviation Justification:** Documented reasons for any exceptions
- **Testing Requirements:** ≥80% coverage for business logic
- **Documentation:** API docs, README updates, ADRs for significant decisions

## Version Management

The constitution uses semantic versioning:

- **MAJOR:** Breaking changes to principles
- **MINOR:** New principles or material expansions
- **PATCH:** Clarifications and typo fixes

Current Version: **1.0.0**

## Tech Stack Enforcement

The constitution enforces the following tech stack:

- **Backend API:** Bun (Elysia/Express) + TypeScript
- **Data Processing:** Python 3.11+ (Pandas, SQLAlchemy, Pydantic)
- **Database:** PostgreSQL (primary), Redis (queues/caching)
- **Frontend:** React + Vite + Tailwind CSS v4.1
- **Infrastructure:** Docker & Docker Compose

### Critical Rules

1. Bun service handles ONLY API/User logic
2. Python service handles ONLY Data Parsing/Normalization
3. Services communicate ONLY via Redis queues
4. Tailwind v4.1: NO `tailwind.config.js`, USE `@theme` in CSS
5. Strong typing mandatory (strict mode)
6. Simple algorithms first (KISS), scale later

## Design System

Use `mcp 21st-dev/magic` for UI design elements before implementation.

Collect tool documentation using `mcp context7` before starting work.

## Maintenance

### Updating the Constitution

1. Modify `.specify/memory/constitution.md`
2. Update version according to change type (MAJOR/MINOR/PATCH)
3. Add Sync Impact Report as HTML comment
4. Update dependent templates if needed
5. Commit with message: `docs: amend constitution to vX.Y.Z (description)`

### Adding New Principles

1. Use `/speckit.constitution` command
2. Ensure no conflicts with existing principles
3. Update templates to reflect new principle
4. Increment minor version

### Template Updates

When updating templates:

1. Maintain consistent structure
2. Ensure constitutional alignment
3. Update all three templates if sections change
4. Test with a sample feature

## Contributing

All contributions must:

1. Adhere to constitutional principles
2. Pass linting (TypeScript, Python, Markdown)
3. Include tests (≥80% coverage)
4. Update relevant documentation
5. Include constitutional compliance statement in PR

## Questions?

Refer to the constitution (`.specify/memory/constitution.md`) as the single source of truth for all governance and technical decisions.

---

**SpecKit** ensures consistent, principled, and well-documented software development.

