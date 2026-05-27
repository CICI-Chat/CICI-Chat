import re

import pytest

from app.services.batch_recognition import (
    BatchNotFoundError,
    BatchRecognitionService,
    EmptyBatchError,
)


class FakeRecognitionService:
    def __init__(self, failing_ids: set[str] | None = None) -> None:
        self.failing_ids = failing_ids or set()
        self.calls: list[tuple[str, object]] = []

    def recognize_image(self, image_id: str, db: object) -> object:
        self.calls.append((image_id, db))
        if image_id in self.failing_ids:
            raise RuntimeError(f"recognition failed for {image_id}")
        return object()


class FakeDb:
    def __init__(self) -> None:
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1


def test_create_batch_initializes_pending_job_with_uuid_like_id():
    service = BatchRecognitionService()
    image_ids = ["image-1", "image-2"]

    job = service.create_batch(image_ids)

    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        job.batch_id,
    )
    assert job.image_ids == image_ids
    assert job.total == 2
    assert job.completed == 0
    assert job.failed == 0
    assert job.running == 0
    assert job.pending == 2
    assert job.status == "pending"


def test_create_batch_raises_for_empty_image_ids():
    service = BatchRecognitionService()

    with pytest.raises(EmptyBatchError):
        service.create_batch([])


def test_get_batch_raises_for_missing_batch_id():
    service = BatchRecognitionService()

    with pytest.raises(BatchNotFoundError, match="missing-batch"):
        service.get_batch("missing-batch")


def test_run_batch_calls_recognition_for_each_image_and_completes(db_session):
    recognition_service = FakeRecognitionService()
    service = BatchRecognitionService(recognition_service)
    job = service.create_batch(["image-1", "image-2", "image-3"])

    result = service.run_batch(job.batch_id, db_session)

    assert result is job
    assert recognition_service.calls == [
        ("image-1", db_session),
        ("image-2", db_session),
        ("image-3", db_session),
    ]
    assert job.completed == 3
    assert job.failed == 0
    assert job.running == 0
    assert job.pending == 0
    assert job.status == "completed"


def test_run_batch_continues_after_recognition_failure_and_marks_failed(db_session):
    recognition_service = FakeRecognitionService(failing_ids={"image-2"})
    service = BatchRecognitionService(recognition_service)
    job = service.create_batch(["image-1", "image-2", "image-3"])

    result = service.run_batch(job.batch_id, db_session)

    assert result is job
    assert recognition_service.calls == [
        ("image-1", db_session),
        ("image-2", db_session),
        ("image-3", db_session),
    ]
    assert job.completed == 2
    assert job.failed == 1
    assert job.running == 0
    assert job.pending == 0
    assert job.status == "failed"


def test_run_batch_rolls_back_after_recognition_failure():
    recognition_service = FakeRecognitionService(failing_ids={"image-2"})
    service = BatchRecognitionService(recognition_service)
    db = FakeDb()
    job = service.create_batch(["image-1", "image-2", "image-3"])

    service.run_batch(job.batch_id, db)

    assert db.rollbacks == 1
    assert recognition_service.calls == [
        ("image-1", db),
        ("image-2", db),
        ("image-3", db),
    ]
    assert job.completed == 2
    assert job.failed == 1
    assert job.pending == 0
    assert job.status == "failed"


def test_run_batch_returns_existing_non_pending_job_without_rerunning(db_session):
    recognition_service = FakeRecognitionService()
    service = BatchRecognitionService(recognition_service)
    job = service.create_batch(["image-1", "image-2"])

    first_result = service.run_batch(job.batch_id, db_session)
    first_calls = list(recognition_service.calls)
    first_counters = (job.completed, job.failed, job.pending, job.running, job.status)
    second_result = service.run_batch(job.batch_id, db_session)

    assert first_result is job
    assert second_result is job
    assert recognition_service.calls == first_calls
    assert (job.completed, job.failed, job.pending, job.running, job.status) == first_counters


def test_run_batch_raises_for_missing_batch_id(db_session):
    service = BatchRecognitionService()

    with pytest.raises(BatchNotFoundError, match="missing-batch"):
        service.run_batch("missing-batch", db_session)
