from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = Field(
        default="postgresql+asyncpg://model_registry_user:model_registry_password@localhost:5432/model_registry",
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
    )
    minio_url: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("MINIO_URL", "S3_ENDPOINT_URL"),
    )
    minio_public_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MINIO_PUBLIC_URL", "S3_PUBLIC_ENDPOINT_URL"),
    )
    minio_access_key: str = Field(
        default="minioadmin",
        validation_alias=AliasChoices("MINIO_ACCESS_KEY", "S3_ACCESS_KEY"),
    )
    minio_secret_key: str = Field(
        default="minioadminpassword",
        validation_alias=AliasChoices("MINIO_SECRET_KEY", "S3_SECRET_KEY"),
    )
    minio_bucket_name: str = Field(default="models", validation_alias="MINIO_BUCKET_NAME")


settings = Settings()
