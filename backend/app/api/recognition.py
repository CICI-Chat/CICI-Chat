from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.images import to_image_detail
from app.database import get_db
from app.schemas import ImageDetail, RecognitionBatchCreate, RecognitionBatchResponse
from app.services.batch_recognition import BatchJob, BatchNotFoundError, BatchRecognitionService, EmptyBatchError
from app.services.recognition import ImageFileMissingError, ImageNotFoundError, RecognitionService

router = APIRouter(tags=["recognition"])
recognition_service = RecognitionService()


def get_batch_recognition_service(request: Request) -> BatchRecognitionService:
    return request.app.state.batch_recognition_service



def to_batch_response(job: BatchJob) -> RecognitionBatchResponse:
    return RecognitionBatchResponse(
        batch_id=job.batch_id,
        total=job.total,
        completed=job.completed,
        failed=job.failed,
        pending=job.pending,
        running=job.running,
        status=job.status,
    )


@router.post("/api/images/{image_id}/recognize", response_model=ImageDetail)
def recognize_image(image_id: str, db: Session = Depends(get_db)) -> ImageDetail:
    try:
        image = recognition_service.recognize_image(image_id, db)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    except ImageFileMissingError as exc:
        raise HTTPException(status_code=404, detail="Image file not found") from exc
    return to_image_detail(image)


@router.post("/api/recognition/batches", response_model=RecognitionBatchResponse, status_code=status.HTTP_201_CREATED)
def create_recognition_batch(
    payload: RecognitionBatchCreate,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        job = batch_service.create_batch(payload.image_ids)
    except EmptyBatchError as exc:
        raise HTTPException(status_code=400, detail="Batch must include at least one image") from exc

    job = batch_service.run_batch(job.batch_id, db)
    return to_batch_response(job)


@router.get("/api/recognition/batches/{batch_id}", response_model=RecognitionBatchResponse)
def get_recognition_batch(
    batch_id: str,
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchResponse:
    try:
        job = batch_service.get_batch(batch_id)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc
    return to_batch_response(job)
