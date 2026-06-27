# PicMind 项目交接手册

> **版本同步说明：** 如果在另一台电脑上继续开发，先 `git pull` 拉取最新代码，**然后启动一个新的 Claude Code 会话**（关闭当前 VS Code 终端再开一个新的）。Claude 会在新会话启动时自动读取本文件，确保两台电脑理解一致。

---

## ✅ 已完成功能总览

| 功能 | 状态 | 说明 |
|------|------|------|
| 基础图库管理 | ✅ | 扫描/索引/搜索/标签/颜色分析 |
| YOLO 静态识别 | ✅ | YOLOv8/yolo11n COCO 80 类 |
| Bbox 边界框渲染 | ✅ | BboxOverlay 组件 |
| 场景分类 | ✅ | 室内/室外，优先级制（室内>室外>默认室外） |
| 危险目标检测 | ✅ | 人/车/动物 16 类 |
| WebSocket 实时流 | ✅ | /api/live/feed，单客户端锁 |
| LiveCamera | ✅ | cv2.VideoCapture 封装 |
| LivePipeline | ✅ | 采集→YOLO(每5帧)→场景→危险→编码 |
| H4 中心点偏移 | ✅ | 十字准星+目标黄点+偏移箭头+dx/dy 数值 |
| H3 多目标追踪 | ✅ | YoloTracker+Ultralytics track，track_id，active_track 锁定 |
| H2 距离估算 | ✅ | 小孔成像 D=(H_real×f_px)/h_px |
| 卡尔曼滤波 | ✅ | 1D 位置-速度滤波，per track_id 平滑 |
| 一键焦距标定 | ✅ | 前端按钮+距离输入→WebSocket→保存 calibration.json |
| 速度显示 | ✅ | bbox 标签 ↑1.2m/s ↓0.5m/s |
| 飞控桥接 | ✅ | BetaflightBridge(COM3) MSP 协议，自动连接/断开 |

## 🚀 启动方式

```bash
# 终端1 - 后端
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 终端2 - 前端
cd frontend && npm run dev -- --host 127.0.0.1

# 浏览器
http://localhost:5173 → 导航「实时预览」
```

## ⚙️ 配置
- 后端 `.env`：`RECOGNITION_PROVIDER=yolo`，`YOLO_MODEL_PATH=D:/my vibe coding/models/yolo/yolo11n.pt`
- 飞控串口：`COM3 @ 115200`（Betaflight）

## 🏗️ 架构要点

```
live.py (WebSocket)
  └─ LivePipeline
       ├─ camera (LiveCamera / ESP32 流)
       ├─ recognizer (YoloRecognizer - 静态识别)
       ├─ tracker (YoloTracker - 实时追踪)
       ├─ KalmanFilter1D registry (per track_id)
       ├─ calibration (焦距持久化)
       └─ flight_bridge (BetaflightBridge MSP→COM3)
```

## 📁 关键文件

| 文件 | 职责 |
|------|------|
| backend/app/api/live.py | WebSocket 端点，双工通信(接收标定+发送帧) |
| backend/app/services/live_pipeline.py | 实时推理核心，含 active track/距离/飞控 |
| backend/app/services/yolo_tracker.py | Ultralytics track 封装 |
| backend/app/services/distance_estimator.py | 小孔成像距离估算 |
| backend/app/services/kalman_filter.py | 1D 卡尔曼滤波 |
| backend/app/services/calibration.py | 焦距校准保存/加载 |
| backend/app/services/flight_controller.py | Betaflight MSP 桥接(COM3) |
| backend/app/services/danger_detector.py | 危险目标定义 |
| frontend/src/pages/LivePreview.tsx | 实时预览页面(含标定按钮) |
| frontend/src/components/BboxOverlay.tsx | 边界框渲染(含距离+速度) |
| frontend/src/components/CenterOffsetOverlay.tsx | 中心偏移 overlay |

## 📡 ESP32 摄像头
当前用 `cv2.VideoCapture(0)`（USB）。如果改用 ESP32-CAM，把 live.py 中改为：
```python
camera = LiveCamera(device_index="http://192.168.x.x:81/stream")
```

## 📋 后续方向（备选清单，选一个做）
- 飞控实际硬件联调（Betaflight 已配好 COM3）
- GPU 加速（见 docs/CODEMAPS/yolo-gpu-migration.md）
- 多目标手动选择锁定（前端点击选择某个 target 追踪）
- ESP32-CAM WiFi 图传接入

## 📚 更多文档
- `docs/superpowers/specs/` - 设计规格
- `docs/superpowers/plans/` - 实现计划
- `docs/CODEMAPS/` - 验证清单
- `docs/ARTICLES/` - 项目总结文章
