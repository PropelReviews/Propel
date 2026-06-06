# AGENTS.md

Guidance for AI agents working in this repository.

## Cursor Cloud specific instructions

### Product overview

Propel is an open-source developer analytics platform (FastAPI backend, React/Vite frontend, PostgreSQL). The documented local stack uses `docker-compose up` after `cp .env.example .env` (see `README.MD` and `CONTRIBUTING.md`).

### Native development (no Docker)

The Cloud Agent VM does not include Docker. Run services natively instead:

| Service | Port | How to start |
|---------|------|--------------|
| PostgreSQL 16 | 5432 | `sudo pg_ctlcluster 16 main start` (or `sudo service postgresql start`) |
| FastAPI backend | 8000 | From `backend/`: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Vite frontend | 5173 | From `frontend/`: `npm run dev -- --host 0.0.0.0` |

Ensure `~/.local/bin` is on `PATH` so `uvicorn` is found after `pip3 install`.

**One-time Postgres setup** (if the `propel` role/database do not exist):

```bash
sudo -u postgres psql -c "CREATE USER propel WITH PASSWORD 'propel' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE propel OWNER propel;"
```

Connection string for local runs: `postgresql://propel:propel@localhost:5432/propel` (see `.env.example`).

### Lint / test / build

There are no root-level lint or test scripts yet. Useful checks today:

- **Frontend type-check + build:** `cd frontend && npm run build`
- **Backend smoke test:** `curl http://localhost:8000/health` → `{"status":"ok"}`

### Gotchas

- `scripts/setup.sh` and `scripts/dev.sh` are referenced in `.devcontainer/devcontainer.json` and `infrastructure/README.md` but are **not present** in the repo. Run `npm install` in `frontend/` manually.
- The frontend Docker image expects `node_modules` on the bind mount; without `scripts/setup.sh`, run `npm install` before `docker-compose up` if using Docker elsewhere.
- Meltano (`backend/meltano/`) and dbt (`transformation/dbt/`) are placeholders — not required for the current Hello World stack.
- Optional integration env vars (`GITHUB_TOKEN`, `LINEAR_API_KEY`, `CURSOR_API_KEY`) are only needed for future data extraction work.
