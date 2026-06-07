from datetime import datetime

from pydantic import BaseModel


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
    model_used: str
    image_url: str


class ImageList(BaseModel):
    items: list[ImageItem]
    total: int
    page: int
    size: int


class ImageFolder(BaseModel):
    path: str
    name: str
    image_count: int


class ImageDetail(ImageItem):
    objects: list[dict[str, object]]
    model_used: str


class RecognitionSelection(BaseModel):
    q: str | None = None
    tag: str | None = None
    format: str | None = None
    folder: str | None = None
    unrecognized_only: bool = False


class RecognitionBatchCreate(BaseModel):
    image_ids: list[str] | None = None
    selection: RecognitionSelection | None = None


class RecognitionBatchResponse(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    pending: int
    running: int
    cancelled: int = 0
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecognitionBatchList(BaseModel):
    items: list[RecognitionBatchResponse]
    total: int
    page: int
    size: int


class RecognitionBatchItemImage(BaseModel):
    id: str
    file_path: str
    caption: str
    image_url: str


class RecognitionBatchItemResponse(BaseModel):
    id: int
    image_id: str
    status: str
    error: str | None = None
    image: RecognitionBatchItemImage


class RecognitionBatchItemList(BaseModel):
    items: list[RecognitionBatchItemResponse]
    total: int
    page: int
    size: int


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
