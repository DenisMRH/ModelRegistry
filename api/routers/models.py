from sqlalchemy import Float, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from api.core.database import get_db
from api.core.s3_client import s3_client
from api.models.registry import ModelVersion, RegisteredModel, StageEnum
from api.schemas.registry import (
    ModelCreate,
    ModelResponse,
    ProductionResponse,
    StageUpdate,
    UploadResponse,
    VersionCreate,
    VersionResponse,
)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.post("", response_model=ModelResponse)
async def create_model(
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    existing = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Model with this name already exists")
    model = RegisteredModel(
        name=body.name,
        team_id=body.team_id,
        description=body.description,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return ModelResponse.model_validate(model)


@router.get("", response_model=list[ModelResponse])
async def list_models(
    team_id: str | None = None,
    stage: str | None = None,
    metric_key: str | None = None,
    metric_min: float | None = None,
    metric_max: float | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ModelResponse]:
    q = select(RegisteredModel).distinct()
    needs_join = stage is not None or (metric_key is not None and (metric_min is not None or metric_max is not None))

    if needs_join:
        q = q.join(ModelVersion, RegisteredModel.id == ModelVersion.model_id)

    if team_id is not None:
        q = q.where(RegisteredModel.team_id == team_id)
    if stage is not None:
        try:
            stage_enum = StageEnum(stage)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stage. Must be one of: {[s.value for s in StageEnum]}",
            )
        q = q.where(ModelVersion.stage == stage_enum)
    if metric_key is not None and (metric_min is not None or metric_max is not None):
        metric_expr = ModelVersion.metrics[metric_key].astext.cast(Float)
        if metric_min is not None:
            q = q.where(metric_expr >= metric_min)
        if metric_max is not None:
            q = q.where(metric_expr <= metric_max)

    q = q.order_by(RegisteredModel.created_at.desc())
    result = await db.execute(q)
    models = result.scalars().all()
    return [ModelResponse.model_validate(m) for m in models]


@router.post("/{model_name}/versions", response_model=UploadResponse)
async def create_version(
    model_name: str,
    body: VersionCreate,
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    model_result = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    model = model_result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    max_version_result = await db.execute(
        select(func.coalesce(func.max(ModelVersion.version), 0)).where(
            ModelVersion.model_id == model.id
        )
    )
    next_version = (max_version_result.scalar() or 0) + 1

    artifact_key = f"{model.team_id}/{model.name}/v{next_version}/model.pkl"

    version = ModelVersion(
        model_id=model.id,
        version=next_version,
        artifact_uri=artifact_key,
        stage=StageEnum.DEVELOPMENT,
        metrics=body.metrics,
        parameters=body.parameters,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)

    upload_url = s3_client.generate_presigned_upload_url(
        object_name=artifact_key,
        expiry=3600,
    )

    return UploadResponse(
        version_id=version.id,
        version=next_version,
        upload_url=upload_url,
    )


@router.patch("/{model_name}/versions/{version}/stage", response_model=VersionResponse)
async def update_version_stage(
    model_name: str,
    version: int,
    body: StageUpdate,
    db: AsyncSession = Depends(get_db),
) -> VersionResponse:
    model_result = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    model = model_result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    version_result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.version == version,
        )
    )
    model_version = version_result.scalar_one_or_none()
    if model_version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    if body.stage == StageEnum.PRODUCTION:
        await db.execute(
            update(ModelVersion)
            .where(
                ModelVersion.model_id == model.id,
                ModelVersion.stage == StageEnum.PRODUCTION,
            )
            .values(stage=StageEnum.ARCHIVED)
        )

    model_version.stage = body.stage
    await db.flush()
    await db.refresh(model_version)

    return VersionResponse.model_validate(model_version)


@router.get("/{model_name}/production", response_model=ProductionResponse)
async def get_production_version(
    model_name: str,
    db: AsyncSession = Depends(get_db),
) -> ProductionResponse:
    model_result = await db.execute(
        select(RegisteredModel).where(RegisteredModel.name == model_name)
    )
    model = model_result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    version_result = await db.execute(
        select(ModelVersion).where(
            ModelVersion.model_id == model.id,
            ModelVersion.stage == StageEnum.PRODUCTION,
        )
    )
    model_version = version_result.scalar_one_or_none()
    if model_version is None:
        raise HTTPException(
            status_code=404,
            detail="No Production version found for this model",
        )

    download_url = s3_client.generate_presigned_download_url(
        object_name=model_version.artifact_uri,
        expiry=3600,
    )

    return ProductionResponse(
        **VersionResponse.model_validate(model_version).model_dump(),
        download_url=download_url,
    )
