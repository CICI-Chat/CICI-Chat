from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.api.images import parse_json_list
from app.database import get_db
from app.models import Image
from app.schemas import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    images = db.query(Image).options(joinedload(Image.annotation)).all()
    tag_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()

    for image in images:
        format_counts[image.format] += 1
        if image.annotation:
            tag_counts.update(str(tag) for tag in parse_json_list(image.annotation.tags))

    return StatsResponse(
        total_images=len(images),
        tags=dict(tag_counts),
        formats=dict(format_counts),
    )
