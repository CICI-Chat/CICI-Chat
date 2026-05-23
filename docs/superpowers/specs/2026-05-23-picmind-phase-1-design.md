# PicMind Phase 1 设计规格

## 目标

PicMind Phase 1 的目标是搭建一个本地可运行的最小闭环：用户配置本地图片目录，后端在启动或手动触发时扫描目录，将图片元数据和 mock AI 标注写入 SQLite，前端通过 Web 页面展示图库、详情和基础统计。

本阶段重点验证项目结构、数据模型、前后端联通、本地图片访问和重复扫描去重能力。真实视觉模型、向量检索和实时监听放到后续阶段。

## 范围

### 包含

- 后端项目骨架：Python 3.11、FastAPI、SQLite。
- 前端项目骨架：React 18、Vite、TailwindCSS。
- 配置读取：通过 `.env` 配置 `WATCH_FOLDERS` 和 `DB_PATH`。
- 启动时扫描配置目录中的图片文件。
- 手动重新扫描接口。
- 图片 hash 去重。
- 图片基础元数据入库：路径、hash、大小、宽高、格式、创建时间、修改时间、索引时间。
- mock annotation：caption 和 tags。
- Web 图库、图片详情、设置页和统计页。
- 后端核心服务单元测试。

### 不包含

- Ollama、OpenAI、通义千问等真实视觉模型接入。
- LanceDB 或真实向量检索。
- watchdog 实时监听。
- WebSocket 索引进度推送。
- 多用户、权限系统和移动端。
- Docker Compose 完整生产化。

## 架构

项目采用前后端分离结构：

- `backend`：提供 REST API、目录扫描、图片元数据解析、SQLite 持久化和 mock annotation。
- `frontend`：通过 REST API 获取图片、统计和设置，并渲染本地图库。
- `data`：默认保存 SQLite 数据库文件。

后端内部按职责拆分：

- `config`：读取环境变量和默认配置。
- `models`：定义 SQLite 表结构。
- `services/scanner`：遍历配置目录，识别图片文件。
- `services/indexer`：计算 hash、去重、读取图片信息、写入数据库。
- `services/annotation`：生成 mock caption 和 tags，后续替换为真实视觉模型适配器。
- `api`：暴露图片、统计、设置和重新扫描接口。

前端内部按页面拆分：

- `Gallery`：图库网格、分页、标签筛选。
- `ImageDetail`：大图、元数据、caption 和 tags。
- `Dashboard`：总数、标签 Top、格式统计。
- `Settings`：展示当前配置，并提供重新扫描按钮。

## 数据模型

### images 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | UUID 主键。 |
| file_path | string | 图片绝对路径。 |
| file_hash | string | SHA256，用于去重。 |
| file_size | integer | 文件大小，单位：字节。 |
| width | integer | 图片宽度。 |
| height | integer | 图片高度。 |
| format | string | 图片格式，例如 `JPEG`、`PNG`。 |
| created_at | datetime | 文件创建时间。 |
| modified_at | datetime | 文件修改时间。 |
| indexed_at | datetime | 入库时间。 |

`file_hash` 必须唯一。重复扫描同一图片时不插入新记录。

### annotations 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| image_id | string | 关联 `images.id`。 |
| caption | string | 一句话描述。Phase 1 固定为 `待分析的本地图片`。 |
| tags | JSON string | 标签数组。Phase 1 固定为 `["本地图片", "待分析"]`。 |
| objects | JSON string | Phase 1 固定为空数组。 |
| model_used | string | Phase 1 固定为 `mock`。 |
| created_at | datetime | 标注创建时间。 |

## 后端 API

### 获取图片列表

- **Method:** GET
- **Path:** `/api/images`
- **Query:**
  - `page`：页码，默认 `1`。
  - `size`：每页数量，默认 `50`。
  - `tag`：可选标签筛选。

返回分页图片列表。每个图片包含基础元数据、caption、tags 和可访问的图片 URL。

### 获取图片详情

- **Method:** GET
- **Path:** `/api/images/{id}`

返回单张图片的元数据、caption、tags、objects 和图片 URL。

### 获取统计信息

- **Method:** GET
- **Path:** `/api/stats`

返回：

- 图片总数。
- 标签 Top 列表。
- 格式分布。

### 获取设置

- **Method:** GET
- **Path:** `/api/settings`

返回当前 `WATCH_FOLDERS`、`DB_PATH` 和 Phase 1 的 mock provider 信息。API Key 不在本阶段处理。

### 手动重新扫描

- **Method:** POST
- **Path:** `/api/reindex`

触发一次同步或后台扫描。Phase 1 可以采用同步实现，返回本次扫描的新增数量、跳过数量和错误数量。

### 图片访问

后端提供安全的图片访问路由，例如 `/api/images/{id}/file`。前端不直接读取本地绝对路径。

## 核心流程

### 启动扫描

1. 后端启动。
2. 读取 `WATCH_FOLDERS`。
3. 遍历支持的图片格式：`.jpg`、`.jpeg`、`.png`、`.webp`、`.gif`、`.bmp`。
4. 计算 SHA256。
5. 如果 hash 已存在，跳过。
6. 使用 Pillow 读取宽高和格式。
7. 写入 `images` 表。
8. 写入 mock `annotations` 表。

### 手动重新扫描

1. 前端在 Settings 页面点击「重新扫描」。
2. 调用 `POST /api/reindex`。
3. 后端重复执行扫描流程。
4. 前端刷新图库和统计。

### 图库浏览

1. 前端打开 Gallery 页面。
2. 调用 `GET /api/images`。
3. 渲染图片网格。
4. 用户点击图片进入详情页。
5. 详情页调用 `GET /api/images/{id}`。

## 错误处理

- 配置目录不存在：记录错误，扫描继续处理其他目录，`/api/settings` 中显示原始配置。
- 文件不是有效图片：跳过并计入错误数量。
- 图片读取失败：跳过该文件，不影响其他文件。
- 数据库写入失败：API 返回 500，并在后端日志中保留错误原因。
- 图片文件被删除：详情接口返回 404 或图片文件接口返回 404。

## 测试策略

后端单元测试覆盖：

- 扫描目录时只识别支持的图片格式。
- 相同 hash 的图片不会重复写入。
- `POST /api/reindex` 多次调用不会重复插入。
- `GET /api/images` 返回分页数据。
- `GET /api/images/{id}` 返回图片详情。
- `GET /api/stats` 返回总数、标签统计和格式统计。

前端 Phase 1 以手动验证为主：

- 能加载图库。
- 能进入详情页。
- 能查看统计。
- Settings 页面能触发重新扫描。

## 验收标准

- 后端和前端能在本地分别启动。
- 配置 `WATCH_FOLDERS` 后，后端启动时能扫描已有图片。
- 前端图库能展示扫描到的图片。
- 点击图片能查看详情、caption 和 tags。
- 点击「重新扫描」不会重复插入已存在图片。
- 后端核心测试通过。
- 整个 Phase 1 不依赖真实视觉模型或向量数据库。

## 后续扩展点

Phase 1 需要为后续阶段保留清晰扩展边界：

- 将 mock annotation 替换为 Ollama LLaVA provider。
- 增加 LanceDB 和 CLIP embedding。
- 增加自然语言搜索接口。
- 增加 watchdog 实时监听。
- 增加 WebSocket 进度推送。
- 增加 Docker Compose 一键启动。
