# YOLO11n 集成手工验证清单

## 前置条件

1. `backend/.env` 中设置：
   ```
   RECOGNITION_PROVIDER=yolo
   YOLO_MODEL_PATH=D:/my vibe coding/models/yolo/yolo11n.pt
   YOLO_CONFIDENCE_THRESHOLD=0.25
   ```
2. `ultralytics` 依赖已安装（`cd backend && uv sync`）。
3. 后端已重启。

## 验证步骤

- [ ] `GET /api/settings` 返回 `"provider": "yolo"`。
- [ ] 对一张包含人和车的图片调用 `POST /api/images/{id}/recognize`，响应内 `annotation.objects` 非空。
- [ ] 图片详情页能看到「检测到的物体」分区，包含 `人（person）· 置信度 xx%`。
- [ ] 图片详情页 tags 中包含 `人`、`汽车` 等中文物体名。
- [ ] 图库搜索框输入 `人` 能命中该图片。
- [ ] 图库搜索框输入 `汽车` 能命中该图片。
- [ ] 方向标签和主色标签仍存在。
- [ ] 创建一个批量识别任务覆盖多张图片，全部完成后多张 annotation 的 objects 非空。
- [ ] 把 `RECOGNITION_PROVIDER` 改回 `mock` 并重启后端，应用启动正常，settings 显示 `"provider": "mock"`。
- [ ] 把 `YOLO_MODEL_PATH` 改为不存在的路径并设 `RECOGNITION_PROVIDER=yolo`，重启后端应该报 `YoloModelMissingError` 并打印切换提示，不应静默崩溃。

## 验证日期

YYYY-MM-DD：

## 备注
