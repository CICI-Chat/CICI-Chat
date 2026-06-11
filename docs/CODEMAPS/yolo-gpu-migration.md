# 把 PicMind 的 YOLO 推理从 CPU 切到 GPU（N 卡电脑）

> 当你回到带独立 N 卡的电脑上跑 PicMind 时，照这份文档操作可以把推理速度提升 **5–10 倍**。
> 业务代码、模型文件、`.env` 全部不动，只换底层 PyTorch 包。

## 适用范围

- ✅ 电脑里装了一张 **NVIDIA 显卡**（GTX 10 系及以后、RTX 全系都行）。
- ✅ 显卡驱动是最近 2 年内更新过的（PyTorch 2.x 至少要 CUDA 12.x 驱动）。
- ❌ AMD/Intel 集成显卡不适用，仍然只能用 CPU。
- ❌ 用纯笔记本核显的 N 卡（如 MX150 之类）也不建议，性能提升有限。

## 第 0 步：确认显卡和驱动

打开 PowerShell 或 cmd：

```bash
nvidia-smi
```

应能看到一张表格，左上角显示「Driver Version: 5xx.xx / CUDA Version: 12.x」。

- ✅ **CUDA Version ≥ 12.4**：直接走下面的步骤。
- ⚠️ **CUDA Version 在 12.1–12.3 之间**：可以用 CUDA 12.1 wheel（把下面的 `cu124` 换成 `cu121` 即可）。
- ❌ **CUDA Version < 12.0**：先去 https://www.nvidia.com/drivers 升级显卡驱动。
- ❌ **`nvidia-smi` 命令不存在**：驱动没装好，去 NVIDIA 官网装一遍。

## 第 1 步：克隆代码（如果是新电脑）

```bash
cd "D:/my vibe coding"   # 或者你想放代码的目录
git clone <你的仓库地址> "picture check"
cd "picture check/backend"
```

如果是同步现有项目（git pull），跳过这一步。

## 第 2 步：换 PyTorch 包

```bash
cd backend
uv remove torch torchvision
uv add torch torchvision --index https://download.pytorch.org/whl/cu124
uv sync
```

- 第 1 行：卸 CPU 版（~210 MB）
- 第 2 行：装 CUDA 12.4 版（~2.5 GB，5–15 分钟看网速）
- 第 3 行：同步其他依赖

期间会下载一堆 `nvidia-cudnn-*`、`nvidia-cublas-*` 等 CUDA 运行时库，全部留在 `.venv/`，不会污染系统。

## 第 3 步：验证 GPU 已被 PyTorch 识别

```bash
uv run python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

期望输出（实际显卡名字按你的电脑显示）：
```
CUDA available: True
Device: NVIDIA GeForce RTX 4070
```

如果显示 `CUDA available: False`：
1. 检查 `nvidia-smi` 还能不能用。
2. 检查装的是不是 cu124 版：`uv run pip show torch | grep -i version`，应当带 `+cu124` 后缀。
3. 重启电脑（驱动刚更新的情况）。

## 第 4 步：确认 YOLO 走 GPU

YOLO（ultralytics）**默认自动选择最快设备**——只要 `torch.cuda.is_available()` 为 True，它就会自动用 GPU，**业务代码 0 行改动**。

跑一次冒烟测试：

```bash
uv run python -c "
from app.config import Settings
from app.services.recognition import build_recognizer
from app.services.annotation import ImageRecognitionInput
from pathlib import Path
from PIL import Image as PI
import urllib.request, tempfile, time

# 用 ultralytics 官方 bus.jpg（包含 4 人 + 1 公交）
url = 'https://ultralytics.com/images/bus.jpg'
tmp = Path(tempfile.gettempdir()) / 'gpu_smoke_bus.jpg'
if not tmp.exists():
    urllib.request.urlretrieve(url, tmp)

s = Settings(_env_file='.env')
r = build_recognizer(s)
w, h = PI.open(tmp).size
inp = ImageRecognitionInput(image_id='gpu', file_path=str(tmp), width=w, height=h, format='jpg')

# 跑 5 次取后 4 次平均，第一次包含 GPU warmup
times = []
for i in range(5):
    t0 = time.time()
    r.recognize(inp)
    times.append(time.time() - t0)
    print(f'iter {i}: {times[-1]*1000:.1f} ms')
print(f'avg (excl. warmup): {sum(times[1:])/4*1000:.1f} ms')
"
```

期望对比（同一张 bus.jpg 的推理耗时）：

| 设备 | 单张耗时 | 备注 |
|---|---|---|
| CPU（torch 2.12+cpu） | 350–500 ms | 这台电脑现在的水平 |
| GPU RTX 30/40 系 | **30–60 ms** | 提升约 8 倍 |
| GPU GTX 10/16 系 | 80–150 ms | 提升约 4 倍 |

第一次跑会慢一点（GPU warmup + 模型加载到显存），从第二次开始才能看到真实的推理速度。

## 第 5 步：跑全量测试 + 启动服务

```bash
cd backend
uv run pytest -q               # 应当 161 passed
cd ../
# 双击 start-picmind.bat 启动
```

进入图库 → 详情页 → 「重新识别」一张含 COCO 物体的图 → 应该看到红框 + 标签，**速度肉眼可感比 CPU 流畅**。

## 第 6 步：（可选）固定 GPU 设备

如果电脑有多张显卡，可以在 `backend/.env` 里追加一行强制走某一张：

```env
CUDA_VISIBLE_DEVICES=0     # 0 表示用第 1 张卡，1 表示第 2 张
```

通常 PicMind 只用一张就够了，不用动。

## 把 CPU 和 GPU 都跑过的电脑该怎么管理？

如果同一台电脑上你既想保留 CPU 版又想试 GPU 版（罕见），**用 git 分支隔离 uv.lock**：

```bash
git checkout -b gpu/local       # 在 GPU 设置下创建本地分支
uv remove torch torchvision
uv add torch torchvision --index https://download.pytorch.org/whl/cu124
uv sync
# 这条分支永远不要 push、不要合到 master
```

切回 CPU 时：

```bash
git checkout master             # 切回 CPU 的 lock
uv sync                         # 重装 CPU 版
```

**绝大多数情况你不需要这么干**——一台电脑用一种版本最省心。

## 常见问题

**Q1: `uv add torch --index https://download.pytorch.org/whl/cu124` 报 "No solution found"**
A: 你的 Python 版本可能太新（如 3.14）。PyTorch 的 CUDA wheel 通常滞后 Python 半年到一年。临时方案：在 `backend/pyproject.toml` 里加 `requires-python = ">=3.11,<3.13"`，删 `.venv` 后重建。

**Q2: 推理时报 `CUDA out of memory`**
A: 显卡显存不够。YOLO11n 只占 ~200 MB，正常显卡（≥ 4 GB）不会触发。如果触发，检查是不是别的程序（游戏/浏览器）正在占显存，关掉再试。

**Q3: GPU 比 CPU 还慢**
A: 一次只识别一张图时，GPU 启动开销可能盖过推理收益。批量识别（Settings 页里的批量任务）才能完全发挥 GPU 价值。这是正常现象。

**Q4: 我要把这个 GPU 版同步回 CPU 那台机器怎么办？**
A: GPU 那台正常 `git commit/push` 业务代码，**不要 push 修改过的 uv.lock**（在 push 前 `git checkout backend/uv.lock` 还原）。CPU 那台 `git pull` 后 `uv sync` 即可。如果业务代码也改了 `pyproject.toml` 的 dependencies，两端各自维护 lock 就行。

## 总结

| 改动项 | 改不改？ |
|---|---|
| 业务代码（`yolo_recognizer.py` 等） | ❌ 不动 |
| `pyproject.toml` | ❌ 不动 |
| `.env` | ❌ 不动 |
| 模型文件 `yolo11n.pt` | ❌ 不动 |
| **`uv.lock`** | ✅ 自动更新（uv remove/add 时） |
| **本地 `.venv/`** | ✅ 重建（uv 自动） |

整个 GPU 切换大约花 **10 分钟**（含下载），完全零编码。
