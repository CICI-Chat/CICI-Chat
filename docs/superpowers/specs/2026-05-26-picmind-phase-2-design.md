# PicMind Phase 2 设计规格

## 目标

PicMind Phase 2 的目标是在 Phase 1 本地图库闭环之上，加入可替换的图片识别流水线。当前阶段先实现 Mock 图片识别 Provider，验证单张识别、批量识别、识别结果持久化和批量进度查询能力。

本阶段不接入真实本地模型或云端 API，但后端需要预留清晰接口，使后续可以替换为 Ollama、OpenAI、通义千问或其他视觉模型 Provider。

## 范围

### 包含

- 定义图片识别 Provider 接口。
- 实现 Mock 图片识别 Provider。
- 识别结果包含 `caption` 和 `tags`，并保留现有 `objects` 和 `model_used` 字段。
- 支持单张图片重新识别。
- 单张识别会覆盖已有 annotation。
- 支持按 `image_ids` 提交批量识别任务。
- 批量任务进度保存在内存中。
- 批量进度包含 `total`、`completed`、`failed`、`pending`、`running` 和 `status`。
- 识别结果持久化到现有 `annotations` 表。
- 前端支持在详情页触发单张重新识别。
- 前端支持在图库页选择多张图片并触发批量识别。
- 后端测试覆盖 Provider、单张识别、批量进度和 API 行为。

### 不包含

- 真实本地视觉模型接入。
- 真实云端视觉 API 接入。
- 批量任务持久化。
- 服务重启后的批量任务恢复。
- WebSocket 实时进度推送。
- 图片 embedding、向量检索和自然语言搜索。
- 多用户权限、任务取消和任务重试。

## 架构

Phase 2 沿用 Phase 1 的 FastAPI、SQLite、React 和 Vite 架构。后端在现有 `services/annotation.py` 的边界上扩展为识别流水线。

后端新增或扩展以下职责：

- `Recognizer`：图片识别 Provider 接口。输入图片文件路径和图片元数据，输出 caption、tags、objects 和 model_used。
- `MockRecognizer`：当前阶段的默认实现，生成可预测的 mock caption 和 tags。
- `RecognitionService`：处理单张识别，负责读取图片记录、调用 Provider、覆盖 annotation 并提交数据库事务。
- `BatchRecognitionService`：创建内存 batch job，按提交顺序逐张识别，并维护进度计数。
- `api/recognition.py`：暴露单张识别、批量创建和批量查询接口。

API 层不直接调用 ORM 写 annotation。所有识别写入都通过 `RecognitionService` 完成。

## 数据模型

Phase 2 不新增持久化表。

### annotations 表

继续使用 Phase 1 的 `annotations` 表：

| 字段 | 说明 |
| --- | --- |
| image_id | 图片 ID，也是主键。 |
| caption | 识别生成的一句话描述。 |
| tags | JSON 字符串，保存标签数组。 |
| objects | JSON 字符串，Phase 2 仍为空数组。 |
| model_used | Provider 名称，Mock 阶段为 `mock`。 |
| created_at | 当前 annotation 的生成时间。 |

单张识别和批量识别都会覆盖对应图片的 annotation。覆盖时更新 `caption`、`tags`、`objects`、`model_used` 和 `created_at`。

### 内存 batch job

批量任务只保存在进程内存中，不写入 SQLite。

每个 batch job 包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| batch_id | string | 批量任务 ID。 |
| image_ids | list[string] | 调用方提交的图片 ID 列表。 |
| total | integer | 提交图片总数。 |
| completed | integer | 成功识别并写入 annotation 的数量。 |
| failed | integer | 识别失败的数量。 |
| pending | integer | 尚未开始处理的数量。 |
| running | integer | 当前正在处理的数量，单进程后台任务下通常为 0 或 1。 |
| status | string | `pending`、`running`、`completed` 或 `failed`。 |
| errors | list[object] | 可选错误列表，记录失败图片 ID 和错误信息。 |

`completed + failed + pending + running` 必须等于 `total`。

## 后端 API

### 单张重新识别 / Recognize Image

- **请求方式 (Method):** POST
- **请求路径 (Path):** `/api/images/{image_id}/recognize`

#### 行为

1. 根据 `image_id` 查询图片。
2. 如果图片不存在，返回 404。
3. 如果本地文件缺失或不可读取，返回错误响应。
4. 调用当前配置的 Recognizer。
5. 覆盖或创建该图片的 annotation。
6. 返回更新后的图片详情。

#### 响应

响应结构与 `GET /api/images/{image_id}` 保持一致，包含最新的 `caption`、`tags`、`objects` 和 `model_used`。

### 创建批量识别任务 / Create Recognition Batch

- **请求方式 (Method):** POST
- **请求路径 (Path):** `/api/recognition/batches`
- **Content-Type:** application/json

#### 请求体

```json
{
  "image_ids": ["image-id-1", "image-id-2"]
}
```

#### 行为

1. 校验 `image_ids` 非空。
2. 创建内存 batch job。
3. 后台按提交顺序逐张调用 `RecognitionService`。
4. 立即返回当前进度。

#### 响应示例

```json
{
  "batch_id": "batch-123",
  "total": 2,
  "completed": 0,
  "failed": 0,
  "pending": 2,
  "running": 0,
  "status": "pending"
}
```

### 查询批量识别进度 / Get Recognition Batch

- **请求方式 (Method):** GET
- **请求路径 (Path):** `/api/recognition/batches/{batch_id}`

#### 行为

- 返回内存中的 batch job 进度。
- 如果 batch 不存在，返回 404。
- 服务重启后，旧 batch 会丢失，查询也返回 404。

#### 状态定义

| 状态 | 说明 |
| --- | --- |
| pending | 任务已创建，但尚未开始处理。 |
| running | 至少有一张图片正在处理，且任务未结束。 |
| completed | 所有图片都成功处理。 |
| failed | 任务已结束，且至少有一张图片失败。 |

## Mock Provider 行为

Mock Provider 必须稳定、可测试，并能体现未来真实 Provider 的调用形态。

输入包括：

- 图片文件路径。
- 图片 ID。
- 文件格式。
- 宽度和高度。
- 文件大小。

输出包括：

- `caption`：基于格式和尺寸生成，例如「一张 32 × 24 的 PNG 本地图片」。
- `tags`：至少包含 `本地图片`、图片格式和方向标签，例如 `横图`、`竖图` 或 `方图`。
- `objects`：Phase 2 固定为空数组。
- `model_used`：固定为 `mock`。

后续接入真实 Provider 时，只替换 Provider 实现，不改变 API 响应契约和 `RecognitionService` 的调用方式。

## 核心流程

### 单张识别流程

1. 前端在图片详情页点击「重新识别」。
2. 前端调用 `POST /api/images/{image_id}/recognize`。
3. 后端查询图片记录。
4. 后端调用 Mock Provider。
5. 后端覆盖 annotation。
6. 后端返回更新后的图片详情。
7. 前端刷新 caption、tags 和 model_used。

### 批量识别流程

1. 前端在图库页选择多张图片。
2. 前端调用 `POST /api/recognition/batches`，提交 `image_ids`。
3. 后端创建内存 batch job。
4. 后端后台逐张识别并更新 annotation。
5. 前端轮询 `GET /api/recognition/batches/{batch_id}`。
6. 前端展示 `total`、`completed`、`failed`、`pending` 和 `running`。
7. 任务结束后，前端刷新图库列表。

## 前端设计

### 图片详情页

`ImageDetail` 页面新增「重新识别」按钮。

交互要求：

- 点击后按钮进入 loading 状态。
- loading 状态下禁用按钮。
- 成功后使用响应数据更新当前详情。
- 失败时显示错误信息，不清空原有详情。

### 图库页

`Gallery` 页面新增多选和批量识别入口。

交互要求：

- 每张图片卡片可切换选中状态。
- 页面顶部显示已选择数量。
- 未选择图片时禁用「批量识别」按钮。
- 提交 batch 后显示批量进度。
- 轮询结束后刷新图库数据。

## 错误处理

- 图片 ID 不存在：单张识别返回 404；批量识别中该图片计入 failed。
- 图片文件缺失：识别失败，不删除图片记录。
- Provider 抛出异常：单张识别返回错误；批量识别中该图片计入 failed，并继续处理后续图片。
- batch ID 不存在：查询接口返回 404。
- `image_ids` 为空：创建批量任务返回 422 或 400。

批量任务中单张失败不能阻塞后续图片处理。

## 测试策略

后端测试覆盖：

- Mock Provider 根据图片元数据生成 caption 和 tags。
- 单张识别会覆盖已有 annotation。
- 单张识别在图片不存在时返回 404。
- 批量任务创建后返回正确的初始进度。
- 批量任务处理成功后，`completed`、`pending`、`running` 和 `status` 正确变化。
- 批量任务中不存在的图片计入 failed。
- 查询不存在的 batch 返回 404。
- 现有图片列表、详情、统计、设置和重扫测试继续通过。

前端验证覆盖：

- `npm run build` 通过。
- 详情页可以触发重新识别并刷新显示。
- 图库页可以选择多张图片并触发批量识别。
- 批量进度可以显示并最终结束。

## 验收标准

- 后端测试全部通过。
- 前端构建通过。
- 单张识别可以覆盖已有 annotation。
- 批量识别只处理调用方提交的 `image_ids`。
- 批量任务进度包含 `total`、`completed`、`failed`、`pending`、`running` 和 `status`。
- 批量任务进度字段满足 `completed + failed + pending + running = total`。
- 识别结果持久化到 `annotations` 表。
- batch job 只保存在内存中，服务重启后不恢复。
- Provider 接口可被本地模型或云端 API 实现替换。

## 后续扩展点

- 新增 Ollama 或其他本地视觉模型 Provider。
- 新增云端视觉 API Provider。
- 增加 Provider 配置项和设置页展示。
- 将 batch job 持久化到 SQLite。
- 使用 WebSocket 或 Server-Sent Events 推送批量进度。
- 在识别结果基础上增加 embedding 和自然语言搜索。
