# PicMind YOLO11n 物体识别接入设计规格

## 目标

把 PicMind 现有的本地识别管线从 Mock + 颜色识别升级为「Mock + 颜色 + YOLO 真实物体识别」。

接入 Ultralytics YOLO11n 通用物体检测模型，把识别出的物体写入 `Annotation.objects` 和 `Annotation.tags`，让用户能在图库搜索框直接用中文物体名（例如 `人`、`汽车`、`猫`、`狗`）搜到图片。

本规格只覆盖第一版集成：单一本地模型、CPU 推理、可在设置中关闭、识别结果落库结构稳定。不覆盖 GPU 加速、多模型切换、训练自定义类别。

## 当前完成度

### 已完成

- 本地图片扫描、SQLite 索引、图片元数据持久化。
- 单张识别和批量识别后端 API。
- Mock 识别 Provider：写入基础标签、方向标签、主色标签。
- `Annotation` 已经为 YOLO 预留 `objects` JSON 字段。
- 颜色识别已在 `MockRecognizer` 内部完成。
- 图库搜索通过 `tags` 命中关键词。

### 已知短板

- `objects` 字段当前始终为空列表。
- 用户搜索 `人`、`猫`、`汽车` 等真实物体名找不到对应图片。
- 没有真正的视觉模型在运行，识别管线对用户的实际价值仍依赖文件名和颜色。

## 范围

### 包含

- 新增 `YoloRecognizer` 实现 `Recognizer` 协议，使用 Ultralytics YOLO11n 模型在本地 CPU 上做物体检测。
- 模型路径通过环境变量 `YOLO_MODEL_PATH` 配置，默认使用本机已下载文件 `D:/my vibe coding/models/yolo/yolo11n.pt`。
- 通过环境变量 `RECOGNITION_PROVIDER` 选择 `mock` 或 `yolo`，默认保持 `mock` 以避免直接破坏现有流程。
- 把检测结果以 `{label, name, confidence}` 结构写入 `Annotation.objects`。
- 把检测到的物体中文名追加到 `Annotation.tags`，让搜索栏可以搜到。
- 保留现有方向标签、主色标签、基础标签。
- 提供 COCO 80 类英文 → 中文名映射表，覆盖人、车、动物、家具、电子设备、食物等常见类别。
- 提供置信度阈值（默认 0.25），低于阈值的检测结果不写入。
- 前端设置页展示当前识别 Provider 名称。
- 前端图片详情页展示已识别的物体列表（label / name / confidence）。

### 不包含

- 不下载新的模型，使用用户已经下载到本机的 `yolo11n.pt`。
- 不接入 GPU 推理，不要求 CUDA。
- 不接入多模型选择 UI、模型在线切换、运行时热替换。
- 不接入物体定位框在图片上的可视化绘制。
- 不接入分割（segmentation）、姿态估计、追踪。
- 不修改批量识别的并发模型、队列、调度逻辑，只复用现有 `BatchRecognitionService`。
- 不实现自定义训练集、再训练流程。
- 不实现「按物体筛选」高级筛选器，搜索仍走现有 tags 模糊匹配。
- 不修改现有 `MockRecognizer`、`ColorAnalysis`、`Annotation` schema。

## 架构

新增一个识别 Provider 单元，作为现有 `Recognizer` 协议的另一个实现，按配置注入 `RecognitionService` 和 `BatchRecognitionService`。

```
RecognitionService / BatchRecognitionService
    │
    └── Recognizer (Protocol)
            ├── MockRecognizer   (现有，保留)
            └── YoloRecognizer   (新增)
                    └── ultralytics.YOLO(model_path)
```

`Recognizer` 协议保持不变。

## 后端设计

### 新增文件

#### `backend/app/services/yolo_recognizer.py`

职责：

1. 在首次调用时按配置路径加载 YOLO11n 模型。
2. 对单张图片运行推理。
3. 把模型原始输出（英文 label + confidence + box）转换为 `RecognitionResult.objects`。
4. 把每个检测物体的中文名追加到 `tags`。
5. 保留方向标签和基础标签。
6. 处理模型未安装、模型文件缺失、图片无法打开等错误。

主要类型：

- `YoloRecognizer`：实现 `Recognizer` 协议。
- `YoloModelMissingError`：模型文件不存在时抛出。
- `YoloRuntimeError`：模型推理过程中失败时抛出。

模型加载策略：

- 第一次 `recognize()` 时再加载模型（懒加载），避免 FastAPI 启动时阻塞数秒。
- 模型实例缓存在 `YoloRecognizer` 内部属性，进程生命周期内复用。
- 多线程环境下，第一次加载使用锁保证只初始化一次。

#### `backend/app/services/yolo_label_map.py`

职责：

- 提供 COCO 80 类英文 → 中文名静态字典 `COCO_LABEL_TO_CHINESE_NAME`。
- 提供 `chinese_name_for_label(label: str) -> str` 函数。未命中时返回原英文标签作为 fallback，保证不丢数据。

示例条目：

```
person      → 人
bicycle     → 自行车
car         → 汽车
motorcycle  → 摩托车
bus         → 公交车
truck       → 卡车
cat         → 猫
dog         → 狗
horse       → 马
backpack    → 背包
umbrella    → 雨伞
bottle      → 瓶子
cup         → 杯子
chair       → 椅子
couch       → 沙发
bed         → 床
laptop      → 笔记本电脑
cell phone  → 手机
book        → 书
clock       → 时钟
```

完整映射表覆盖 COCO 80 类。

### 配置变更

#### `backend/app/config.py`

新增字段：

- `recognition_provider: str = "mock"`，alias `RECOGNITION_PROVIDER`。允许值 `mock`、`yolo`。
- `yolo_model_path: Path`，alias `YOLO_MODEL_PATH`。默认值 `Path("D:/my vibe coding/models/yolo/yolo11n.pt")`。
- `yolo_confidence_threshold: float = 0.25`，alias `YOLO_CONFIDENCE_THRESHOLD`。

不在 `.env.example` 中写入用户本机绝对路径，只在 spec 和 `README` 中说明默认路径，鼓励用户用相对路径或 `.env.local` 覆盖。

#### Provider 选择

新增工厂函数 `build_recognizer(settings: Settings) -> Recognizer`：

- `settings.recognition_provider == "yolo"` 时返回 `YoloRecognizer(model_path=..., confidence_threshold=...)`。
- 否则返回 `MockRecognizer()`。
- 未来如果加入 `RECOGNITION_PROVIDER=cloud` 等，可以在此扩展。

`RecognitionService` 不直接读 settings，仍接受注入。`main.py` 在创建 `app.state.batch_recognition_service` 时调用 `build_recognizer(get_settings())` 并通过 `RecognitionService(recognizer=...)` 注入。

`backend/app/api/recognition.py` 中模块级 `recognition_service = RecognitionService()` 改为按 settings 构造一次：`recognition_service = RecognitionService(recognizer=build_recognizer(get_settings()))`。

### `RecognitionResult` 输出

`YoloRecognizer` 返回的 `RecognitionResult`：

- `caption`：固定字符串 `本地图片`（识别已经发生，不再使用 `待分析的本地图片` 字面值；与现有 Mock 行为保留差异，让用户能从 caption 区分 provider）。
- `tags`：
  - `本地图片`
  - 方向标签（landscape / portrait / square），逻辑与 Mock 完全一致。
  - 主色标签（沿用现有 `detect_dominant_color_label`）。
  - 每个高于阈值的检测物体的中文名（去重后追加）。
- `objects`：列表，每个元素：
  ```json
  {
    "label": "person",
    "name": "人",
    "confidence": 0.91
  }
  ```
  列表按 `confidence` 倒序，最多保留前 20 项以避免巨型 JSON。
- `model_used`：`yolo11n`。

### 依赖

新增 Python 依赖：

- `ultralytics>=8.3,<9.0`

注意：

- `ultralytics` 会传递依赖 `torch`、`torchvision`，安装体积较大，但不下载模型权重（权重由用户提供本地路径）。
- 安装失败或运行环境缺包时，`build_recognizer` 在 `RECOGNITION_PROVIDER=yolo` 下应给出明确错误，并允许通过把 `RECOGNITION_PROVIDER` 改回 `mock` 立即恢复。

### 错误处理

| 场景 | 行为 |
|------|------|
| `RECOGNITION_PROVIDER=yolo` 且 `yolo_model_path` 不存在 | `build_recognizer` 抛 `YoloModelMissingError`，FastAPI 启动失败并打印明确错误（包含路径和切回 mock 的提示） |
| `ultralytics` 未安装 | `build_recognizer` 抛带提示的 `ImportError` |
| 图片文件不存在 | 沿用现有 `ImageFileMissingError` |
| 图片可读但模型推理异常（例如图片损坏触发底层错误） | `YoloRecognizer.recognize` 抛 `YoloRuntimeError`，单张识别 API 返回 500 / 批量识别将该项标记为失败，不污染其他图片 |
| 模型加载阶段崩溃 | 沿用 `YoloRuntimeError`，下次调用允许重试，不锁死进程 |

## 前端设计

### 设置页（最小改动）

设置页（已存在）新增一个只读项：`当前识别 Provider`，展示后端返回的 `recognition_provider`（`mock` 或 `yolo`）。

后端 `GET /api/settings` 在现有响应里追加：

```json
{
  "recognition_provider": "yolo"
}
```

不在前端提供 Provider 切换控件，第一版要求用户改 `.env` 后重启后端。

### 图片详情页（最小改动）

图片详情页新增「检测到的物体」分区：

- 如果 `objects` 为空，显示「未检测到物体」。
- 否则以列表形式展示：`中文名（英文 label） · 置信度 92%`。

不绘制 bounding box，不做 hover 高亮。

### 图库页

图库页不新增控件。用户在搜索栏输入 `人`、`猫`、`汽车` 等中文物体名时，由现有 tags 模糊匹配命中。

## 数据迁移

不需要数据库 schema 变更：

- `Annotation.objects` 已经存在，类型为 JSON 字符串。
- `Annotation.tags` 已经存在。

历史已识别图片仍保留旧 Mock 结果。需要用户主动触发「重新识别」或新一轮批量识别后，旧记录才会被新 YOLO 结果覆盖。

## 配置加载与文件位置

模型默认路径为本机绝对路径 `D:/my vibe coding/models/yolo/yolo11n.pt`。

- `.env` 不入库，由用户在本地写入。
- `.env.example` 仅写示例占位值，不写真实本机路径。
- 文档（README 或本规格附录）说明模型来源和下载链接，便于其他机器复现。

## 测试策略

### 后端单元测试

- `test_yolo_label_map.py`
  - `chinese_name_for_label("person")` 返回 `人`。
  - `chinese_name_for_label("unknown_label")` 返回 `unknown_label`（fallback）。

- `test_yolo_recognizer_unit.py`（使用 fake / monkeypatch 替换底层模型，不依赖真实权重和 torch）
  - 给定 fake 检测输出 `[{label: "person", conf: 0.91}, {label: "car", conf: 0.84}]`，`objects` 字段顺序按 confidence 倒序。
  - 低于阈值的检测结果被丢弃。
  - 重复 label 在 `tags` 中只出现一次。
  - `model_used == "yolo11n"`。
  - 保留 `本地图片` 和方向标签。
  - 主色标签仍存在（当 Pillow 能识别图片时）。

- `test_recognizer_factory.py`
  - `build_recognizer(settings(provider="mock"))` 返回 `MockRecognizer`。
  - `build_recognizer(settings(provider="yolo", model_path=non_existent))` 抛 `YoloModelMissingError`。
  - `build_recognizer(settings(provider="yolo", model_path=existing_tmp_file))`，通过 monkeypatch 阻止真正加载模型，验证返回 `YoloRecognizer` 实例且未触发推理。

### 后端集成测试

- `test_api.py`
  - `/api/settings` 响应包含 `recognition_provider` 字段。
  - 注入 fake `YoloRecognizer` 的 `RecognitionService`，对一张测试图片调用 `POST /api/images/{id}/recognize`，响应包含非空 `objects`，且 `Annotation.tags` 包含中文物体名。
  - 注入 fake `YoloRecognizer` 的 `BatchRecognitionService`，批量识别后 `Annotation.objects` 数量 > 0。

### 前端测试

- 现有 Vitest 套件继续通过。
- 新增最小测试：图片详情页在 `objects` 非空时渲染中文物体名和置信度；在 `objects` 为空时渲染「未检测到物体」。

### 手工验证（Phase 3）

- 在 `.env` 中设置 `RECOGNITION_PROVIDER=yolo` 和 `YOLO_MODEL_PATH=D:/my vibe coding/models/yolo/yolo11n.pt`。
- 重启后端。
- 对一张包含人和车的本地图片触发单张识别。
- 在图片详情页看到 `人`、`汽车` 等中文物体。
- 在图库搜索栏搜 `人` 能命中该图片。
- 把 `RECOGNITION_PROVIDER` 改回 `mock` 重启后端，确认应用仍正常启动且现有 Mock 流程未被破坏。

## 实施分期

为控制每次改动幅度，本规格落地分三个阶段实现：

### Phase 1：后端 YOLO Provider（核心）

- 新增 `yolo_label_map.py`、`yolo_recognizer.py`。
- 新增配置项 `RECOGNITION_PROVIDER`、`YOLO_MODEL_PATH`、`YOLO_CONFIDENCE_THRESHOLD`。
- 新增 `build_recognizer` 工厂并接入 `RecognitionService`、`BatchRecognitionService`。
- 新增对应单元测试（使用 fake 模型替换）。
- 不修改前端。
- 默认 `RECOGNITION_PROVIDER=mock`，不影响现有用户。

### Phase 2：前端最小展示

- 设置页只读展示 `recognition_provider`。
- 图片详情页展示 `objects` 列表。
- 后端 `/api/settings` 追加 `recognition_provider` 字段。
- 增加最小前端测试。

### Phase 3：真实模型手工验证

- 用户在本机设置 `.env`，使用真实 `yolo11n.pt` 推理。
- 跑过手工验证清单。
- 把验证结果记入项目验证文档（如 `docs/CODEMAPS/yolo-integration-verification.md`，可选）。

每个阶段单独成 PR / commit 组，便于回滚。

## 安全与隐私

- 模型完全在本机推理，不上传图片。
- 不引入网络调用、不在启动时下载模型权重。
- 不把 `YOLO_MODEL_PATH` 这类本机绝对路径提交到 git。
- 不缓存图片像素，仅在内存中临时存在。

## 验收标准

- 设置 `RECOGNITION_PROVIDER=yolo` 后，单张识别和批量识别成功在 `Annotation.objects` 写入非空检测结果。
- 检测到的物体中文名被写入 `Annotation.tags`。
- 图库搜索 `人`、`猫`、`汽车` 能命中包含相应物体的图片。
- 图片详情页能展示「检测到的物体」分区。
- 设置页能展示当前 Provider 名称。
- 切回 `RECOGNITION_PROVIDER=mock` 后，应用仍正常运行，与本阶段实施前行为一致。
- 模型路径不存在时，后端在启动期给出明确错误，不导致沉默崩溃。
- 后端测试套件通过。
- 前端 `npm run build` 通过。

## 未来扩展（明确不在本规格内）

- GPU / CUDA 推理。
- 多模型选择（yolo11s、yolo11m、自定义权重）。
- bounding box 可视化绘制。
- 「按物体筛选」高级筛选器。
- 增量识别队列、夜间自动识别策略。
- 离线模型自动下载与校验。
