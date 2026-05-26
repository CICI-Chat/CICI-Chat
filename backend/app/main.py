from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import images, reindex, settings, stats
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.services.indexer import index_folders


def create_lifespan(run_startup_indexing: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_startup_indexing:
            init_db()
            settings_values = get_settings()
            with SessionLocal() as db:
                index_folders(settings_values.watch_folder_paths, db)
        yield

    return lifespan


def create_app(run_startup_indexing: bool = True) -> FastAPI:
    app = FastAPI(title="PicMind", lifespan=create_lifespan(run_startup_indexing))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(images.router)
    app.include_router(stats.router)
    app.include_router(settings.router)
    app.include_router(reindex.router)
    return app


app = create_app()
