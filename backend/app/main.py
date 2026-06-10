from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import images, recognition, reindex, settings, stats
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.services.batch_recognition import BatchRecognitionService, RecognitionBatchWorker
from app.services.indexer import index_folders
from app.services.recognition import RecognitionService, build_recognizer


def create_lifespan(run_startup_indexing: bool, run_batch_worker: bool):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_startup_indexing:
            init_db()
            settings_values = get_settings()
            with SessionLocal() as db:
                index_folders(settings_values.watch_folder_paths, db)
        if run_batch_worker:
            app.state.batch_recognition_service.recover_interrupted_batches()
            app.state.batch_recognition_worker.start()
        try:
            yield
        finally:
            if run_batch_worker:
                app.state.batch_recognition_worker.stop()

    return lifespan


def create_app(run_startup_indexing: bool = True, run_batch_worker: bool = True) -> FastAPI:
    app = FastAPI(title="PicMind", lifespan=create_lifespan(run_startup_indexing, run_batch_worker))
    app.state.batch_recognition_service = BatchRecognitionService(
        recognition_service=RecognitionService(recognizer=build_recognizer(get_settings()))
    )
    app.state.batch_recognition_worker = RecognitionBatchWorker(app.state.batch_recognition_service)

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
    app.include_router(recognition.router)
    return app


app = create_app()
