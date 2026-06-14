-- Creates Zitadel's database on first Postgres boot (docker-entrypoint-initdb.d).
-- Safe to re-run: CREATE DATABASE cannot be repeated, so we guard with a DO block.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'zitadel') THEN
    CREATE DATABASE zitadel;
  END IF;
END
$$;
