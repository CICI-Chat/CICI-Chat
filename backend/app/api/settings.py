from fastapi import APIRouter

from app.config import get_settings
from app.schemas import SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        watch_folders=[str(path) for path in settings.watch_folder_paths],
        db_path=str(settings.db_path),
        provider=settings.recognition_provider,
    )
