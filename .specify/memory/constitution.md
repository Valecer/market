<!--
Sync Impact Report:
Version: N/A → 1.0.0
Modified Principles: Initial creation
Added Sections: All (initial constitution)
Removed Sections: None
Templates Status:
  ✅ plan-template.md - Created
  ✅ spec-template.md - Created
  ✅ tasks-template.md - Created
  ✅ commands/speckit.constitution.md - Created
Follow-up TODOs: None
-->

# Project Constitution

**Project Name:** Marketbel

**Version:** 1.0.0

**Ratification Date:** 2025-11-23

**Last Amended:** 2025-11-23

---

## Preamble

This constitution establishes the foundational principles, architectural decisions, and development standards for the Marketbel project. All code, architecture, and process decisions must align with these principles. This document serves as the single source of truth for project governance and technical direction.

---

## Core Principles

### Principle 1: Single Responsibility Principle (SOLID-S)

**Declaration:**

Every module, class, or function MUST have one and only one reason to change. Each component serves a single, well-defined purpose within its domain.

**Rationale:**

Single responsibility ensures maintainability, testability, and reduces coupling. When a component has multiple reasons to change, modifications become risky and unpredictable. This principle is especially critical given our multi-service architecture where the Bun service handles API/User logic and the Python service handles Data Parsing/Normalization.

**Application:**

- API endpoints MUST NOT contain business logic; delegate to service layers
- Service modules MUST NOT handle HTTP concerns; return domain objects
- Data parsing functions MUST NOT make external API calls; process input only
- Database models MUST NOT contain business rules; represent data structure only
- React components MUST NOT contain business logic; delegate to hooks or services

### Principle 2: Open/Closed Principle (SOLID-O)

**Declaration:**

Software entities MUST be open for extension but closed for modification. New functionality should be added through extension mechanisms (interfaces, composition, plugins) rather than modifying existing stable code.

**Rationale:**

Modifying stable, tested code introduces regression risk. Extension through interfaces and composition allows new features without touching working implementations, reducing bugs and improving confidence in deployments.

**Application:**

- Use TypeScript interfaces and abstract classes for extensibility
- Leverage Python protocols and abstract base classes
- Implement strategy patterns for algorithms (e.g., matching: Levenshtein now, embeddings later)
- Use dependency injection for swappable implementations
- Design plugin-based architectures where appropriate

### Principle 3: Liskov Substitution Principle (SOLID-L)

**Declaration:**

Objects of a superclass MUST be replaceable with objects of a subclass without breaking the application. Derived types must honor the contracts established by their base types.

**Rationale:**

Contract violations lead to runtime errors and unpredictable behavior. LSP ensures that abstractions are reliable and that polymorphism works correctly, especially important for our scalability path (simple algorithms → ML embeddings).

**Application:**

- Subtypes MUST NOT strengthen preconditions or weaken postconditions
- Exception handling MUST be consistent across implementations
- Matching algorithm implementations MUST adhere to common interface contracts
- Database repositories MUST honor base repository contracts
- Test doubles (mocks/stubs) MUST behave according to production contracts

### Principle 4: Interface Segregation Principle (SOLID-I)

**Declaration:**

No client should be forced to depend on methods it does not use. Interfaces MUST be narrow, cohesive, and client-specific rather than fat and general-purpose.

**Rationale:**

Fat interfaces create unnecessary coupling and force implementations to provide stub methods. Narrow interfaces reduce dependencies, improve clarity, and make testing simpler.

**Application:**

- Split large service interfaces into smaller, focused contracts
- Create role-based interfaces (e.g., IReadable, IWritable vs IRepository)
- Avoid god objects; decompose into specific capability interfaces
- Use TypeScript's type composition features for flexibility
- Design Python protocols with minimal method requirements

### Principle 5: Dependency Inversion Principle (SOLID-D)

**Declaration:**

High-level modules MUST NOT depend on low-level modules. Both must depend on abstractions. Abstractions MUST NOT depend on details; details must depend on abstractions.

**Rationale:**

Direct dependencies on concrete implementations create tight coupling and hinder testing. Depending on abstractions enables flexibility, testability, and independent evolution of components.

**Application:**

- Services depend on repository interfaces, not concrete database implementations
- Business logic depends on service abstractions, not HTTP frameworks
- Use dependency injection containers (Bun: native DI, Python: dependency-injector)
- Mock external dependencies via interfaces in tests
- Redis queue operations MUST be abstracted behind queue interfaces

### Principle 6: Keep It Simple, Stupid (KISS)

**Declaration:**

Solutions MUST be as simple as possible but no simpler. Complexity must be justified by measurable requirements. Prefer straightforward implementations over clever optimizations until profiling proves necessity.

**Rationale:**

Unnecessary complexity is the root of technical debt, bugs, and cognitive overload. Simple code is easier to understand, maintain, and debug. Our MVP strategy explicitly prioritizes simple algorithms (Levenshtein) over complex ones (embeddings) until scale demands otherwise.

**Application:**

- Start with the simplest algorithm that meets requirements
- Use plain objects/dataclasses before introducing frameworks
- Avoid premature abstractions; extract after patterns emerge
- Write obvious code over clever code
- Default to synchronous flows unless async is required for performance
- Question every dependency: can we solve this without a library?

### Principle 7: Don't Repeat Yourself (DRY)

**Declaration:**

Every piece of knowledge MUST have a single, unambiguous, authoritative representation within the system. Duplication of logic, data, or configuration is prohibited unless explicitly justified for performance or isolation.

**Rationale:**

Duplication creates inconsistency, maintenance burden, and bugs. When logic exists in multiple places, changes require updates everywhere, increasing error likelihood. Single sources of truth ensure consistency and reduce cognitive load.

**Application:**

- Extract shared logic into utility functions or services
- Use shared TypeScript types across frontend and backend (monorepo or published types package)
- Centralize validation schemas (Pydantic models, Zod schemas)
- Configuration MUST live in environment variables or single config files
- Database schema is the single source of truth for data structure
- API contracts defined once (OpenAPI/Swagger) and generated from that definition

### Principle 8: Separation of Concerns

**Declaration:**

The Bun service handles API/User logic exclusively. The Python service handles Data Parsing/Normalization exclusively. These services MUST communicate only via Redis queues. No direct service-to-service HTTP calls are permitted.

**Rationale:**

Clear separation of concerns enables independent scaling, technology-specific optimization, and team specialization. Async communication via queues decouples services, improving resilience and enabling work distribution.

**Application:**

- Bun API receives requests, enqueues data jobs, returns responses
- Python workers consume queue messages, process data, write results to PostgreSQL
- No shared code between Bun and Python services except data contracts
- Each service has its own database connection pool and migration system
- Frontend interacts only with Bun API, never directly with Python or databases

### Principle 9: Strong Typing

**Declaration:**

All code MUST use the strongest type system available in its language. Runtime type validation MUST occur at system boundaries (API requests, queue messages, external data).

**Rationale:**

Types are documentation, contracts, and bug prevention. Strong typing catches errors at compile time rather than runtime, improves IDE support, and makes refactoring safer.

**Application:**

- TypeScript: strict mode enabled, no `any` without explicit justification
- Python: use type hints everywhere, run mypy in CI with strict mode
- Validate API requests with Zod or TypeBox schemas
- Validate queue messages with Pydantic models
- Use discriminated unions for state machines and polymorphic types
- Database models MUST have TypeScript/Python type definitions

### Principle 10: Design System Consistency

**Declaration:**

All UI components MUST follow the design system. Use `mcp 21st-dev/magic` for design element selection. No arbitrary styling or pattern deviations are permitted without design review.

**Rationale:**

Consistent UI improves user experience, reduces cognitive load, and accelerates development. Design systems ensure cohesive visual language and accessibility compliance.

**Application:**

- Query `mcp 21st-dev/magic` before implementing new UI components
- Use Tailwind CSS v4.1 CSS-first configuration approach
- Do NOT generate `tailwind.config.js`; use `@theme` blocks in CSS
- All components follow atomic design principles (atoms → molecules → organisms)
- Reuse existing components before creating new ones
- Accessibility (a11y) is non-negotiable: semantic HTML, ARIA labels, keyboard navigation

---

## Technical Standards

### Tailwind CSS v4.1 Requirements

- **MUST** use CSS-first configuration: `@import "tailwindcss";` in CSS files
- **MUST** use `@theme` blocks for theme customization
- **MUST** use `@tailwindcss/vite` plugin in Vite configuration
- **MUST NOT** generate or use `tailwind.config.js` files

### Documentation Requirements

- Collect tool documentation using `mcp context7` before implementation
- All public APIs MUST have OpenAPI/Swagger documentation
- All services MUST have README with setup, usage, and architecture overview
- Complex algorithms MUST include inline comments explaining approach and complexity

### Code Quality Standards

- All TypeScript code MUST pass `tsc --noEmit` with zero errors
- All Python code MUST pass `mypy --strict` with zero errors
- Test coverage MUST be ≥80% for business logic
- No linter errors permitted in committed code
- All commits MUST pass pre-commit hooks

---

## Governance

### Amendment Procedure

1. Proposed amendments MUST be submitted as pull requests to `.specify/memory/constitution.md`
2. Amendments require consensus from project maintainers
3. Version MUST be incremented according to semantic versioning:
   - **MAJOR:** Backward incompatible changes (principle removal/redefinition)
   - **MINOR:** New principles or materially expanded guidance
   - **PATCH:** Clarifications, wording improvements, typo fixes
4. All dependent templates (`.specify/templates/*`) MUST be updated to reflect amendments
5. A Sync Impact Report MUST be generated and included as an HTML comment at the top of this file

### Versioning Policy

- This constitution follows semantic versioning (MAJOR.MINOR.PATCH)
- `RATIFICATION_DATE` remains constant (original adoption date)
- `LAST_AMENDED` updates to the date of any modification
- Each amendment includes a Sync Impact Report documenting changes

### Compliance Review

- All pull requests MUST include a constitutional compliance statement
- Architecture Decision Records (ADRs) MUST cite relevant principles
- Quarterly reviews verify project adherence to constitutional principles
- Violations MUST be addressed immediately or formally waived with documentation

---

## Enforcement

Violations of this constitution are technical debt. They MUST be tracked, justified, and remediated. No principle may be ignored without explicit, documented rationale and a remediation plan.

---

**End of Constitution**
