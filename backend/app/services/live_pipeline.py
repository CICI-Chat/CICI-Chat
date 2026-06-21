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
from app.services.danger_detector import DANGER_LABELS, detect_danger
from app.services.scene_classifier import classify_scene


class _CameraLike(Protocol):
    def open(self) -> None: ...
    def read(self): ...
    def close(self) -> None: ...


class _RecognizerLike(Protocol):
    def recognize(self, image: ImageRecognitionInput): ...


class _TrackerLike(Protocol):
    def track_frame(self, frame) -> list[dict]: ...


class LivePipeline:
    def __init__(
        self,
        camera: _CameraLike,
        recognizer: _RecognizerLike,
        tracker: _TrackerLike | None = None,
        infer_every_n_frames: int = 5,
        jpeg_quality: int = 80,
    ) -> None:
        self._camera = camera
        self._recognizer = recognizer
        self._tracker = tracker
        self._infer_every = max(1, infer_every_n_frames)
        self._jpeg_quality = jpeg_quality
        self._stopped = False
        self._frame_idx = 0
        # 上一次推理结果缓存（中间帧复用）
        self._last_objects: list[dict] = []
        self._last_scene: str = "unknown"
        self._last_danger: dict = {"is_danger": False, "labels": []}
        # H4: 帧信息和目标中心偏移
        self._last_frame: dict | None = None
        self._last_target_offset: dict | None = None
        self._active_track_id: int | None = None
        self._lost_inference_count = 0
        self._max_lost_inferences = 10

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

                # 没有物体时强制 target_offset 为 null（即使是中间帧）
                current_target_offset = self._last_target_offset if self._last_objects else None

                yield {
                    "ts": time.time(),
                    "jpeg_base64": base64.b64encode(jpeg_bytes.tobytes()).decode("ascii"),
                    "objects": self._last_objects,
                    "scene": self._last_scene,
                    "danger": self._last_danger,
                    "frame": self._last_frame,
                    "target_offset": current_target_offset,
                    "active_track_id": self._active_track_id,
                }
        finally:
            self._camera.close()

    def _run_inference(self, frame) -> None:
        h, w = frame.shape[:2]
        if self._tracker is not None:
            self._last_objects = list(self._tracker.track_frame(frame))
        else:
            result = self._recognize_ndarray(frame, w, h)
            self._last_objects = list(result.objects)
        self._last_scene = classify_scene(self._last_objects)
        self._last_danger = detect_danger(self._last_objects)
        # H4: 帧信息
        self._last_frame = {
            "width": w,
            "height": h,
            "center": {"x": 0.5, "y": 0.5},
        }
        self._update_active_track()
        self._mark_active_target()
        # H4: 计算目标中心偏移
        self._last_target_offset = self._compute_target_offset(w, h)

    def _danger_objects_with_track(self) -> list[tuple[int, dict]]:
        return [
            (idx, obj)
            for idx, obj in enumerate(self._last_objects)
            if obj.get("label") in DANGER_LABELS and obj.get("track_id") is not None
        ]

    def _update_active_track(self) -> None:
        if self._tracker is None:
            self._active_track_id = None
            self._lost_inference_count = 0
            return

        candidates = self._danger_objects_with_track()
        visible_ids = {obj.get("track_id") for _, obj in candidates}

        if self._active_track_id in visible_ids:
            self._lost_inference_count = 0
            return

        if self._active_track_id is not None:
            self._lost_inference_count += 1
            if self._lost_inference_count <= self._max_lost_inferences:
                return
            self._active_track_id = None
            self._lost_inference_count = 0

        if not candidates:
            return

        _, target = max(candidates, key=lambda pair: pair[1].get("confidence", 0.0))
        self._active_track_id = target.get("track_id")

    def _mark_active_target(self) -> None:
        if self._tracker is None:
            return

        for obj in self._last_objects:
            obj["is_active_target"] = (
                self._active_track_id is not None
                and obj.get("track_id") == self._active_track_id
            )

    def _compute_target_offset(self, frame_width: int, frame_height: int) -> dict | None:
        """计算主目标相对于画面中心的偏移。

        目标选择策略：
        1. 优先选置信度最高的危险目标
        2. 否则选置信度最高的普通目标
        3. 无目标返回 None
        """
        if not self._last_objects:
            return None

        if self._tracker is None:
            # 只筛选危险目标（人、车、动物）——无人机避障目标
            danger_candidates = [
                (idx, obj)
                for idx, obj in enumerate(self._last_objects)
                if obj.get("label") in DANGER_LABELS
            ]

            # 没有危险目标 → 不追踪（背景物体不算）
            if not danger_candidates:
                return None

            # 在危险目标中选置信度最高的
            target_idx, target = max(
                danger_candidates,
                key=lambda pair: pair[1].get("confidence", 0.0),
            )
        else:
            danger_candidates = self._danger_objects_with_track()

            if self._active_track_id is not None:
                for idx, obj in danger_candidates:
                    if obj.get("track_id") == self._active_track_id:
                        target_idx, target = idx, obj
                        break
                else:
                    return None
            else:
                if not danger_candidates:
                    return None
                target_idx, target = max(
                    danger_candidates,
                    key=lambda pair: pair[1].get("confidence", 0.0),
                )

        x = target.get("x", 0.0)
        y = target.get("y", 0.0)
        bw = target.get("w", 0.0)
        bh = target.get("h", 0.0)

        center_x = x + bw / 2
        center_y = y + bh / 2

        dx = center_x - 0.5
        dy = center_y - 0.5

        return {
            "target_index": target_idx,
            "track_id": target.get("track_id"),
            "label": target.get("label"),
            "name": target.get("name"),
            "confidence": target.get("confidence"),
            "target_center": {
                "x": round(center_x, 4),
                "y": round(center_y, 4),
            },
            "dx": round(dx, 4),
            "dy": round(dy, 4),
            "dx_px": round(dx * frame_width),
            "dy_px": round(dy * frame_height),
        }

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
