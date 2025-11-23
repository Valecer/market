# Contributing to Marketbel

Thank you for your interest in contributing to Marketbel! This document provides guidelines for contributing to this principle-driven project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Constitutional Compliance](#constitutional-compliance)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Prioritize project principles and code quality
- Help maintain the constitutional framework

## Getting Started

### Prerequisites

1. Read the [Project Constitution](.specify/memory/constitution.md)
2. Understand the [Tech Stack](README.md#tech-stack)
3. Set up your [Development Environment](README.md#development-setup)
4. Familiarize yourself with the [SpecKit System](.specify/README.md)

### First Contribution

Good first contributions:

- Fix typos or improve documentation
- Add missing tests to increase coverage
- Implement well-defined tasks from `.specify/tasks/`
- Resolve open issues tagged with `good first issue`

## Constitutional Compliance

**Every contribution MUST align with our constitutional principles.**

### Required Compliance Statement

Include in your PR description:

```markdown
## Constitutional Compliance

This PR adheres to the following principles:

- **[Principle Name]**: [How this PR upholds the principle]
- **[Principle Name]**: [How this PR upholds the principle]

**Deviations**: [None | Justified deviation with remediation plan]
```

### Core Principles Checklist

- [ ] **Single Responsibility**: Each component has one reason to change
- [ ] **Open/Closed**: Extended via interfaces, not modifications
- [ ] **Liskov Substitution**: Subtypes honor base contracts
- [ ] **Interface Segregation**: Narrow, client-specific interfaces
- [ ] **Dependency Inversion**: Depend on abstractions, not concretions
- [ ] **KISS**: Simplest solution that meets requirements
- [ ] **DRY**: No duplication of logic or data
- [ ] **Separation of Concerns**: Bun API vs Python processing respected
- [ ] **Strong Typing**: TypeScript strict, Python mypy strict
- [ ] **Design System**: UI follows established patterns

## Development Workflow

### 1. Create or Claim an Issue

- Check existing issues first
- Create an issue describing the problem/feature
- Wait for approval before starting significant work

### 2. Create a Feature Branch

```bash
git checkout -b feature/descriptive-name
# or
git checkout -b fix/issue-description
```

Branch naming conventions:

- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Adding or updating tests

### 3. Follow SpecKit Process

For new features:

```bash
# Generate specification
/speckit.specify Describe your feature here

# Create task breakdown
/speckit.plan Reference the spec file
```

### 4. Implement Changes

- Write code following [Code Standards](#code-standards)
- Add tests for all new functionality
- Update documentation as needed
- Ensure linting passes

### 5. Commit Your Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:

```bash
git commit -m "feat(api): add user authentication endpoint"
git commit -m "fix(worker): resolve Redis connection timeout"
git commit -m "docs(constitution): clarify KISS principle application"
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-branch-name
```

Then create a PR on GitHub/GitLab.

## Pull Request Process

### PR Title

Use the same format as commit messages:

```
feat(api): add JWT-based authentication
```

### PR Description Template

```markdown
## Description

[Clear description of what this PR does]

## Related Issue

Closes #[issue-number]

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Constitutional Compliance

- **[Principle]**: [How this PR adheres]
- **[Principle]**: [How this PR adheres]

**Deviations**: None

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] E2E tests added/updated (if applicable)
- [ ] All tests pass locally
- [ ] Coverage remains ≥80%

## Checklist

- [ ] Code follows project style guidelines
- [ ] TypeScript: `tsc --noEmit` passes with zero errors
- [ ] Python: `mypy --strict` passes with zero errors
- [ ] Linting passes (no warnings)
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes (or documented if necessary)

## Screenshots (if applicable)

[Add screenshots for UI changes]
```

### Review Process

1. **Automated Checks**: CI must pass (linting, tests, type checking)
2. **Code Review**: At least one maintainer approval required
3. **Constitutional Review**: Compliance verified
4. **Testing**: All tests pass, coverage maintained
5. **Documentation**: Updates complete and accurate

### Addressing Feedback

- Respond to all review comments
- Make requested changes promptly
- Re-request review after updates
- Be open to suggestions and alternative approaches

## Code Standards

### TypeScript (Bun Service)

```typescript
// ✅ Good: Strong typing, clear responsibility
interface UserRequest {
  email: string;
  password: string;
}

export async function validateUser(request: UserRequest): Promise<User> {
  // Validation logic only
  return user;
}

// ❌ Bad: `any` type, mixed concerns
async function validateUser(req: any) {
  // Don't mix HTTP and business logic
  return res.json({ user });
}
```

**Requirements**:

- TypeScript strict mode enabled
- No `any` without explicit justification
- Export types for all public APIs
- Use interfaces for object shapes
- Prefer `const` over `let`, avoid `var`

### Python (Data Processing)

```python
# ✅ Good: Type hints, Pydantic validation
from pydantic import BaseModel

class DataRecord(BaseModel):
    id: str
    value: float
    
def process_record(record: DataRecord) -> ProcessedData:
    """Process a single data record."""
    # Processing logic only
    return processed

# ❌ Bad: No types, no validation
def process_record(record):
    return record['value'] * 2
```

**Requirements**:

- Type hints on all functions
- Pydantic models for data validation
- Docstrings for all public functions
- Pass `mypy --strict` with zero errors
- Use `black` for formatting, `ruff` for linting

### Frontend (React + Tailwind)

```tsx
// ✅ Good: Typed props, single responsibility
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

export function Button({ label, onClick, variant = 'primary' }: ButtonProps) {
  return (
    <button onClick={onClick} className="btn btn-{variant}">
      {label}
    </button>
  );
}

// ❌ Bad: No types, mixed concerns, inline styles
export function Button(props) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    // Don't fetch data in presentational components
    fetchData().then(setData);
  }, []);
  
  return <button style={{ color: 'red' }}>{props.label}</button>;
}
```

**Requirements**:

- Tailwind CSS v4.1 with `@theme` blocks
- No `tailwind.config.js`
- Typed props with TypeScript
- Semantic HTML
- ARIA labels for accessibility

## Testing Requirements

### Coverage

- **Minimum**: 80% coverage for business logic
- **Target**: 90%+ coverage for critical paths

### Unit Tests

Test individual functions/methods in isolation:

```typescript
// Bun/TypeScript
import { describe, it, expect } from 'bun:test';

describe('validateEmail', () => {
  it('should return true for valid email', () => {
    expect(validateEmail('user@example.com')).toBe(true);
  });
  
  it('should return false for invalid email', () => {
    expect(validateEmail('invalid')).toBe(false);
  });
});
```

```python
# Python
import pytest

def test_process_record_success():
    record = DataRecord(id="1", value=10.0)
    result = process_record(record)
    assert result.value == 20.0

def test_process_record_invalid():
    with pytest.raises(ValidationError):
        process_record({"invalid": "data"})
```

### Integration Tests

Test service interactions:

```typescript
it('should enqueue job and receive result', async () => {
  const response = await api.post('/process', { data });
  expect(response.status).toBe(202);
  
  // Wait for processing
  const result = await pollForResult(response.body.jobId);
  expect(result.status).toBe('completed');
});
```

### E2E Tests

Test complete user flows:

```typescript
test('user can submit data and see results', async ({ page }) => {
  await page.goto('/');
  await page.fill('input[name="data"]', 'test data');
  await page.click('button[type="submit"]');
  await expect(page.locator('.result')).toContainText('Processed');
});
```

## Documentation

### Code Documentation

- **TypeScript**: JSDoc for public APIs
- **Python**: Docstrings following Google or NumPy style
- **Complex Logic**: Inline comments explaining "why", not "what"

### Feature Documentation

When adding features:

1. Create specification in `.specify/specs/`
2. Update main `README.md`
3. Add/update API documentation
4. Create ADR for significant decisions

### API Documentation

- Generate from code (OpenAPI/Swagger)
- Include request/response examples
- Document all error codes
- Specify authentication requirements

## Questions?

- **Principles**: See [Constitution](.specify/memory/constitution.md)
- **Process**: See [SpecKit README](.specify/README.md)
- **Technical**: Create an issue with the `question` label
- **Chat**: [Link to Slack/Discord if applicable]

## Thank You!

Your contributions help make Marketbel better. We appreciate your commitment to quality and principles! 🎯

