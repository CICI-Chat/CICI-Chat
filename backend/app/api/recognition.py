from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.images import apply_image_filters, to_image_detail
from app.config import Settings, get_settings
from app.database import get_db
from app.models import Annotation, Image
from app.schemas import ImageDetail, RecognitionBatchCreate, RecognitionBatchResponse
from app.services.batch_recognition import BatchNotFoundError, BatchRecognitionService, EmptyBatchError
from app.services.recognition import ImageFileMissingError, ImageNotFoundError, RecognitionService

router = APIRouter(tags=["recognition"])
recognition_service = RecognitionService()


def get_batch_recognition_service(request: Request) -> BatchRecognitionService:
    return request.app.state.batch_recognition_service


def selection_image_ids(payload: RecognitionBatchCreate, db: Session, settings: Settings) -> list[str]:
    if payload.image_ids is not None:
        image_ids = list(dict.fromkeys(payload.image_ids))
        existing_ids = {image_id for (image_id,) in db.query(Image.id).filter(Image.id.in_(image_ids)).all()}
        if len(existing_ids) != len(image_ids):
            raise HTTPException(status_code=400, detail="Batch contains unknown images")
        return image_ids
    if payload.selection is None:
        return []

    selection = payload.selection
    query = apply_image_filters(
        db.query(Image).outerjoin(Annotation),
        q=selection.q,
        tag=selection.tag,
        image_format=selection.format,
        folder=selection.folder,
        settings=settings,
        unrecognized_only=selection.unrecognized_only,
    )
    return [image.id for image in query.order_by(Image.indexed_at.desc()).all()]


@router.post("/api/images/{image_id}/recognize", response_model=ImageDetail)
def recognize_image(image_id: str, db: Session = Depends(get_db)) -> ImageDetail:
    try:
        image = recognition_service.recognize_image(image_id, db)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    except ImageFileMissingError as exc:
        raise HTTPException(status_code=404, detail="Image file not found") from exc
    return to_image_detail(image)


@router.post("/api/recognition/batches", response_model=RecognitionBatchResponse, status_code=status.HTTP_202_ACCEPTED)
def create_recognition_batch(
    payload: RecognitionBatchCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        batch = batch_service.create_batch(db, selection_image_ids(payload, db, settings))
    except EmptyBatchError as exc:
        raise HTTPException(status_code=400, detail="Batch must include at least one image") from exc
    return batch_service.get_batch_progress(db, batch.id)


@router.get("/api/recognition/batches/{batch_id}", response_model=RecognitionBatchResponse)
def get_recognition_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        return batch_service.get_batch_progress(db, batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc


@router.post("/api/recognition/batches/{batch_id}/pause", response_model=RecognitionBatchResponse)
def pause_recognition_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        batch_service.pause_batch(db, batch_id)
        return batch_service.get_batch_progress(db, batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc


@router.post("/api/recognition/batches/{batch_id}/resume", response_model=RecognitionBatchResponse)
def resume_recognition_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        batch_service.resume_batch(db, batch_id)
        return batch_service.get_batch_progress(db, batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc


@router.post("/api/recognition/batches/{batch_id}/cancel", response_model=RecognitionBatchResponse)
def cancel_recognition_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        batch_service.cancel_batch(db, batch_id)
        return batch_service.get_batch_progress(db, batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc
