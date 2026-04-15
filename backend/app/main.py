from fastapi import FastAPI

from .settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Nomenclator", version=settings.version)

    @app.get("/health")
    def health():
        return {"ok": True, "version": settings.version}

    return app


app = create_app()
