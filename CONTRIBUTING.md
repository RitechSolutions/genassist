# Contributing to GenAssist

Thank you for your interest in contributing to GenAssist! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Branch Naming Conventions](#branch-naming-conventions)
- [Feature Implementation Process](#feature-implementation-process)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Requirements](#documentation-requirements)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences

## Getting Started

### Prerequisites

- Git
- Docker and Docker Compose
- Node.js and npm (for frontend development)
- Python 3.10+ (for backend development)

### Initial Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/genassist.git
   cd genassist
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/RitechSolutions/genassist.git
   ```
4. Set up your development environment:
   - Frontend: Follow [frontend/README.md](frontend/README.md)
   - Backend: Follow [backend/README.md](backend/README.md)

## Development Workflow

GenAssist uses the **GitFlow** branching strategy. Understanding this workflow is essential for contributing.

### Branch Types

- **`main`** - Production-ready code. Always stable and deployable.
- **`development`** - Integration branch for features. All feature branches merge here first.
- **`feature/*`** - New features and enhancements. Created from `development`.
- **`release/*`** - Release preparation branches. Created from `development` when preparing a release.
- **`hotfix/*`** - Critical production fixes. Created from `main`.

### Workflow Diagram

```
main ────────────────────────────────────── (production)
  │
  └── hotfix/* ──────────────────────────── (critical fixes)
  │
development ──────────────────────────────────── (integration)
  │
  ├── feature/* ─────────────────────────── (new features)
  │
  └── release/* ─────────────────────────── (release prep)
```

## Branch Naming Conventions

Use descriptive, lowercase branch names with hyphens:

- **Features**: `feature/description-of-feature`
  - Example: `feature/user-authentication`, `feature/rag-integration`
- **Bug Fixes**: `bugfix/description-of-bug`
  - Example: `bugfix/fix-login-error`, `bugfix/resolve-memory-leak`
- **Hotfixes**: `hotfix/description-of-fix`
  - Example: `hotfix/security-patch`, `hotfix/critical-api-fix`
- **Releases**: `release/version-number`
  - Example: `release/v1.2.0`, `release/v2.0.0`

## Feature Implementation Process

### Step 1: Create a Feature Branch

```bash
# Ensure you're on development and up to date
git checkout development
git pull upstream development

# Create and switch to your feature branch
git checkout -b feature/your-feature-name
```

### Step 2: development Your Feature

- Write clean, maintainable code following our [Code Standards](#code-standards)
- Write tests as you development (see [Testing Requirements](#testing-requirements))
- Commit frequently with clear messages (see [Commit Message Guidelines](#commit-message-guidelines))
- Keep your branch up to date with `development`:
  ```bash
  git fetch upstream
  git rebase upstream/development
  ```

### Step 3: Test Your Changes

Before submitting a PR, ensure:

- ✅ All existing tests pass
- ✅ New tests are written for your changes
- ✅ Code passes linting checks
- ✅ Manual testing is completed
- ✅ Documentation is updated (if needed)

### Step 4: Submit a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Create a Pull Request on GitHub:
   - Target branch: `development` (for features) or `main` (for hotfixes)
   - Use the appropriate PR template (feature, bugfix, core, or improvement)
   - Fill out all required sections
   - Link related issues

3. Wait for code review (see [Code Review Guidelines](#code-review-guidelines))

### Step 5: Address Review Feedback

- Respond to all comments
- Make requested changes
- Push updates to your branch (the PR will update automatically)
- Mark conversations as resolved when addressed

### Step 6: Merge

Once approved:
- A maintainer will merge your PR
- Your feature will be integrated into `development`
- For releases, `development` is merged into `main` via a release branch

## Code Standards

### Frontend (React/TypeScript)

- **TypeScript**: Use TypeScript for all new code. Avoid `any` types.
- **Components**: Use functional components with hooks
- **Styling**: Use Tailwind CSS classes. Follow existing component patterns.
- **File Structure**: 
  - Components: `src/components/`
  - Services: `src/services/`
  - Types/Interfaces: `src/interfaces/`
- **Naming**:
  - Components: PascalCase (e.g., `UserProfile.tsx`)
  - Functions/Variables: camelCase (e.g., `getUserData`)
  - Constants: UPPER_SNAKE_CASE (e.g., `API_BASE_URL`)
- **Linting**: Code must pass ESLint checks
  ```bash
  cd frontend
  npm run lint
  ```

### Backend (Python/FastAPI)

- **Python Version**: Python 3.10+
- **Style Guide**: Follow PEP 8
- **Type Hints**: Use type hints for all function signatures
- **File Structure**:
  - API endpoints: `app/api/v1/`
  - Models: `app/db/models/`
  - Services: `app/services/`
  - Schemas: `app/schemas/`
- **Naming**:
  - Classes: PascalCase (e.g., `UserService`)
  - Functions/Variables: snake_case (e.g., `get_user_data`)
  - Constants: UPPER_SNAKE_CASE
- **Linting**: Code must pass flake8/black formatting
  ```bash
  cd backend
  # Run linter (if configured)
  ```

### Database Migrations

- Use Alembic for database migrations
- Create migrations for all schema changes:
  ```bash
  cd backend
  alembic revision --autogenerate -m "Description of changes"
  alembic upgrade head
  ```
- Test migrations both up and down

## Testing Requirements

### Frontend Testing

- Write unit tests for components and utilities
- Write integration tests for critical user flows
- Use Playwright for E2E tests (see `ui_tests/`)
- Run tests before submitting PR:
  ```bash
  cd frontend
  npm test
  ```

### Backend Testing

- Write unit tests for services and utilities
- Write integration tests for API endpoints
- Maintain or improve test coverage
- Run tests before submitting PR:
  ```bash
  cd backend
  python -m pytest tests/ -v
  ```

### Test Coverage

- Aim for >80% code coverage for new code
- Critical paths should have 100% coverage
- Include both positive and negative test cases

## Documentation Requirements

### Code Documentation

- **Functions/Methods**: Add docstrings explaining purpose, parameters, and return values
- **Complex Logic**: Add inline comments explaining non-obvious decisions
- **API Endpoints**: Document request/response schemas

### Frontend Documentation

- Document new components in component files
- Update README if adding new dependencies or setup steps

### Backend Documentation

- Use FastAPI's automatic OpenAPI documentation
- Add docstrings to all public functions and classes
- Update API documentation if endpoints change

### General Documentation

- Update `README.md` if project setup changes
- Update `CONTRIBUTING.md` if workflow changes
- Add architecture diagrams if system design changes (see `docs/`)

## Commit Message Guidelines

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `hotfix`: Critical production fix
- `bugfix`: Bug fix (alias for fix)
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build config, etc.)
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `build`: Build system changes
- `security`: Security-related changes
- `release`: Release preparation

### Examples

```
feat(auth): add OAuth2 authentication

Implement OAuth2 flow with Google and GitHub providers.
Add new authentication endpoints and update user model.

Closes #123
```

```
fix(api): resolve memory leak in conversation service

Fix issue where conversation history was not properly cleaned up,
causing memory leaks during long-running sessions.

Fixes #456
```

```
docs(readme): update installation instructions

Add Docker Compose setup instructions and environment variable
configuration details.
```

## Pull Request Process

### PR Title Format

**Important**: PR titles are validated by an automated workflow. Your PR title must follow this format:

```
<type>: <description>
```

or

```
<type> - <description>
```

**Allowed types**: `feat`, `fix`, `hotfix`, `bugfix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `security`, `release`

**Examples**:
- `feat: add user authentication`
- `fix: resolve memory leak in conversation service`
- `docs - update installation instructions`
- `chore: bump dependencies`

### PR Requirements

1. **Target Branch**:
   - Features → `development`
   - Hotfixes → `main`
   - Core changes → `development` (may require special review)

2. **PR Template**: Use the appropriate template:
   - `feature.md` - For new features
   - `bugfix.md` - For bug fixes
   - `core.md` - For core implementation changes
   - `improvement.md` - For improvements/suggestions

3. **Description**: 
   - Clear description of changes
   - Link related issues
   - Include screenshots for UI changes
   - Document breaking changes (if any)

4. **Checklist**: Complete all relevant checklist items

5. **Tests**: All tests must pass

6. **Review**: Wait for required approvals (see [Branch Protection Rules](.github/BRANCH_PROTECTION.md))

### PR Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: At least 1-2 reviewers (depending on branch)
3. **Feedback**: Address all review comments
4. **Approval**: Once approved, maintainer merges the PR

### Merging

- **Squash and Merge**: Preferred for feature branches (cleaner history)
- **Merge Commit**: Used for release branches
- **Rebase and Merge**: Used sparingly, only when appropriate

## Code Review Guidelines

### For Reviewers

- Be constructive and respectful
- Focus on code quality, not personal preferences
- Explain the reasoning behind suggestions
- Approve when satisfied, or request changes with clear feedback
- Review within 2-3 business days when possible

### For Contributors

- Respond to all review comments
- Don't take feedback personally
- Ask questions if feedback is unclear
- Make requested changes promptly
- Mark conversations as resolved when addressed

### Review Checklist

- ✅ Code follows project standards
- ✅ Tests are included and passing
- ✅ Documentation is updated
- ✅ No breaking changes (or properly documented)
- ✅ Performance considerations addressed
- ✅ Security implications considered

## Getting Help

- **Documentation**: Check [docs/](docs/) and README files
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions
- **Contact**: Reach out to maintainers for urgent matters

## Additional Resources

- [Branch Protection Rules](.github/BRANCH_PROTECTION.md)
- [Architecture Documentation](docs/architecture_diagrams.md)
- [Tech Stack Documentation](docs/tech_stack.md)
- [Official GenAssist Documentation](https://docs.genassist.ai/)

Thank you for contributing to GenAssist! 🚀

