import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Query as SqlAlchemyQuery
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Annotation, Image
from app.schemas import ImageDetail, ImageFolder, ImageItem, ImageList

router = APIRouter(prefix="/api/images", tags=["images"])


def parse_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def to_image_item(image: Image) -> ImageItem:
    annotation = image.annotation
    tags = parse_json_list(annotation.tags) if annotation else []
    caption = annotation.caption if annotation else ""
    model_used = annotation.model_used if annotation else ""
    return ImageItem(
        id=image.id,
        file_path=image.file_path,
        file_size=image.file_size,
        width=image.width,
        height=image.height,
        format=image.format,
        created_at=image.created_at,
        modified_at=image.modified_at,
        indexed_at=image.indexed_at,
        caption=caption,
        tags=tags,
        model_used=model_used,
        image_url=f"/api/images/{image.id}/file",
    )


def to_image_detail(image: Image) -> ImageDetail:
    item = to_image_item(image)
    annotation = image.annotation
    return ImageDetail(
        **item.model_dump(),
        objects=parse_json_list(annotation.objects) if annotation else [],
    )


SORT_COLUMNS = {
    "indexed_at": Image.indexed_at,
    "modified_at": Image.modified_at,
    "file_size": Image.file_size,
    "width": Image.width,
    "height": Image.height,
}

COLOR_FAMILIES: tuple[tuple[str, str], ...] = (
    ("红色", "red"),
    ("橙色", "orange"),
    ("黄色", "yellow"),
    ("绿色", "green"),
    ("青色", "cyan"),
    ("蓝色", "blue"),
    ("紫色", "purple"),
    ("粉色", "pink"),
    ("棕色", "brown"),
    ("灰色", "gray"),
)

COLOR_SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    "黑色": ("黑色",),
    "black": ("黑色",),
    "白色": ("白色",),
    "white": ("白色",),
}

for chinese_name, english_name in COLOR_FAMILIES:
    light_name = f"浅{chinese_name}"
    dark_name = f"深{chinese_name}"
    COLOR_SEARCH_ALIASES[chinese_name] = (light_name, chinese_name, dark_name)
    COLOR_SEARCH_ALIASES[light_name] = (light_name,)
    COLOR_SEARCH_ALIASES[dark_name] = (dark_name,)
    COLOR_SEARCH_ALIASES[english_name] = (light_name, chinese_name, dark_name)
    COLOR_SEARCH_ALIASES[f"light {english_name}"] = (light_name,)
    COLOR_SEARCH_ALIASES[f"dark {english_name}"] = (dark_name,)
    COLOR_SEARCH_ALIASES[f"deep {english_name}"] = (dark_name,)

COLOR_SEARCH_ALIASES["grey"] = COLOR_SEARCH_ALIASES["gray"]
COLOR_SEARCH_ALIASES["light grey"] = COLOR_SEARCH_ALIASES["light gray"]
COLOR_SEARCH_ALIASES["dark grey"] = COLOR_SEARCH_ALIASES["dark gray"]
COLOR_SEARCH_ALIASES["deep grey"] = COLOR_SEARCH_ALIASES["deep gray"]


def normalized_color_search_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def color_search_labels(value: str) -> tuple[str, ...]:
    return COLOR_SEARCH_ALIASES.get(normalized_color_search_text(value), (value,))


def normalized_file_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve())))


def watch_roots(settings: Settings) -> list[Path]:
    return [path.resolve() for path in settings.watch_folder_paths]


def resolve_watch_folder(folder: str, settings: Settings) -> Path:
    requested = Path(folder).resolve()
    for root in watch_roots(settings):
        try:
            requested.relative_to(root)
        except ValueError:
            continue
        return requested
    raise HTTPException(status_code=400, detail="Folder must be inside a watch folder")


def folder_like_pattern(folder: Path) -> str:
    return f"{escape_like(normalized_file_path(folder))}{escape_like(os.sep)}%"


def apply_image_filters(
    query: SqlAlchemyQuery,
    *,
    q: str | None = None,
    tag: str | None = None,
    image_format: str | None = None,
    folder: str | None = None,
    settings: Settings,
    unrecognized_only: bool = False,
) -> SqlAlchemyQuery:
    search_text = q.strip() if q else ""
    if search_text:
        escaped_search_text = escape_like(search_text)
        search_pattern = f"%{escaped_search_text}%"
        tag_filters = [
            Annotation.tags.ilike(f'%"{escape_like(label)}"%', escape="\\")
            for label in color_search_labels(search_text)
        ]
        query = query.filter(
            or_(
                Image.file_path.ilike(search_pattern, escape="\\"),
                Annotation.caption.ilike(search_pattern, escape="\\"),
                *tag_filters,
            )
        )

    tag_text = tag.strip() if tag else ""
    if tag_text:
        query = query.filter(Annotation.tags.ilike(f'%"{escape_like(tag_text)}"%', escape="\\"))

    format_text = image_format.strip() if image_format else ""
    if format_text:
        query = query.filter(Image.format == format_text)

    folder_text = folder.strip() if folder else ""
    if folder_text:
        query = query.filter(Image.file_path.ilike(folder_like_pattern(resolve_watch_folder(folder_text, settings)), escape="\\"))

    if unrecognized_only:
        query = query.filter(Annotation.tags.ilike('%"待分析"%'))

    return query


@router.get("/folders", response_model=list[ImageFolder])
def list_image_folders(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[ImageFolder]:
    roots = watch_roots(settings)
    counts: Counter[Path] = Counter()
    for (file_path,) in db.query(Image.file_path).all():
        parent = Path(file_path).resolve().parent
        if any(is_path_relative_to(parent, root) for root in roots):
            counts[parent] += 1

    return [
        ImageFolder(path=str(path), name=path.name, image_count=count)
        for path, count in sorted(counts.items(), key=lambda item: str(item[0]))
    ]


def is_path_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@router.get("", response_model=ImageList)
def list_images(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    tag: str | None = None,
    q: str | None = None,
    folder: str | None = None,
    image_format: str | None = Query(default=None, alias="format"),
    sort: str = "indexed_at",
    order: str = "desc",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImageList:
    sort_column = SORT_COLUMNS.get(sort)
    if sort_column is None:
        raise HTTPException(status_code=400, detail="Unsupported sort field")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Unsupported sort order")

    query = apply_image_filters(
        db.query(Image).outerjoin(Annotation).options(joinedload(Image.annotation)),
        q=q,
        tag=tag,
        image_format=image_format,
        folder=folder,
        settings=settings,
    )

    total = query.count()
    order_by = asc(sort_column) if order == "asc" else desc(sort_column)
    images = query.order_by(order_by).offset((page - 1) * size).limit(size).all()
    return ImageList(items=[to_image_item(image) for image in images], total=total, page=page, size=size)


@router.get("/{image_id}", response_model=ImageDetail)
def get_image(image_id: str, db: Session = Depends(get_db)) -> ImageDetail:
    image = db.query(Image).options(joinedload(Image.annotation)).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return to_image_detail(image)


@router.get("/{image_id}/file")
def get_image_file(image_id: str, db: Session = Depends(get_db)) -> FileResponse:
    image = db.query(Image).options(joinedload(Image.annotation)).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(image.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(file_path)
