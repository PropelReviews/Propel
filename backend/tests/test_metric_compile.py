"""Tests for metric compile dirty-set enqueue + single-flight claim."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.metric_definition import MetricCompileDirty, MetricCompileRun
from app.services import metric_compile as compile_svc


@pytest.mark.asyncio
async def test_enqueue_marks_dirty_without_running_row(
    db_engine, clean_db, monkeypatch
):
    monkeypatch.setenv("METRICS_COMPILE_SOURCE", "db")
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        result = await compile_svc.enqueue_compile(
            session,
            trigger="test",
            content_hashes=["abc123", "def456"],
            reason="unit",
        )
        await session.commit()
        assert result["status"] == "queued"
        assert set(result["dirtied"]) == {"abc123", "def456"}

        dirty = (await session.execute(select(MetricCompileDirty))).scalars().all()
        assert {d.content_hash for d in dirty} == {"abc123", "def456"}

        running = (
            (
                await session.execute(
                    select(MetricCompileRun).where(MetricCompileRun.status == "running")
                )
            )
            .scalars()
            .all()
        )
        assert running == []


@pytest.mark.asyncio
async def test_run_compile_claims_single_flight_and_clears_dirty(
    db_engine, clean_db, monkeypatch, tmp_path
):
    monkeypatch.setenv("METRICS_COMPILE_SOURCE", "db")
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        await compile_svc.enqueue_compile(
            session,
            trigger="test",
            content_hashes=["deadbeef"],
            reason="unit",
        )
        await session.commit()

        report = await compile_svc.run_compile(
            session, full=False, trigger="test", output_dir=tmp_path
        )
        await session.commit()
        assert report["source"] == "db"
        assert report["dirty_count"] == 1
        assert report.get("skipped") is False

        dirty = (await session.execute(select(MetricCompileDirty))).scalars().all()
        assert dirty == []

        runs = (await session.execute(select(MetricCompileRun))).scalars().all()
        assert len(runs) == 1
        assert runs[0].status == "succeeded"


@pytest.mark.asyncio
async def test_enqueue_deferred_when_files_source(db_engine, clean_db, monkeypatch):
    monkeypatch.setenv("METRICS_COMPILE_SOURCE", "files")
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        result = await compile_svc.enqueue_compile(
            session,
            trigger="test",
            content_hashes=["abc"],
            reason="unit",
        )
        await session.commit()
        assert result["status"] == "deferred"
        dirty = (await session.execute(select(MetricCompileDirty))).scalars().all()
        assert {d.content_hash for d in dirty} == {"abc"}
