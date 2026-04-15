from contextlib import asynccontextmanager
from fastapi import FastAPI

from .api.auth import router as auth_router
from .api.errors import register_handlers
from .api.jobs import router as jobs_router
from .api.spend import router as spend_router
from .anthropic.client import RealAnthropicClient
from .db import get_connection
from .settings import settings
from .worker.poller import Worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager that starts/stops the background worker."""
    client = RealAnthropicClient(api_key=settings.anthropic_api_key)
    worker = Worker(client=client, db_factory=get_connection)
    await worker.start()
    app.state.worker = worker
    app.state.anthropic_client = client
    try:
        yield
    finally:
        await worker.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nomenclator",
        version=settings.version,
        lifespan=lifespan,
    )

    register_handlers(app)
    app.include_router(auth_router, tags=["auth"])
    app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
    app.include_router(spend_router, prefix="/spend", tags=["spend"])

    @app.get("/health")
    def health():
        return {"ok": True, "version": settings.version}

    return app


app = create_app()
