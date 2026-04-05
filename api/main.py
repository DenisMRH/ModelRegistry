from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.core.database import Base, engine
from api.routers import models

from api.models import registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Model Registry API", lifespan=lifespan)
app.include_router(models.router)
