# Infrastructure

Docker, environment configuration, and Terraform IaC for Propel.

## Contents

```
infrastructure/
├── docker/
│   ├── dev.Dockerfile          # Dev container (Python 3.12, Node 22, AWS CLI)
│   ├── backend.Dockerfile      # Dev FastAPI image (bind-mount, --reload)
│   ├── backend.prod.Dockerfile # Prod FastAPI image (baked code) -> ECR/ECS
│   ├── frontend.Dockerfile     # Dev Vite dev-server image
│   └── README.md               # Container setup (dev vs prod)
└── terraform/                  # AWS IaC: beta + prod (see terraform/README.md)
```

## Deployment

- **Self-hosting** (Docker Compose, env vars, integrations): [`../docs/self-hosting.md`](../docs/self-hosting.md)
- **Bootstrap runbook** (one-time AWS setup): [`../docs/deployment/bootstrap.md`](../docs/deployment/bootstrap.md)
- **CI/CD** (GitHub Actions): [`../docs/deployment/cicd.md`](../docs/deployment/cicd.md)
- **Local AWS SSO**: [`../docs/deployment/aws-sso.md`](../docs/deployment/aws-sso.md)
- **Containers** (dev vs prod, build/push): [`docker/README.md`](docker/README.md)
- **AWS infra reference** (Terraform modules/architecture): [`terraform/README.md`](terraform/README.md)

## Local stack

The root `docker-compose.yml` orchestrates the full local stack:

| Service  | Port | Description              |
|----------|------|--------------------------|
| postgres | 5432 | Postgres 18.3 database     |
| backend  | 8000 | FastAPI API + auth         |
| frontend | 5173 | Vite + React dashboard   |
| ingestion | 3001 | Dagster scheduler + UI  |
| dask-worker | — | Ingestion job executor |

```bash
cp .env.example .env
docker compose up
```

For integration setup (GitHub App, Linear OAuth) and every environment variable,
see the [self-hosting guide](../docs/self-hosting.md).

## Dev container

Open the repo in a dev container (VS Code / Cursor: **Dev Containers: Reopen in Container**). Docker Compose runs on the **host** — no Docker-in-Docker and no Docker CLI inside the dev container.

On open, the host starts:

| Service  | Role                                      |
|----------|-------------------------------------------|
| dev      | Your editor environment (Python 3.12, uv, Node 22, AWS CLI) |
| postgres | Database                                  |
| backend  | FastAPI with `uvicorn --reload`           |
| frontend | Vite dev server with HMR                  |

The dev, backend, and frontend services all share the same workspace bind mount. Edit code in the dev container and the backend/frontend containers pick up changes automatically via hot reload.

| URL | Service |
|-----|---------|
| http://localhost:8000 | FastAPI backend |
| http://localhost:5173 | Vite frontend |

`postCreateCommand` runs `scripts/setup.sh` to install frontend `node_modules` and backend Python deps (`uv sync`). `postAttachCommand` runs `scripts/dev.sh` to verify services are reachable.

The `dev` service shares the Compose network, so Postgres is reachable at `postgres:5432` from inside the dev container (`psql` client is preinstalled).

`dev.Dockerfile` installs the dev tooling and configures `git config --system safe.directory` so bind-mounted workspaces from WSL/Windows do not trigger dubious-ownership errors.

### Dev image build fails with `crc32 mismatch` or `invalid deflate data`

This usually means **Docker Desktop cache corruption** on Windows, not a bad Dockerfile. Try in order:

1. **Prune build cache and remove the broken image**
   ```powershell
   docker builder prune -af
   docker rmi propel-dev:latest -f
   ```
2. **Restart Docker Desktop** (or run `wsl --shutdown`, then reopen Docker).
3. **Rebuild without cache**
   ```powershell
   docker compose build dev --no-cache --progress=plain
   ```
4. If it still fails: Docker Desktop → Settings → General → disable **Use containerd for pulling and storing images**, restart, rebuild.

The dev Dockerfile splits apt packages, Node, and AWS CLI into separate layers so a retry does not redo the entire install.

## Related

- [Backend](../backend/README.md)
- [Frontend](../frontend/README.md)
- [Transformation](../transformation/README.md)
