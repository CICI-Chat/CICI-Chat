# H2 距离估算设计

**目标：** 利用 bbox 高度 + 已知物体真实尺寸 + 摄像头焦距，实时推算每个目标距摄像头的距离，显示在 bbox 标签上。

**技术：** 小孔成像模型 `D = (H_real × f_px) / h_px`，固定平均值作为 `H_real`，简要标定获取 `f_px`。

## 不在本期范围

- ✅ 不自动标定
- ✅ 不做手机/相机专用标定
- ✅ 不用多种物类回退宽高比
- ✅ 不做前端手动输入物体真实高度

## 原理

```
  真实物体高度 H_real (米)
          │
  ┌───────▼───────┐
  │   pinhole     │
  │  camera model │─── 焦距 f_px (像素)
  │               │
  └───────▲───────┘
          │
  bbox 像素高度 h_px (像素 = h × frame_height)
  
  距离 D = (H_real × f_px) / h_px   (米)
```

## 已知物体高度表

hardcode，后续可扩展为配置文件：

| 标签 | 类别 ID | 平均身高/高度（米） | 来源说明 |
|------|---------|-------------------|----------|
| person | 0 | 1.70 | 中国成年人平均身高 |
| bicycle | 1 | 1.00 | 自行车车座高度 |
| car | 2 | 1.50 | 轿车车身高度 |
| motorcycle | 3 | 1.20 | 摩托车把高度 |
| bus | 5 | 3.50 | 公交车身高度 |
| truck | 7 | 3.00 | 卡车车身高度 |
| dog | 16 | 0.50 | 中型犬肩高 |
| cat | 15 | 0.30 | 家猫体长 |
| 其余 COCO 动物 | — | 0.50 | 通用小型动物回退值 |

非危险目标的物体（椅子、桌子、书等）不估算距离。

## 焦距获取

第一版使用硬编码典型值 `FOCAL_LENGTH_PX = 700`（适配 640×480 分辨率下的典型笔记本摄像头）。

后续加入快速标定命令：`/calibrate --label person --height 1.7 --distance 2.0`，计算 `f_px = (dist × h_px) / H_real` 并保存到 `data/calibration.json`。

## 后端集成

在 `LivePipeline._run_inference()` 末尾新增：

```python
self._add_distances(frame_height)
```

`_add_distances` 遍历 `_last_objects`，对有 `track_id` 的危险目标计算 `distance_m`。公式：

```python
h_px = obj["h"] * frame_height
if h_px == 0: continue
distance_m = (KNOWN_HEIGHTS.get(label) * FOCAL_LENGTH_PX) / h_px
```

输出到 object 字段：

```json
{
  "track_id": 1,
  "label": "person",
  "name": "人",
  "confidence": 0.91,
  "x": 0.3,
  "y": 0.2,
  "w": 0.2,
  "h": 0.6,
  "is_active_target": true,
  "distance_m": 5.2
}
```

## 前端显示

`BboxOverlay.tsx` 标签行从：

```
#1 人 91%
```

变为：

```
#1 人 91% 5.2m
```

若 `distance_m` 存在且为数字，显示 `{distance_m.toFixed(1)}m`。不存在时不改变现有显示。

## 文件改动清单

| 文件 | 改动 |
|------|------|
| 新建 `backend/app/services/distance_estimator.py` | 已知高度表 + 距离计算函数 |
| 修改 `backend/app/services/live_pipeline.py` | 新增 `_add_distances()`；yield 消息含 `distance_m` |
| 修改 `frontend/src/components/BboxOverlay.tsx` | bbox 标签显示 `X.Xm` |
| 新建 `backend/tests/test_distance_estimator.py` | 距离计算纯函数测试 |
| 修改 `backend/tests/test_live_pipeline.py` | 验证 tracker 路径下 `distance_m` 字段 |

## 测试

1. **`test_distance_estimator.py`**
   - 已知高度 + 已知焦距 → 期望距离
   - bbox 高度为 0 → 不计算距离（跳过）
   - 非危险目标（如 chair）→ 不计算距离
   - 不同 label 使用不同已知高度

2. **`test_live_pipeline.py`**
   - tracker 路径下 objects 含 `distance_m` 字段
   - 值类型为 float，范围合理

## 手工验证

1. 对着摄像头前的人，标签显示 `#1 人 91% 1.Xm` 字样
2. 人走近 → 距离数字变小
3. 人走远 → 距离数字变大
4. 人走出画面 → 距离消失
5. 只有椅子/桌子时 → 不显示距离
