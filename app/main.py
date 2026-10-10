"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.database import engine, initialize_database
from app import models  # noqa: F401 - registers models with Base.metadata
from app.routers.jobs import router as jobs_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create database tables when the application starts."""
    initialize_database(engine)
    yield


app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)
app.include_router(jobs_router)


@app.get("/")
def health_check() -> dict[str, str]:
    """Confirm that the API is running."""
    return {"status": "ok"}
