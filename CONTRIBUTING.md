# Contributing to Propel

Thank you for your interest in contributing. Propel is an open source project, and contributions from the community are what make transparent developer analytics possible.

## What you can contribute

| Area | Examples |
|---|---|
| **Metrics & data models** | New dbt models, metric definitions, SQL improvements |
| **Integrations** | Connectors for GitHub, Linear, Cursor, and other tools |
| **Application** | FastAPI backend, React frontend, dashboard features |
| **Documentation** | README improvements, setup guides, metric explanations |
| **Issues** | Bug reports, feature requests, questions about how metrics work |

Metric contributions are especially valuable. Because transparency is central to Propel, every new metric should include a clear definition and the SQL that produces it.

## Getting set up

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Git](https://git-scm.com/)

### Local environment

```bash
git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
docker-compose up
```

Once the project structure is in place, component-specific setup instructions will live alongside each service. Check the relevant directory README when working on a particular layer.

## How to contribute

### Report a bug or request a feature

Open an [issue](https://github.com/PropelReviews/Propel/issues) with:

- A clear description of the problem or proposal
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Your environment (OS, Docker version, etc.) when relevant

For metric-related issues, include which metric is affected and, if you can, the SQL or dbt model involved.

### Submit a pull request

1. Fork the repository and create a branch from `main`
2. Make your changes
3. Run checks locally (see [Code quality](#code-quality))
4. Test locally with `docker-compose up`
5. Open a pull request against `main`

**Pull request guidelines:**

- Keep changes focused — one concern per PR when possible
- Write a clear description of what changed and why
- For new metrics, include the definition and link to the dbt model or SQL
- Update documentation if your change affects setup, configuration, or behavior

### Commit messages

Write commit messages that explain the intent behind the change:

```
Add cycle time metric for pull requests

Defines cycle time as time from PR open to merge, using the
github_pull_requests dbt model.
```

## Code quality

CI runs linting, formatting, type checks, tests, and builds on every pull request. Run the same checks locally before opening a PR:

```bash
# Frontend (from frontend/)
npm run lint          # ESLint
npm run format:check  # Prettier
npm run typecheck     # TypeScript
npm test
npm run build
npm run build:landing

# Backend (from backend/)
uv run ruff check .
uv run ruff format --check .
uv run pytest

# Terraform (from infrastructure/terraform/)
terraform fmt -check -recursive
```

To auto-fix formatting issues:

```bash
cd frontend && npm run format
cd backend && uv run ruff format .
```

## Code of conduct

Be direct, be respectful, and assume good intent. Propel exists because teams deserve analytics they can trust, that starts with how we work together on the project.

## Questions

Open a [GitHub issue](https://github.com/PropelReviews/Propel/issues) or start a [discussion](https://github.com/PropelReviews/Propel/discussions) if you are unsure where a change belongs or want feedback before writing code.

## License

By contributing to Propel, you agree that your contributions will be licensed under the same terms as the rest of the project:

- Code outside `ee/` is licensed under the [MIT License](LICENSE)
- Code in `ee/` is licensed under the [Propel Enterprise License](ee/LICENSE)
