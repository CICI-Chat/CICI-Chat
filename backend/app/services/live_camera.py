"""摄像头采集封装：开/关/读单帧，线程安全的 read。

支持 USB 摄像头（device_index=数字）和网络流（device_index=URL 字符串）。
网络流（如 ESP32-CAM）易掉线，read() 内置自动重连。
"""

import time
from threading import Lock
from typing import Optional

import cv2
import numpy as np


class CameraUnavailableError(RuntimeError):
    """摄像头打不开（被占用、未连接、驱动异常）。"""


class LiveCamera:
    def __init__(self, device_index: int | str = 0, reconnect_attempts: int = 1) -> None:
        self.device_index = device_index
        self.reconnect_attempts = reconnect_attempts
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = Lock()

    def _open_locked(self) -> None:
        """内部：在已持有锁的情况下打开摄像头。"""
        if self._cap is not None:
            self._cap.release()
        cap = cv2.VideoCapture(self.device_index)
        if not cap.isOpened():
            cap.release()
            raise CameraUnavailableError(
                f"无法打开摄像头 {self.device_index}（被占用或未连接）"
            )
        self._cap = cap

    def open(self) -> None:
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return
            self._open_locked()

    def read(self) -> np.ndarray:
        with self._lock:
            if self._cap is None:
                raise CameraUnavailableError("摄像头未打开，请先调用 open()")

            ok, frame = self._cap.read()
            if ok and frame is not None:
                return frame

            # 读帧失败：网络流可能临时掉线，自动重连重试
            for attempt in range(self.reconnect_attempts):
                time.sleep(0.5)
                try:
                    self._open_locked()
                except CameraUnavailableError:
                    continue
                ok, frame = self._cap.read()
                if ok and frame is not None:
                    return frame

            raise CameraUnavailableError(
                f"摄像头读帧失败，重连 {self.reconnect_attempts} 次仍无画面"
            )

    def close(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
