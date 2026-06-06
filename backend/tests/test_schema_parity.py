"""Guard against drift between the ORM models and the Alembic migrations.

The Zitadel cutover (006) reshaped the auth tables and was only partially
reverted, leaving the `users` table missing columns fastapi-users maps —
every login/register then failed with 500. This test compares the fully
migrated schema against the ORM metadata so any such drift fails CI with an
explicit diff instead of surfacing as runtime UndefinedColumn errors.
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

import app.models  # noqa: F401 — register all models with metadata
from app.db.base import Base


@pytest.mark.asyncio
async def test_orm_matches_migrated_schema(db_engine):
    def diff_against_metadata(connection):
        context = MigrationContext.configure(connection)
        return compare_metadata(context, Base.metadata)

    async with db_engine.connect() as connection:
        diffs = await connection.run_sync(diff_against_metadata)

    assert diffs == [], f"ORM models and migrations have drifted: {diffs}"
