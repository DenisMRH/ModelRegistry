import os
import uuid

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://model_registry_user:model_registry_password@localhost:5432/model_registry",
)
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")

import pytest
import pytest_asyncio
from httpx import AsyncClient

API_URL = os.environ.get("TEST_API_URL", "http://localhost:8000")


@pytest.fixture
def unique_suffix():
    return str(uuid.uuid4())[:8]


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(base_url=API_URL, timeout=30.0) as ac:
        yield ac
