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


class FakeTracker:
    """每次 track_frame 返回预设 objects，并记录调用次数。"""

    def __init__(self, frames: list[list[dict]]) -> None:
        self.frames = frames
        self.call_count = 0

    def track_frame(self, frame) -> list[dict]:
        idx = min(self.call_count, len(self.frames) - 1)
        self.call_count += 1
        return self.frames[idx]


def _take(it: Iterator[dict], n: int) -> list[dict]:
    return [next(it) for _ in range(n)]


def test_pipeline_yields_messages_with_required_fields():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    # 基础字段必须存在
    assert {"ts", "jpeg_base64", "objects", "scene", "danger", "frame", "target_offset"}.issubset(msg.keys())
    assert isinstance(msg["ts"], float)
    assert isinstance(msg["jpeg_base64"], str) and len(msg["jpeg_base64"]) > 0
    assert msg["objects"][0]["label"] == "person"
    assert msg["scene"] == "outdoor"  # 单个 person 不属于 indoor/outdoor 词表，默认室外
    assert msg["danger"] == {"is_danger": True, "labels": ["person"]}

    # H4: 验证 frame 信息
    assert msg["frame"] == {"width": 64, "height": 48, "center": {"x": 0.5, "y": 0.5}}

    # H4: 验证 target_offset 计算正确
    # Fake bbox: x=0.3, y=0.2, w=0.2, h=0.6
    # center_x = 0.3 + 0.2/2 = 0.4
    # center_y = 0.2 + 0.6/2 = 0.5
    # dx = 0.4 - 0.5 = -0.1
    # dy = 0.5 - 0.5 = 0
    # dx_px = -0.1 * 64 = -6.4 → round 后 -6
    # dy_px = 0 * 48 = 0
    assert msg["target_offset"] is not None
    assert msg["target_offset"]["target_index"] == 0
    assert msg["target_offset"]["label"] == "person"
    assert msg["target_offset"]["name"] == "人"
    assert msg["target_offset"]["confidence"] == 0.91
    assert msg["target_offset"]["target_center"] == {"x": 0.4, "y": 0.5}
    assert msg["target_offset"]["dx"] == -0.1
    assert msg["target_offset"]["dy"] == 0.0
    assert msg["target_offset"]["dx_px"] == -6
    assert msg["target_offset"]["dy_px"] == 0

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


def test_target_offset_is_null_when_no_objects():
    """H4: 没有检测到物体时 target_offset 应为 None。"""
    class EmptyRecognizer:
        def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
            return RecognitionResult(
                caption="空",
                tags=[],
                objects=[],
                model_used="yolo11n",
            )

    cam = FakeCamera()
    rec = EmptyRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert msg["target_offset"] is None
    assert msg["frame"] == {"width": 64, "height": 48, "center": {"x": 0.5, "y": 0.5}}
    pipeline.stop()


def test_target_offset_is_null_when_only_non_danger_objects():
    """H4: 只有非危险目标（如椅子、桌子）时，target_offset 也应为 None。"""
    class ChairOnlyRecognizer:
        def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
            return RecognitionResult(
                caption="只有椅子",
                tags=["chair"],
                objects=[{
                    "label": "chair", "name": "椅子", "confidence": 0.85,
                    "x": 0.3, "y": 0.3, "w": 0.2, "h": 0.3,
                }],
                model_used="yolo11n",
            )

    cam = FakeCamera()
    rec = ChairOnlyRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert msg["target_offset"] is None  # 椅子不是危险目标，不追踪
    assert msg["objects"][0]["label"] == "chair"  # 确实检测到了椅子
    pipeline.stop()


def test_pipeline_uses_tracker_and_emits_active_track_id():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([[
        {
            "track_id": 7, "label": "person", "name": "人", "confidence": 0.91,
            "x": 0.3, "y": 0.2, "w": 0.2, "h": 0.6,
        }
    ]])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert tracker.call_count == 1
    assert rec.call_count == 0
    assert msg["active_track_id"] == 7
    assert msg["objects"][0]["is_active_target"] is True
    assert msg["target_offset"]["track_id"] == 7
    pipeline.stop()


def test_active_track_does_not_switch_when_new_target_has_higher_confidence():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([
        [{
            "track_id": 1, "label": "person", "name": "人", "confidence": 0.80,
            "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
        [
            {
                "track_id": 1, "label": "person", "name": "人", "confidence": 0.70,
                "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
            },
            {
                "track_id": 2, "label": "person", "name": "人", "confidence": 0.99,
                "x": 0.6, "y": 0.2, "w": 0.2, "h": 0.6,
            },
        ],
    ])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=1)

    msgs = _take(iter(pipeline), 2)

    assert msgs[0]["active_track_id"] == 1
    assert msgs[1]["active_track_id"] == 1
    assert msgs[1]["target_offset"]["track_id"] == 1
    pipeline.stop()


def test_active_track_reacquires_after_lost_threshold():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([
        [{
            "track_id": 1, "label": "person", "name": "人", "confidence": 0.90,
            "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
        [],
        [],
        [{
            "track_id": 2, "label": "person", "name": "人", "confidence": 0.95,
            "x": 0.6, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
    ])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=1)
    pipeline._max_lost_inferences = 2

    msgs = _take(iter(pipeline), 4)

    assert msgs[0]["active_track_id"] == 1
    assert msgs[1]["active_track_id"] == 1
    assert msgs[1]["target_offset"] is None
    assert msgs[2]["active_track_id"] == 1
    assert msgs[2]["target_offset"] is None
    assert msgs[3]["active_track_id"] == 2
    assert msgs[3]["target_offset"]["track_id"] == 2
    pipeline.stop()
