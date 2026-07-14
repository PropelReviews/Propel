"""Tenant-scoped metric definition management (M4 + M5 read/authoring APIs).

Uses query param ``metric_id`` for dotted ids (e.g. propel.cycle_time).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.metric_definitions import (
    ActivateBody,
    ClassifyBody,
    ClassifyResponse,
    CompileRunRead,
    DiffBody,
    DiffResponse,
    DimensionMappingSummary,
    DraftPutBody,
    GeneratedSqlResponse,
    MetricCatalogResponse,
    MetricDefinitionRead,
    MetricHealthSummary,
    MetricSetRead,
    MetricSummaryRead,
    MetricVersionRead,
    ValidateResponse,
    YamlBody,
)
from app.services import metric_definitions as svc

router = APIRouter(prefix="/api/v1", tags=["metric-definitions"])


@router.get(
    "/tenants/{tenant_id}/metric-definitions",
    response_model=list[MetricSummaryRead],
)
async def list_metric_definitions(
    referencable: bool = Query(default=False),
    entity: str | None = Query(default=None),
    include_drafts: bool = Query(default=True),
    include_broken: bool = Query(default=True),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await svc.list_resolved_summaries(
        session,
        ctx.tenant.slug,
        referencable=referencable,
        entity=entity,
        include_drafts=include_drafts,
        include_broken=include_broken,
    )
    return [MetricSummaryRead.model_validate(r) for r in rows]


@router.get(
    "/tenants/{tenant_id}/metric-catalog",
    response_model=MetricCatalogResponse,
)
async def get_metric_catalog(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return MetricCatalogResponse.model_validate(
        await svc.get_metric_catalog(session, ctx.tenant.slug)
    )


@router.get(
    "/tenants/{tenant_id}/metric-definitions/detail",
    response_model=MetricDefinitionRead,
)
async def get_metric_definition(
    metric_id: str = Query(..., description="Full namespaced metric id"),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    detail = await svc.get_definition_detail(session, ctx.tenant.slug, metric_id)
    return MetricDefinitionRead.model_validate(detail)


@router.get(
    "/tenants/{tenant_id}/metric-definitions/versions",
    response_model=list[MetricVersionRead],
)
async def list_metric_definition_versions(
    metric_id: str = Query(...),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await svc.list_definition_versions(session, ctx.tenant.slug, metric_id)
    return [MetricVersionRead.model_validate(r) for r in rows]


@router.get(
    "/tenants/{tenant_id}/metric-definitions/sql",
    response_model=GeneratedSqlResponse,
)
async def get_metric_generated_sql(
    metric_id: str = Query(...),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return GeneratedSqlResponse.model_validate(
        await svc.get_generated_sql(session, ctx.tenant.slug, metric_id)
    )


@router.post(
    "/tenants/{tenant_id}/metric-definitions:diff",
    response_model=DiffResponse,
)
async def diff_metric_definitions(
    body: DiffBody,
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return DiffResponse.model_validate(
        await svc.diff_definitions(
            session,
            ctx.tenant.slug,
            metric_id=body.metric_id,
            from_version=body.from_version,
            to_version=body.to_version,
            from_yaml=body.from_yaml,
            to_yaml=body.to_yaml,
        )
    )


@router.post(
    "/tenants/{tenant_id}/metric-definitions:validate",
    response_model=ValidateResponse,
)
async def validate_metric_definition(
    body: YamlBody,
    ctx=Depends(require_permission("metrics:read")),
):
    _ = ctx
    return ValidateResponse.model_validate(await svc.validate_definition(body.yaml))


@router.post(
    "/tenants/{tenant_id}/metric-definitions",
    response_model=MetricDefinitionRead,
    status_code=201,
)
async def create_metric_definition(
    body: YamlBody,
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    row = await svc.create_draft(
        session,
        ctx.tenant.slug,
        body.yaml,
        created_by=str(user.id),
    )
    detail = await svc.get_definition_detail(session, ctx.tenant.slug, row.metric_id)
    return MetricDefinitionRead.model_validate(detail)


@router.put(
    "/tenants/{tenant_id}/metric-definitions/draft",
    response_model=MetricDefinitionRead,
)
async def put_metric_definition_draft(
    body: DraftPutBody,
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Autosave draft with optimistic concurrency (409 on version/revision mismatch)."""
    row = await svc.create_draft(
        session,
        ctx.tenant.slug,
        body.yaml,
        created_by=str(user.id),
        expected_version=body.expected_version,
        expected_revision=body.expected_revision,
    )
    detail = await svc.get_definition_detail(session, ctx.tenant.slug, row.metric_id)
    return MetricDefinitionRead.model_validate(detail)


@router.post(
    "/tenants/{tenant_id}/metric-definitions:classify",
    response_model=ClassifyResponse,
)
async def classify_metric_definition(
    body: ClassifyBody,
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return ClassifyResponse.model_validate(
        await svc.classify_definition(
            session,
            ctx.tenant.slug,
            body.yaml,
            previous_version=body.previous_version,
        )
    )


@router.post(
    "/tenants/{tenant_id}/metric-definitions:activate",
    response_model=MetricDefinitionRead,
)
async def activate_metric_definition(
    body: ActivateBody,
    metric_id: str = Query(...),
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    row = await svc.activate_definition(
        session, ctx.tenant.slug, metric_id, version=body.version
    )
    detail = await svc.get_definition_detail(session, ctx.tenant.slug, row.metric_id)
    return MetricDefinitionRead.model_validate(detail)


@router.post(
    "/tenants/{tenant_id}/metric-definitions:repin",
    response_model=MetricDefinitionRead,
)
async def repin_metric_definition(
    metric_id: str = Query(...),
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    row = await svc.repin_definition(
        session, ctx.tenant.slug, metric_id, created_by=str(user.id)
    )
    detail = await svc.get_definition_detail(session, ctx.tenant.slug, row.metric_id)
    return MetricDefinitionRead.model_validate(detail)


@router.post(
    "/tenants/{tenant_id}/metric-definitions:archive",
    response_model=MetricDefinitionRead,
)
async def archive_metric_definition(
    metric_id: str = Query(...),
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    row = await svc.archive_definition(session, ctx.tenant.slug, metric_id)
    return MetricDefinitionRead(
        org_id=row.org_id,
        metric_id=row.metric_id,
        version=row.version,
        revision=row.revision,
        status=row.status,
        kind=row.kind,
        yaml=row.yaml,
        resolved_json=row.resolved_json,
        content_hash=row.content_hash,
        parent_pin=row.parent_pin,
        notices=[],
    )


@router.get(
    "/tenants/{tenant_id}/metric-set",
    response_model=MetricSetRead,
)
async def get_metric_set(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return MetricSetRead.model_validate(
        await svc.get_metric_set(session, ctx.tenant.slug)
    )


@router.put(
    "/tenants/{tenant_id}/metric-set",
    response_model=MetricSetRead,
)
async def put_metric_set(
    body: YamlBody,
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await svc.put_metric_set(
        session, ctx.tenant.slug, body.yaml, created_by=str(user.id)
    )
    return MetricSetRead.model_validate(
        await svc.get_metric_set(session, ctx.tenant.slug)
    )


@router.get(
    "/tenants/{tenant_id}/dimension-mappings",
    response_model=list[DimensionMappingSummary],
)
async def list_dimension_mappings(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await svc.list_dimension_mappings(session, ctx.tenant.slug)
    return [DimensionMappingSummary.model_validate(r) for r in rows]


@router.get("/tenants/{tenant_id}/dimension-mappings/detail")
async def get_dimension_mapping(
    mapping_id: str = Query(...),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return await svc.get_dimension_mapping(session, ctx.tenant.slug, mapping_id)


@router.put("/tenants/{tenant_id}/dimension-mappings")
async def put_dimension_mapping(
    body: YamlBody,
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    row = await svc.put_dimension_mapping(
        session, ctx.tenant.slug, body.yaml, created_by=str(user.id)
    )
    return await svc.get_dimension_mapping(session, ctx.tenant.slug, row.metric_id)


@router.get(
    "/tenants/{tenant_id}/metric-health",
    response_model=MetricHealthSummary,
)
async def get_metric_health(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return MetricHealthSummary.model_validate(
        await svc.get_metric_health(session, ctx.tenant.slug)
    )


@router.get(
    "/tenants/{tenant_id}/metric-compile-runs",
    response_model=list[CompileRunRead],
)
async def list_metric_compile_runs(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    _ = ctx
    rows = await svc.list_compile_runs(session)
    return [CompileRunRead.model_validate(r) for r in rows]


@router.post(
    "/tenants/{tenant_id}/metric-compile-runs:enqueue",
)
async def enqueue_metric_compile(
    ctx=Depends(require_permission("metrics:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    """Mark enrollment hashes dirty so the Dagster dirty-set sensor drains them."""
    from app.services import metric_compile as compile_svc
    from app.services.metric_store import SqlAlchemyDefinitionStore

    sql = SqlAlchemyDefinitionStore(session)
    enrollments = await sql.list_enrollments(ctx.tenant.slug)
    hashes = [e.content_hash for e in enrollments if e.content_hash]
    result = await compile_svc.enqueue_compile(
        session,
        trigger="api",
        content_hashes=hashes,
        reason=f"api-enqueue:{ctx.tenant.slug}",
    )
    await session.commit()
    return result
