"""实时摄像头 WebSocket 端点。

协议：每条消息是一条 JSON 文本，结构见 LivePipeline yield 出的 dict。
单连接互斥：第二个客户端连接时立刻关闭并返回 `ALREADY_RUNNING` 原因。
客户端断开时立即停止 pipeline、释放摄像头。
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.live_camera import CameraUnavailableError, LiveCamera
from app.services.live_pipeline import LivePipeline
from app.services.recognition import build_recognizer
from app.services.yolo_tracker import YoloTracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


@router.websocket("/api/live/feed")
async def live_feed(websocket: WebSocket) -> None:
    lock: asyncio.Lock = websocket.app.state.live_lock
    if lock.locked():
        await websocket.close(code=1008, reason="ALREADY_RUNNING")
        return

    async with lock:
        await websocket.accept()
        camera = LiveCamera(device_index=0)
        settings = get_settings()
        recognizer = build_recognizer(settings)
        tracker = None
        if settings.recognition_provider == "yolo":
            tracker = YoloTracker(
                model_path=settings.yolo_model_path,
                confidence_threshold=settings.yolo_confidence_threshold,
            )
            tracker._ensure_model()
        pipeline = LivePipeline(
            camera=camera,
            recognizer=recognizer,
            tracker=tracker,
            infer_every_n_frames=5,
        )

        iterator = iter(pipeline)
        stream_end = object()

        def _next_or_sentinel() -> object:
            # StopIteration 无法跨线程/Future 传播（会被转换成 RuntimeError），
            # 因此在工作线程内部捕获并返回哨兵值来表示迭代结束。
            try:
                return next(iterator)
            except StopIteration:
                return stream_end

        async def _next_msg() -> object:
            return await asyncio.to_thread(_next_or_sentinel)

        async def recv_loop():
            try:
                while True:
                    text = await websocket.receive_text()
                    data = json.loads(text)
                    if data.get("type") == "calibrate":
                        pipeline.request_calibrate(data["distance_m"])
            except WebSocketDisconnect:
                pass

        recv_task = asyncio.create_task(recv_loop())

        try:
            while True:
                try:
                    msg = await _next_msg()
                except CameraUnavailableError as exc:
                    await websocket.send_json({"type": "error", "reason": str(exc)})
                    break
                if msg is stream_end:
                    break
                await websocket.send_text(json.dumps(msg))
        except WebSocketDisconnect:
            logger.info("live feed: client disconnected")
        finally:
            recv_task.cancel()
            pipeline.stop()
            try:
                await websocket.close()
            except RuntimeError:
                # 已经在断连状态
                pass
