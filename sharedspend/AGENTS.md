# SharedSpend Development Guidelines

## Repository Workflow

- This repository is `SharedSpend-clone`, the development repository.
- Develop, test, and commit changes here.
- The private `SharedSpend` repository is the stable/master repository.
- Do not modify or push to the private master repository unless explicitly instructed.
- Never force-push.
- Do not commit changes unless explicitly requested.
- `Start_SharedSpend.bat` is tracked at the repository root; keep it limited to relative project paths and local development startup settings. Do not remove it from version control unless explicitly requested.

## Before Making Changes

1. Inspect the existing implementation.
2. Understand the relevant backend and frontend flow.
3. Make the smallest targeted change necessary.
4. Avoid unrelated refactoring or formatting changes.

## Validation

For backend changes:

```bash
cd backend
pytest
```

For frontend changes:

```bash
cd frontend
npm run build
```

Run relevant frontend tests when applicable:

```bash
cd frontend
npm test
```

## Backend

- FastAPI + SQLAlchemy async ORM.
- Keep API routes under `/api/v1`.
- Use existing services, schemas, and models where appropriate.
- Use Alembic migrations for database schema changes.
- Do not modify the database schema without considering migration requirements.

## Frontend

- React + TypeScript + Vite.
- Use existing components and patterns before introducing new ones.
- Use TanStack Query for server state.
- Use the existing API clients in `src/api/`.
- Use the `@` alias for `src/`.
- Avoid unnecessary UI/library changes.

## Git

Before finishing a task, show:

```bash
git status
git diff --stat
git diff
```

Do not commit or push unless the user explicitly asks.

## Safety

- Do not delete files or data without explicit approval.
- Do not run destructive Git commands.
- Do not modify unrelated files.
- Do not silently change dependency versions.
- Do not run `npm audit fix` unless explicitly requested.
