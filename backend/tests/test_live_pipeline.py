from typing import Iterator

import numpy as np
import pytest

from app.services.annotation import ImageRecognitionInput, RecognitionResult
from app.services.live_pipeline import LivePipeline


class FakeCamera:
    """每次 read 返回固定形状的纯色帧。计数 read 次数。"""

    def __init__(self) -> None:
        self.read_count = 0
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> np.ndarray:
        self.read_count += 1
        # 64x48 BGR 纯红
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[:, :, 2] = 255
        return frame

    def close(self) -> None:
        self.closed = True


class FakeRecognizer:
    """每次 recognize 返回一个固定的 person 检测结果。计数推理次数。"""

    def __init__(self) -> None:
        self.call_count = 0

    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        self.call_count += 1
        return RecognitionResult(
            caption="本地图片",
            tags=["人", "本地图片", "landscape"],
            objects=[{
                "label": "person", "name": "人", "confidence": 0.91,
                "x": 0.3, "y": 0.2, "w": 0.2, "h": 0.6,
            }],
            model_used="yolo11n",
        )


def _take(it: Iterator[dict], n: int) -> list[dict]:
    return [next(it) for _ in range(n)]


def test_pipeline_yields_messages_with_required_fields():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert set(msg.keys()) == {"ts", "jpeg_base64", "objects", "scene", "danger"}
    assert isinstance(msg["ts"], float)
    assert isinstance(msg["jpeg_base64"], str) and len(msg["jpeg_base64"]) > 0
    assert msg["objects"][0]["label"] == "person"
    assert msg["scene"] == "outdoor"  # 单个 person 不属于 indoor/outdoor 词表，默认室外
    assert msg["danger"] == {"is_danger": True, "labels": ["person"]}
    pipeline.stop()


def test_pipeline_throttles_inference_every_n_frames():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msgs = _take(iter(pipeline), 12)

    # 12 帧、每 5 帧推理一次 → 推理调用 ⌈12/5⌉ = 3 次
    assert rec.call_count == 3
    # 12 帧都应当 yield 出消息（中间帧复用上一次推理结果）
    assert len(msgs) == 12
    pipeline.stop()


def test_pipeline_open_close_camera_lifecycle():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    it = iter(pipeline)
    next(it)
    assert cam.opened is True
    assert cam.closed is False

    pipeline.stop()
    assert cam.closed is True
