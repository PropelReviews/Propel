# Backend

FastAPI application and data extraction for Propel.

## Stack

- **API:** FastAPI (Python 3.12)
- **Extraction:** Meltano (co-located in `meltano/` for shared Python environment)

## Purpose

The backend serves the Propel API and orchestrates data extraction from your toolchain (GitHub, Linear, Cursor) into Postgres via Meltano.

```
Your tools (GitHub, Linear, Cursor)
        │
        ▼
   meltano/          ← extraction
        │
        ▼
   Postgres         ← storage
        │
        ▼
   FastAPI           ← dashboards + API
```

## Directory layout

```
backend/
├── meltano/        # Meltano project — extractors and loaders
└── README.md
```

## Setup

Setup instructions coming soon. Once the app is scaffolded, local development will run via:

```bash
# API
uvicorn app.main:app --reload --port 8000

# Extraction (from meltano/)
meltano run tap-github target-postgres
```

## Related

- [Frontend](../frontend/README.md) — React dashboard
- [Transformation](../transformation/README.md) — dbt SQL transformations
- [Infrastructure](../infrastructure/README.md) — Docker and deployment config
