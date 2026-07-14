"""Metric definition store tables (M4).

Revision ID: 013
Revises: 012
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("yaml", sa.Text(), nullable=False),
        sa.Column(
            "resolved_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column(
            "parent_pin",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("catalog_version", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("org_id", "metric_id", "version"),
        sa.CheckConstraint(
            "kind in ('Metric','MetricSet','DimensionMapping')",
            name="ck_metric_definitions_kind",
        ),
        sa.CheckConstraint(
            "status in ('draft','active','deprecated','archived','broken')",
            name="ck_metric_definitions_status",
        ),
    )
    op.create_index(
        "one_active_version",
        "metric_definitions",
        ["org_id", "metric_id"],
        unique=True,
        postgresql_where=sa.text("status in ('active','broken')"),
    )
    op.create_index(
        "defs_by_hash",
        "metric_definitions",
        ["content_hash"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "org_metric_enrollment",
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("definition_org", sa.Text(), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column(
            "params_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("org_id", "metric_id"),
    )

    op.create_table(
        "definition_notices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("notice", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_definition_notices_org_metric",
        "definition_notices",
        ["org_id", "metric_id"],
    )

    op.create_table(
        "metric_compile_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column(
            "report_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "one_running_compile",
        "metric_compile_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "metric_compile_dirty",
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "marked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("content_hash"),
    )


def downgrade() -> None:
    op.drop_table("metric_compile_dirty")
    op.drop_index("one_running_compile", table_name="metric_compile_runs")
    op.drop_table("metric_compile_runs")
    op.drop_index("ix_definition_notices_org_metric", table_name="definition_notices")
    op.drop_table("definition_notices")
    op.drop_table("org_metric_enrollment")
    op.drop_index("defs_by_hash", table_name="metric_definitions")
    op.drop_index("one_active_version", table_name="metric_definitions")
    op.drop_table("metric_definitions")
