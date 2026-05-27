from datetime import datetime

from pydantic import BaseModel, Field


class ImageItem(BaseModel):
    id: str
    file_path: str
    file_size: int
    width: int
    height: int
    format: str
    created_at: datetime
    modified_at: datetime
    indexed_at: datetime
    caption: str
    tags: list[str]
    image_url: str


class ImageList(BaseModel):
    items: list[ImageItem]
    total: int
    page: int
    size: int


class ImageDetail(ImageItem):
    objects: list[dict[str, object]]
    model_used: str


class RecognitionBatchCreate(BaseModel):
    image_ids: list[str] = Field(max_length=200)


class RecognitionBatchResponse(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    pending: int
    running: int
    status: str


class StatsResponse(BaseModel):
    total_images: int
    tags: dict[str, int]
    formats: dict[str, int]


class SettingsResponse(BaseModel):
    watch_folders: list[str]
    db_path: str
    provider: str


class ReindexResponse(BaseModel):
    added: int
    skipped: int
    errors: int
