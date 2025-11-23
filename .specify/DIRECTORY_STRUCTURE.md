# Marketbel Directory Structure

```
marketbel/
├── .gitignore                       # Git ignore patterns
├── CLAUDE.md                        # Original file
├── CONTRIBUTING.md                  # Contribution guidelines
├── README.md                        # Main project documentation
│
├── .specify/                        # SpecKit Framework
│   ├── README.md                    # SpecKit system guide
│   ├── SETUP_SUMMARY.md             # Setup summary
│   ├── DIRECTORY_STRUCTURE.md       # This file
│   │
│   ├── memory/
│   │   └── constitution.md          # Project Constitution v1.0.0
│   │
│   ├── specs/                       # Feature Specifications
│   │   └── .gitkeep                 # (empty - specs go here)
│   │
│   ├── tasks/                       # Task Breakdowns
│   │   └── .gitkeep                 # (empty - tasks go here)
│   │
│   └── templates/
│       ├── plan-template.md         # Feature planning template
│       ├── spec-template.md         # Specification template
│       ├── tasks-template.md        # Task breakdown template
│       │
│       └── commands/
│           ├── speckit.constitution.md  # Constitution command
│           ├── speckit.specify.md       # Specification command
│           └── speckit.plan.md          # Planning command
│
└── docs/
    └── adr/                         # Architecture Decision Records
        └── README.md                # ADR guide

Future Structure (to be created):
├── services/
│   ├── api/                         # Bun API service (TypeScript)
│   └── data-processing/             # Python processing service
│
├── frontend/                        # React + Vite + Tailwind v4.1
│
├── docker-compose.yml               # Docker services configuration
└── .env                             # Environment variables (from .env.example)
```

## Quick Reference

### Created Files (11 total)

1. `.specify/memory/constitution.md` - Core principles and governance
2. `.specify/templates/plan-template.md` - Feature planning
3. `.specify/templates/spec-template.md` - Technical specs
4. `.specify/templates/tasks-template.md` - Task organization
5. `.specify/templates/commands/speckit.constitution.md` - Constitution management
6. `.specify/templates/commands/speckit.specify.md` - Spec generation
7. `.specify/templates/commands/speckit.plan.md` - Task planning
8. `.specify/README.md` - SpecKit documentation
9. `README.md` - Main project docs
10. `CONTRIBUTING.md` - Contribution guide
11. `docs/adr/README.md` - ADR documentation

### Key Directories

- `.specify/specs/` - Store feature specifications here
- `.specify/tasks/` - Store task breakdowns here
- `docs/adr/` - Store architecture decisions here

### File Purposes

#### Constitution & Governance
- **constitution.md**: Single source of truth for all project principles
- **README.md**: Project overview and getting started guide
- **CONTRIBUTING.md**: How to contribute to the project

#### SpecKit Templates
- **plan-template.md**: Template for feature planning documents
- **spec-template.md**: Template for detailed technical specifications
- **tasks-template.md**: Template for task breakdowns and project management

#### SpecKit Commands
- **speckit.constitution**: Create/update constitutional principles
- **speckit.specify**: Generate feature specifications from requirements
- **speckit.plan**: Create task breakdowns from specifications

#### Documentation
- **adr/README.md**: Guide for Architecture Decision Records

## Navigation Guide

### I want to...

**...understand project principles**
→ Read `.specify/memory/constitution.md`

**...create a new feature**
→ Use `/speckit.specify [feature description]`

**...break down a feature into tasks**
→ Use `/speckit.plan [spec file reference]`

**...contribute code**
→ Read `CONTRIBUTING.md`

**...document an architectural decision**
→ Create ADR in `docs/adr/`

**...understand the SpecKit system**
→ Read `.specify/README.md`

**...set up the development environment**
→ Follow `README.md` setup instructions

## File Organization Rules

### .specify/specs/
- One spec file per feature
- Naming: `feature-name-spec.md` (kebab-case)
- Generated via `/speckit.specify`

### .specify/tasks/
- One task file per feature
- Naming: `feature-name-tasks.md` (kebab-case)
- Generated via `/speckit.plan`

### docs/adr/
- One ADR per significant decision
- Naming: `XXXX-decision-title.md` (numbered, kebab-case)
- Example: `0001-use-redis-for-queues.md`

## Version History

- **v1.0.0** (2025-11-23): Initial constitution and SpecKit framework setup

