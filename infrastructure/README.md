# Infrastructure

Docker, environment configuration, and future IaC for Propel.

## Contents

```
infrastructure/
└── docker/
    ├── backend.Dockerfile    # Python 3.12 base for FastAPI + Meltano
    └── frontend.Dockerfile   # Node 20 base for Vite + React
```

## Local stack

The root `docker-compose.yml` orchestrates the full local stack:

| Service  | Port | Description              |
|----------|------|--------------------------|
| postgres | 5432 | Postgres 16 database     |
| backend  | 8000 | FastAPI + Meltano        |
| frontend | 5173 | Vite + React dashboard   |

```bash
cp .env.example .env
docker-compose up
```

## Dev container

For VS Code / Cursor local development, use the root `.devcontainer/` configuration. It provides Python 3.12, Node 20, and Docker-in-Docker.

## Related

- [Backend](../backend/README.md)
- [Frontend](../frontend/README.md)
- [Transformation](../transformation/README.md)
