# H2 进阶：卡尔曼滤波 + 一键标定

**目标：** 让距离估算更精确（焦距标定）、输出更平滑（卡尔曼滤波）、显示速度（靠近/远离）。

---

## 功能一：一键焦距标定

**原理：** 用户站到已知距离（默认 2 米），系统利用当前 active target 的 bbox 高度反算真实焦距。

```
f_px = (真实距离 × h_px) / 已知物体高度
h_px = h_norm × frame_height
```

**前端交互：** 实时预览页面新增「标定」按钮 + 距离输入框（默认 2.0 米）。点击后发送 WebSocket 标定消息。完成后显示"焦距已校准：680px"。

**后端协议：** 复用现有 WebSocket 连接。
- 前端发送（JSON 文本，与正常帧同级但带 type）：

```json
{"type": "calibrate", "distance_m": 2.0}
```

- 后端在当前帧的 active target 上计算焦距，保存到 `data/calibration.json`，回复：

```json
{"type": "calibrated", "focal_length_px": 680}
```

- 后端不会卡住流——标定在当前帧立即完成，后续帧继续使用新焦距。

**焦距持久化：** `data/calibration.json` 保存格式：

```json
{"focal_length_px": 680, "calibrated_at": "2026-06-25T10:00:00"}
```

未标定时使用默认值 700。存在 `data/calibration.json` 时优先使用其值。

**文件改动：**
- 新建 `backend/app/services/calibration.py`：加载/保存焦距
- 修改 `backend/app/services/distance_estimator.py`：焦距改为动态加载
- 修改 `backend/app/services/live_pipeline.py`：`_run_inference` 中处理标定消息
- 修改 `backend/app/api/live.py`：WebSocket 接收标定消息并调用标定
- 修改 `frontend/src/pages/LivePreview.tsx`：标定按钮 + 距离输入 + 状态反馈

---

## 功能二：卡尔曼滤波平滑距离与速度

**滤波器设计：** 1D 卡尔曼滤波器，每个 track_id 独立实例。

**状态向量：**
```
x = [distance, velocity]^T
  distance: 目标距摄像头的距离（米）
  velocity: 目标移动速度（米/帧，正=靠近，负=远离）
```

**预测模型：**
```
distance' = distance + velocity × dt  
velocity' = velocity  

P' = F × P × F^T + Q
   = [[1, dt], [0, 1]] × P × [[1, 0], [dt, 1]] + Q
```

**观测更新：**
```
z = 原始距离观测值（从 estimate_distance 获得）
y = z - distance               （残差）
K = P × H^T × (H × P × H^T + R)^-1
x += K × y
P = (I - K × H) × P
```

**参数默认值：**
- `Q_diag = [0.1, 0.01]`（过程噪声）
- `R = 1.0`（观测噪声，焦距越准这个值应该越小）
- `dt = 0.2`（6 推理帧/秒 ≈ 0.166，取 0.2 为偏保守估计）

**生命周期：** 卡尔曼滤波器挂载在 `track_id` 上。目标消失后保留一段时间（同 H3 的 `_max_lost_inferences` 机制）。

**消息输出：**
```json
{
  "track_id": 1,
  "distance_m": 5.2,
  "velocity_ms": 1.2,
  "is_active_target": true
}
```

前端 bbox 标签：
```
#1 人 91% 5.2m ↑1.2m/s
```

速度方向用上下箭头表示，`↑` = 靠近（正速度），`↓` = 远离（负速度）。速度绝对值小于 0.2 m/s 时不显示，避免零值闪烁。

**文件改动：**
- 新建 `backend/app/services/kalman_filter.py`：1D 卡尔曼实现
- 修改 `backend/app/services/live_pipeline.py`：集成卡尔曼器
- 新建 `backend/tests/test_kalman_filter.py`：卡尔曼测试
- 修改 `frontend/src/components/BboxOverlay.tsx`：显示速度箭头

---

## 数据流总结

```
摄像头帧
  → YOLO tracker (track_id, bbox)
  → estimate_distance(h_px) → 原始距离观测值
  → 卡尔曼滤波（per track_id）→ 平滑距离 + 速度
  → objects[]: {distance_m, velocity_ms}
  → WebSocket 消息
  → LivePreview.tsx（标定按钮 + 距离输入）
  → BboxOverlay（#1 人 91% 5.2m ↑1.2m/s）
                ↑ 标定命令
                ↓ 标定结果
  → calibration.py（保存/加载焦距）
  → distance_estimator.py（使用标定后的焦距）
```

## 测试

1. **test_kalman_filter.py**
   - 恒定距离下输出收敛到观测值
   - 恒定速度下的跟踪能力
   - 空观测不崩溃
   - 重置后状态清零

2. **test_calibration.py（若有）**
   - 焦距保存和加载正确
   - 不存在时返回默认值

3. **test_live_pipeline.py**
   - tracker 路径下 objects 含 `velocity_ms`（float）
