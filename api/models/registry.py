import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class StageEnum(str, enum.Enum):
    DEVELOPMENT = "Development"
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


class RegisteredModel(Base):
    __tablename__ = "registered_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    versions: Mapped[list["ModelVersion"]] = relationship(
        "ModelVersion",
        back_populates="model",
        order_by="ModelVersion.version",
        cascade="all, delete-orphan",
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        Index("ix_model_versions_metrics_gin", "metrics", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registered_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[StageEnum | None] = mapped_column(
        Enum(StageEnum),
        default=StageEnum.DEVELOPMENT,
        nullable=True,
    )
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    model: Mapped["RegisteredModel"] = relationship(
        "RegisteredModel",
        back_populates="versions",
    )
