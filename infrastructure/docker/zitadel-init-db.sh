#!/bin/sh
# Creates Zitadel's database if missing. Safe to re-run.
set -eu

host="${PGHOST:-localhost}"
user="${POSTGRES_USER:?POSTGRES_USER is required}"
db="${POSTGRES_DB:?POSTGRES_DB is required}"

psql -v ON_ERROR_STOP=1 -h "$host" -U "$user" -d "$db" <<'EOSQL'
SELECT 'CREATE DATABASE zitadel'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'zitadel')\gexec
EOSQL
