"""把 LiveCamera + Recognizer + 场景/危险判定串成一条消息流迭代器。

设计要点：
- 节流推理：每 N 帧才调用一次 YOLO，中间帧复用上次结果（CPU 上够用）。
- 摄像头由 pipeline 持有 open/close 生命周期，stop() 后保证释放。
- 所有时间戳用 time.time()（实时流不需要 deterministic）。
"""

import base64
import os
import tempfile
import time
import uuid
from typing import Iterator, Protocol

import cv2

from app.services.annotation import ImageRecognitionInput
from app.services.danger_detector import detect_danger
from app.services.scene_classifier import classify_scene


class _CameraLike(Protocol):
    def open(self) -> None: ...
    def read(self): ...
    def close(self) -> None: ...


class _RecognizerLike(Protocol):
    def recognize(self, image: ImageRecognitionInput): ...


class LivePipeline:
    def __init__(
        self,
        camera: _CameraLike,
        recognizer: _RecognizerLike,
        infer_every_n_frames: int = 5,
        jpeg_quality: int = 80,
    ) -> None:
        self._camera = camera
        self._recognizer = recognizer
        self._infer_every = max(1, infer_every_n_frames)
        self._jpeg_quality = jpeg_quality
        self._stopped = False
        self._frame_idx = 0
        # 上一次推理结果缓存（中间帧复用）
        self._last_objects: list[dict] = []
        self._last_scene: str = "unknown"
        self._last_danger: dict = {"is_danger": False, "labels": []}

    def __iter__(self) -> Iterator[dict]:
        self._camera.open()
        try:
            while not self._stopped:
                frame = self._camera.read()
                self._frame_idx += 1

                if (self._frame_idx - 1) % self._infer_every == 0:
                    self._run_inference(frame)

                ok, jpeg_bytes = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
                )
                if not ok:
                    # 编码失败：跳过这一帧，不阻塞流
                    continue

                yield {
                    "ts": time.time(),
                    "jpeg_base64": base64.b64encode(jpeg_bytes.tobytes()).decode("ascii"),
                    "objects": self._last_objects,
                    "scene": self._last_scene,
                    "danger": self._last_danger,
                }
        finally:
            self._camera.close()

    def _run_inference(self, frame) -> None:
        h, w = frame.shape[:2]
        result = self._recognize_ndarray(frame, w, h)
        self._last_objects = list(result.objects)
        self._last_scene = classify_scene(self._last_objects)
        self._last_danger = detect_danger(self._last_objects)

    def _recognize_ndarray(self, frame, width: int, height: int):
        """为 LivePipeline 设计的 in-memory 推理路径：
        把 ndarray 暂存到 OS 临时目录的随机文件名 → 调 recognizer.recognize → 删除。
        这样 YoloRecognizer 接口（要求 file_path）不变。
        """
        path = os.path.join(tempfile.gettempdir(), f"picmind_live_{uuid.uuid4().hex}.jpg")
        try:
            cv2.imwrite(path, frame)
            return self._recognizer.recognize(
                ImageRecognitionInput(
                    image_id="live",
                    file_path=path,
                    width=width,
                    height=height,
                    format="jpg",
                )
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def stop(self) -> None:
        self._stopped = True
        # 幂等关闭：生成器的 finally 也会关一次，但 close() 必须幂等以应对
        # 调用方 stop() 后没继续推进迭代器的情况。
        self._camera.close()
