from contextlib import asynccontextmanager
from fastapi import FastAPI

from .api.errors import register_handlers
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

    @app.get("/health")
    def health():
        return {"ok": True, "version": settings.version}

    return app


app = create_app()
