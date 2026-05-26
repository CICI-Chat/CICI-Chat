from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas import ReindexResponse
from app.services.indexer import index_folders

router = APIRouter(prefix="/api/reindex", tags=["reindex"])


@router.post("", response_model=ReindexResponse)
def reindex(db: Session = Depends(get_db)) -> ReindexResponse:
    settings = get_settings()
    result = index_folders(settings.watch_folder_paths, db)
    return ReindexResponse(added=result.added, skipped=result.skipped, errors=result.errors)
