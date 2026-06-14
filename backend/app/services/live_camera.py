"""摄像头采集封装：开/关/读单帧，线程安全的 read。"""

from threading import Lock
from typing import Optional

import cv2
import numpy as np


class CameraUnavailableError(RuntimeError):
    """摄像头打不开（被占用、未连接、驱动异常）。"""


class LiveCamera:
    def __init__(self, device_index: int = 0) -> None:
        self.device_index = device_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = Lock()

    def open(self) -> None:
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return
            cap = cv2.VideoCapture(self.device_index)
            if not cap.isOpened():
                cap.release()
                raise CameraUnavailableError(
                    f"无法打开摄像头 device_index={self.device_index}（被占用或未连接）"
                )
            self._cap = cap

    def read(self) -> np.ndarray:
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                raise CameraUnavailableError("摄像头未打开，请先调用 open()")
            ok, frame = self._cap.read()
            if not ok or frame is None:
                raise CameraUnavailableError("摄像头读帧失败（可能已被其他进程接管）")
            return frame

    def close(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
