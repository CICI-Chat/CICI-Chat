# PicMind 批次历史记录页面设计

## 目标

为 PicMind 增加独立的“批次历史”页面，让用户查看过去的批量识别任务、查看失败图片，并一键重新识别失败项。

## 背景

当前 PicMind 已有 SQLite 持久化后台识别队列，支持大批量识别、暂停、继续、取消、刷新恢复和重启恢复。Gallery 只展示当前 active batch，缺少查看历史批次和定位失败图片的入口。

批次历史页面复用现有 `recognition_batches` 和 `recognition_batch_items` 表，不新增数据库表。

## 第一版范围

包含：

- 新增独立页面：批次历史
- 顶部导航新增入口
- 批次列表，按创建时间倒序展示
- 批次列表分页
- 批次详情，默认显示失败项
- 批次 item 按状态筛选，第一版至少支持 `failed`
- 失败项展示图片缩略图、路径、状态、错误原因
- “重新识别失败项”按钮，复用现有批次创建 API 创建新批次

不包含：

- 删除历史批次
- 批次命名
- 批次搜索
- 导出日志
- 单张失败项逐个重试
- 自动跳转 Gallery
- 复杂统计图表

## 后端设计

### 数据模型

复用现有模型：

- `RecognitionBatch`
- `RecognitionBatchItem`
- `Image`
- `Annotation`

不新增表。

### Schema

新增批次列表响应：

```python
class RecognitionBatchList(BaseModel):
    items: list[RecognitionBatchResponse]
    total: int
    page: int
    size: int
```

新增批次 item 响应：

```python
class RecognitionBatchItemImage(BaseModel):
    id: str
    file_path: str
    caption: str
    image_url: str

class RecognitionBatchItemResponse(BaseModel):
    id: int
    image_id: str
    status: str
    error: str | None
    image: RecognitionBatchItemImage

class RecognitionBatchItemList(BaseModel):
    items: list[RecognitionBatchItemResponse]
    total: int
    page: int
    size: int
```

日期字段沿用现有批次响应，如果实现时扩展 `RecognitionBatchResponse`，至少包含 `created_at` 和 `updated_at` 以支持历史列表展示。

### API

新增历史列表接口：

```text
GET /api/recognition/batches?page=1&size=20
```

行为：

- 按 `RecognitionBatch.created_at desc` 排序
- 返回分页结果
- 每个 item 使用现有批次进度字段：`batch_id`、`total`、`completed`、`failed`、`pending`、`running`、`cancelled`、`status`
- 包含 `created_at` 和 `updated_at`

新增批次 item 接口：

```text
GET /api/recognition/batches/{batch_id}/items?page=1&size=50&status=failed
```

行为：

- 批次不存在返回 `404 Batch not found`
- `status` 为空时返回该批次全部 item
- `status=failed` 时只返回失败项
- 每个 item 包含图片基本信息和错误原因
- 图片缩略图 URL 复用现有 `/api/images/{image_id}/file` 路径模式

重新识别失败项不新增后端接口。前端收集失败项中的 `image_id`，调用现有：

```text
POST /api/recognition/batches
```

请求体：

```json
{
  "image_ids": ["image-id-1", "image-id-2"]
}
```

### 服务层

在 `BatchRecognitionService` 中新增只读方法：

- `list_batches(db, page, size)`
- `list_batch_items(db, batch_id, page, size, status=None)`

这些方法只查询数据库，不启动识别，不修改批次状态。

## 前端设计

### API client

在 `frontend/src/api/client.ts` 中新增类型：

- `RecognitionBatchList`
- `RecognitionBatchItemImage`
- `RecognitionBatchItem`
- `RecognitionBatchItemList`

新增方法：

- `listRecognitionBatches(params)`
- `listRecognitionBatchItems(batchId, params)`

复用现有：

- `createRecognitionBatch(imageIds)`

### 页面

新增页面：

```text
frontend/src/pages/BatchHistory.tsx
```

布局：

- 标题：批次历史
- 左侧或上方：批次列表
- 右侧或下方：批次详情
- 窄屏时上下排列

批次列表每条显示：

- 状态
- total / completed / failed / pending / running / cancelled
- created_at / updated_at

状态颜色：

- `queued` / `running`：蓝色
- `paused`：黄色
- `completed`：绿色
- `failed`：红色
- `cancelled`：灰色

批次详情：

- 点击批次后加载失败项
- 默认请求 `status=failed`
- 没有失败项时显示“这个批次没有失败图片”
- 有失败项时显示缩略图、路径、错误原因、状态

重新识别失败项：

- 仅当失败项数量大于 0 时显示按钮
- 点击后收集当前失败项 `image_id`
- 调用 `api.createRecognitionBatch(imageIds)`
- 成功后显示“已创建新的识别批次”
- 第一版不自动跳转 Gallery

### 导航

在 `frontend/src/App.tsx` 增加页面状态和导航入口：

```text
图库 | 设置 | 批次历史
```

## 测试设计

### 后端测试

在 `backend/tests/test_batch_recognition.py` 或 `backend/tests/test_api.py` 添加测试：

1. 批次历史列表按创建时间倒序返回
2. 批次历史列表支持分页
3. 批次 item 接口可筛选 `status=failed`
4. 批次 item 响应包含图片基本信息和错误原因
5. 不存在批次的 item 接口返回 404
6. 从 failed item 的 image IDs 创建新批次返回 202

### 前端源码守卫

当前项目没有完整 React 测试框架，第一版沿用源码守卫。新增或扩展源码测试，检查：

- 存在 `BatchHistory` 页面
- 存在 `api.listRecognitionBatches`
- 存在 `api.listRecognitionBatchItems`
- 导航包含“批次历史”
- 页面包含“重新识别失败项”
- item 请求支持 `status=failed`

### 验证命令

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest -q
npm --prefix "D:/my vibe coding/picture check/frontend" run build
```

## 手动验证

1. 创建一个批量识别任务
2. 让部分图片失败，或用缺失文件模拟失败
3. 打开“批次历史”页面
4. 确认历史列表显示该批次
5. 点击该批次
6. 确认失败项显示图片、路径和错误原因
7. 点击“重新识别失败项”
8. 确认创建新的识别批次

## 实现顺序

1. 后端 schema
2. 后端 service 查询方法
3. 后端 API
4. 后端测试
5. 前端 API client
6. `BatchHistory` 页面
7. App 导航入口
8. 前端源码守卫
9. 完整验证
