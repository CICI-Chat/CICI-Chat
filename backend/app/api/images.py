import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Annotation, Image
from app.schemas import ImageDetail, ImageItem, ImageList

router = APIRouter(prefix="/api/images", tags=["images"])


def parse_json_list(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def to_image_item(image: Image) -> ImageItem:
    annotation = image.annotation
    tags = parse_json_list(annotation.tags) if annotation else []
    caption = annotation.caption if annotation else ""
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
        image_url=f"/api/images/{image.id}/file",
    )


def to_image_detail(image: Image) -> ImageDetail:
    item = to_image_item(image)
    annotation = image.annotation
    return ImageDetail(
        **item.model_dump(),
        objects=parse_json_list(annotation.objects) if annotation else [],
        model_used=annotation.model_used if annotation else "",
    )


SORT_COLUMNS = {
    "indexed_at": Image.indexed_at,
    "modified_at": Image.modified_at,
    "file_size": Image.file_size,
    "width": Image.width,
    "height": Image.height,
}


@router.get("", response_model=ImageList)
def list_images(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    tag: str | None = None,
    q: str | None = None,
    image_format: str | None = Query(default=None, alias="format"),
    sort: str = "indexed_at",
    order: str = "desc",
    db: Session = Depends(get_db),
) -> ImageList:
    sort_column = SORT_COLUMNS.get(sort)
    if sort_column is None:
        raise HTTPException(status_code=400, detail="Unsupported sort field")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Unsupported sort order")

    query = db.query(Image).outerjoin(Annotation).options(joinedload(Image.annotation))

    search_text = q.strip() if q else ""
    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                Image.file_path.ilike(search_pattern),
                Annotation.caption.ilike(search_pattern),
                Annotation.tags.ilike(search_pattern),
            )
        )

    if tag is not None:
        tag_text = tag.strip()
        if tag_text:
            query = query.filter(Annotation.tags.ilike(f'%"{tag_text}"%'))

    if image_format is not None:
        format_text = image_format.strip()
        if format_text:
            query = query.filter(Image.format == format_text)

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
