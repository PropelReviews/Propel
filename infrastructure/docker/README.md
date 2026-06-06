# Containers

Propel uses two distinct sets of container images: **dev** images for local
development (orchestrated by `docker-compose.yml`) and a single **prod** image
for the API that is shipped to AWS.

## Image matrix

| Image / file | Where it runs | How it's built | Deployed to AWS? |
|--------------|---------------|----------------|------------------|
| `dev.Dockerfile` | Local dev container (editor) | `docker compose` (service `dev`) | No |
| `backend.Dockerfile` | Local `backend` service | `docker compose`, source bind-mounted, `uvicorn --reload` | No |
| `frontend.Dockerfile` | Local `frontend` service | `docker compose`, source bind-mounted, `vite dev` | No |
| `postgres:16` | Local `postgres` service | Pulled image | No (RDS Aurora in AWS) |
| `backend.prod.Dockerfile` | **ECS Fargate** | `docker build` (context `backend/`) -> ECR | **Yes** |
| Frontend (built `dist/`) | **S3 + CloudFront** | `vite build` -> `aws s3 sync` | **Yes (not a container)** |

> The frontend is **not** containerized in production. The dev `frontend.Dockerfile`
> only runs the Vite dev server for local hot-reload. In AWS the SPA is built to
> static assets and served from S3 behind CloudFront (see
> [`../terraform/README.md`](../terraform/README.md)).

## Local development

```bash
cp .env.example .env
docker compose up
```

| Service  | Port | Notes |
|----------|------|-------|
| postgres | 5432 | Postgres 16, named volume `pgdata` |
| backend  | 8000 | FastAPI with `uvicorn --reload`, `./backend` bind-mounted |
| frontend | 5173 | Vite dev server (HMR) for the app, `./frontend` bind-mounted |
| frontend-landing | 5174 | Vite dev server (HMR) for the marketing landing site (apex/www in prod), `./frontend` bind-mounted |

The `dev`, `backend`, and `frontend` services share the workspace bind mount, so
edits are picked up automatically via hot reload. `node_modules` for the
frontend lives on a shared volume (installed by `scripts/setup.sh`).

### Dev vs prod backend image

| | `backend.Dockerfile` (dev) | `backend.prod.Dockerfile` (prod) |
|--|----------------------------|----------------------------------|
| App code | Bind-mounted (`./backend:/app`) | Baked in (`COPY app ./app`) |
| Reload | `--reload` (hot reload) | none (stable workers) |
| Build context | repo root | `backend/` |
| Target | local Compose | ECR -> ECS Fargate |

## Production API image

Build and run locally to sanity-check the production image:

```bash
# Build (context is the backend/ directory)
docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api backend

# Run it (FastAPI on :8000)
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://propel:propel@host.docker.internal:5432/propel \
  propel-api
curl localhost:8000/health   # {"status":"ok"}
```

### Push to ECR / deploy

You normally never push by hand — `scripts/deploy-api.sh <beta|prod>` and the
GitHub Actions workflows do it. Under the hood:

```bash
# Image tagging: <ecr-repo-url>:<tag>  (default tag: latest; CI may use a git SHA)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -f infrastructure/docker/backend.prod.Dockerfile -t <ecr-repo-url>:latest backend
docker push <ecr-repo-url>:latest
aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment
```

The ECR repository URL, cluster, and service names come from
`terraform output` (see `scripts/deploy-api.sh`).

### Logging

The ECS task has **no `logConfiguration`** (no CloudWatch). Container stdout is
not collected; observability is exported to PostHog by the app itself via
OpenTelemetry traces (`backend/app/tracing.py`), gated on `POSTHOG_TOKEN`.
