# PicMind Phase 2 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 PicMind 增加 Mock 图片识别流水线，支持单张重新识别、按图片 ID 批量识别和内存批量进度查询。

**架构：** 后端新增可替换的 Recognizer Provider 接口、Mock Provider、RecognitionService 和内存 BatchRecognitionService。识别结果覆盖写入现有 `annotations` 表，批量任务进度只保存在进程内存中。前端在详情页触发单张识别，在图库页多选图片并轮询批量进度。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy、pytest、React、TypeScript、Vite、TailwindCSS。

---

## 文件结构

### 后端

- 修改：`backend/app/services/annotation.py` — 从 Phase 1 固定 mock annotation 扩展为可替换 Recognizer 接口和 MockRecognizer。
- 创建：`backend/app/services/recognition.py` — 单张识别服务，读取图片、调用 Provider、覆盖 annotation。
- 创建：`backend/app/services/batch_recognition.py` — 内存批量任务服务，维护 `total/completed/failed/pending/running/status`。
- 修改：`backend/app/schemas.py` — 增加单张识别、批量创建和批量进度响应模型。
- 创建：`backend/app/api/recognition.py` — 暴露 `/api/images/{image_id}/recognize`、`POST /api/recognition/batches`、`GET /api/recognition/batches/{batch_id}`。
- 修改：`backend/app/main.py` — 注册 recognition router。
- 创建：`backend/tests/test_recognition.py` — 覆盖 Provider 和单张识别服务。
- 创建：`backend/tests/test_batch_recognition.py` — 覆盖内存批量任务状态迁移。
- 修改：`backend/tests/test_api.py` — 增加识别 API 测试。

### 前端

- 修改：`frontend/src/api/client.ts` — 增加 recognition API 类型和方法。
- 修改：`frontend/src/pages/ImageDetail.tsx` — 增加「重新识别」按钮和错误/loading 状态。
- 修改：`frontend/src/pages/Gallery.tsx` — 增加多选、批量识别按钮和进度轮询。

---

## 任务拆分

### 任务 1：实现 Recognizer 接口和 Mock Provider

修改 `backend/app/services/annotation.py`，新增 `RecognitionResult`、`ImageRecognitionInput`、`Recognizer` 和 `MockRecognizer`。测试写在 `backend/tests/test_recognition.py`，覆盖横图、竖图和方图标签。运行 `cd backend && uv run pytest tests/test_recognition.py tests/test_annotation.py -v`，通过后提交 `feat: add mock image recognizer`。

### 任务 2：实现单张识别服务

创建 `backend/app/services/recognition.py`，实现 `RecognitionService.recognize_image(image_id, db)`。服务查询图片，检查文件存在，调用 `MockRecognizer`，覆盖或创建 annotation，并返回刷新后的 `Image`。测试覆盖覆盖旧 annotation、图片不存在和文件缺失。运行 `cd backend && uv run pytest tests/test_recognition.py -v`，通过后提交 `feat: add single image recognition service`。

### 任务 3：实现内存批量识别服务

创建 `backend/app/services/batch_recognition.py`，实现 `BatchJob`、`BatchRecognitionService`、`BatchNotFoundError` 和 `EmptyBatchError`。`create_batch(image_ids)` 初始化 `pending = total`，`run_batch(batch_id, db)` 逐张调用 `RecognitionService`，维护 `completed/failed/pending/running/status`，失败继续处理后续图片。测试写在 `backend/tests/test_batch_recognition.py`。运行 `cd backend && uv run pytest tests/test_batch_recognition.py -v`，通过后提交 `feat: add batch recognition progress tracking`。

### 任务 4：暴露识别 API

修改 `backend/app/schemas.py`，增加 `RecognitionBatchCreate` 和 `RecognitionBatchResponse`。创建 `backend/app/api/recognition.py`，暴露：

- `POST /api/images/{image_id}/recognize`
- `POST /api/recognition/batches`
- `GET /api/recognition/batches/{batch_id}`

修改 `backend/app/main.py` 注册 router。扩展 `backend/tests/test_api.py`，覆盖单张识别、缺失图片、创建并查询 batch、缺失 batch。运行 `cd backend && uv run pytest tests/test_api.py -v` 和 `cd backend && uv run pytest -v`，通过后提交 `feat: expose recognition api`。

### 任务 5：扩展前端 API 客户端

修改 `frontend/src/api/client.ts`，新增 `RecognitionBatch` 类型，以及 `recognizeImage`、`createRecognitionBatch`、`getRecognitionBatch` 方法。运行 `cd frontend && npm run build`，通过后提交 `feat: add recognition api client`。

### 任务 6：在详情页增加单张重新识别

修改 `frontend/src/pages/ImageDetail.tsx`，新增 `recognizing` 状态和「重新识别」按钮。点击后调用 `api.recognizeImage(imageId)`，成功后刷新当前详情，失败时保留原详情并显示错误。运行 `cd frontend && npm run build`，通过后提交 `feat: add single image recognition action`。

### 任务 7：在图库页增加多选批量识别

修改 `frontend/src/pages/Gallery.tsx`，新增 `selectedIds` 和 `batch` 状态。每张卡片增加 checkbox，顶部显示已选择数量和「批量识别」按钮。调用 `api.createRecognitionBatch(selectedIds)` 后轮询 `api.getRecognitionBatch(batch_id)`，显示 `total/completed/failed/pending/running/status`，结束后刷新图库。运行 `cd frontend && npm run build`，通过后提交 `feat: add batch recognition controls`。

### 任务 8：最终验证和文档更新

运行：

```bash
cd backend && uv run pytest -v
```

预期：PASS。

运行：

```bash
cd frontend && npm run build
```

预期：PASS。

手动验证：启动后端和前端，在浏览器确认详情页单张重新识别、图库多选批量识别和批量进度展示可用。验证完成后在本计划末尾追加验证记录，并提交 `docs: add picmind phase two plan`。

---

## 自检结果

- 规格覆盖度：本计划覆盖 Provider 接口、Mock Provider、单张识别覆盖 annotation、按 `image_ids` 批量识别、内存进度、识别 API、前端详情页操作、前端图库批量操作、后端测试和前端验证。
- 占位符扫描：计划不包含待定章节、TODO 或未定义的后续步骤。
- 类型一致性：`ImageRecognitionInput`、`RecognitionResult`、`RecognitionService`、`BatchRecognitionService`、`RecognitionBatchResponse` 和前端 `RecognitionBatch` 字段保持一致。

## 验证记录

- 后端完整测试：`cd backend && uv run pytest -v`，44 passed。
- 前端生产构建：`cd frontend && npm run build`，TypeScript 与 Vite build 通过。
- 运行时验证：使用临时样例图片目录启动后端，`GET /api/images` 返回 3 张图片，`POST /api/images/{image_id}/recognize` 返回 200 和 mock 标签，`POST /api/recognition/batches` 返回 201 且批量状态 completed，`GET /api/recognition/batches/{batch_id}` 返回同一进度。
- 异常路径验证：缺失 batch 返回 404，空 batch 返回 400。
- 前端 dev server 可响应 HTML；浏览器点击级验证因 Playwright MCP Bridge 连接超时未完成。
