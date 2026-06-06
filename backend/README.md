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
├── app/
│   ├── __init__.py
│   └── main.py     # FastAPI application
├── meltano/        # Meltano project — extractors and loaders (coming soon)
├── requirements.txt
└── README.md
```

## Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API listens on port `8000` by default.

### Endpoints

| Route | Description |
|---|---|
| `GET /` | Hello World |
| `GET /health` | Health check |

### Extraction (coming soon)

```bash
# From meltano/
meltano run tap-github target-postgres
```

## Related

- [Frontend](../frontend/README.md) — React dashboard
- [Transformation](../transformation/README.md) — dbt SQL transformations
- [Infrastructure](../infrastructure/README.md) — Docker and deployment config
