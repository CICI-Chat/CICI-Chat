# YOLO11n 物体框可视化设计

**目标:** 在图片详情页上把 YOLO 识别出来的物体用红色边框 + 中文标签直接画在图片上，让用户一眼看到「哪个物体在图片的哪个位置」。

**最简化决定（已与用户确认）:**

- 交互：静态红框 + 标签，不可点、不可关。
- 颜色：所有物体框统一红色。
- 旧数据：允许「YOLO 模式下已识别但未存 bbox 的图片」不显示框；用户需要框时手动点「重新识别」即可。
- 前端实现：CSS 绝对定位 `<div>` 叠加在 `<img>` 上，不引入第三方库、不用 canvas。

---

## 1. 数据契约变更

唯一改动：`Annotation.objects` JSON 数组中每个对象新增 4 个字段。

**改前：**
```json
{ "label": "person", "name": "人", "confidence": 0.89 }
```

**改后：**
```json
{
  "label": "person",
  "name": "人",
  "confidence": 0.89,
  "x": 0.31,
  "y": 0.18,
  "w": 0.22,
  "h": 0.64
}
```

- `x`、`y`：边框左上角的归一化坐标（0.0–1.0，相对于图片宽/高）。
- `w`、`h`：边框宽高的归一化值。
- 所有数字保留 4 位小数。
- **不向后破坏**：旧记录里缺失 `x/y/w/h` 字段时，前端按「无 bbox」处理，只显示 chip。
- **不需要数据库迁移**：`annotations.objects` 本来就是 JSON TEXT。

## 2. 后端改动

**文件:** `backend/app/services/yolo_recognizer.py`

在 `for box in boxes:` 循环里追加：

```python
cx, cy, bw, bh = box.xywhn[0].tolist()  # YOLO 提供的中心点归一化坐标
x = max(0.0, cx - bw / 2)
y = max(0.0, cy - bh / 2)
objects.append({
    "label": label,
    "name": name,
    "confidence": confidence,
    "x": round(x, 4),
    "y": round(y, 4),
    "w": round(bw, 4),
    "h": round(bh, 4),
})
```

**为什么 `max(0.0, ...)`**：YOLO 偶尔会给出框中心贴近边缘、left = cx − w/2 < 0 的边界值，裁到 0 防止前端渲染时出现负偏移。

**测试**：在 `backend/tests/test_yolo_recognizer.py` 已有的 fake YOLO mock 上扩展 `FakeBox`，加一个 `xywhn` 属性返回固定坐标，断言输出 dict 含 4 个新字段且值落在 [0, 1]。

## 3. 前端改动

**文件:** `frontend/src/pages/ImageDetail.tsx`

把现有的 `<img>` 包一层相对定位容器，按 objects 的 `x/y/w/h` 在容器内绝对定位红框：

```tsx
<div className="relative inline-block">
  <img ... />
  {image.objects?.map((obj, idx) => {
    const o = obj as Record<string, unknown>;
    const x = o.x as number | undefined;
    const y = o.y as number | undefined;
    const w = o.w as number | undefined;
    const h = o.h as number | undefined;
    const name = (o.name as string) ?? (o.label as string);
    const conf = o.confidence as number | undefined;
    if (typeof x !== 'number' || typeof y !== 'number'
        || typeof w !== 'number' || typeof h !== 'number') {
      return null;  // 旧数据无 bbox → 不画
    }
    return (
      <div
        key={idx}
        className="absolute border-2 border-red-500 pointer-events-none"
        style={{
          left:   `${x * 100}%`,
          top:    `${y * 100}%`,
          width:  `${w * 100}%`,
          height: `${h * 100}%`,
        }}
      >
        <span className="absolute -top-6 left-0 bg-red-500 text-white text-xs px-1.5 py-0.5 rounded">
          {name} {typeof conf === 'number' ? `${Math.round(conf * 100)}%` : ''}
        </span>
      </div>
    );
  })}
</div>
```

**关键点：**
- `relative` 容器 + `absolute` 子元素 → 子元素的 `left/top/width/height` 用 `%` 自动以容器（= 图片渲染尺寸）为基准。图片缩放，框跟着缩放。
- `pointer-events-none` → 框不阻挡点击图片本身的交互（虽然现在没有，但留给未来）。
- 标签 `-top-6 left-0` → 贴在框上方左对齐，宽框/窄框都美观。
- 标签栏溢出图片顶部时由浏览器自然处理，不做防溢出（YAGNI）。

下方原有的蓝色 chip 列表保留——红框给位置感，chip 给完整列表（包括有些用户可能更习惯看 chip）。

## 4. 测试与验证

**后端：**
- 扩展 `test_yolo_recognizer.py::test_yolo_recognizer_filters_low_confidence_and_sorts`，断言新增的 `x/y/w/h` 字段存在、类型 float、落在 [0, 1]。
- 全量回归：`uv run pytest -q` 保持绿。

**前端：**
- `npm run build` 通过（TypeScript 编译）。
- 手工验证：找一张含 COCO 物体的图（用之前测过的 bus.jpg），扔进监听目录 → 浏览器进详情页 → 点「重新识别」→ 看到红框 + 标签贴合人物/车辆。

## 5. 不做什么（明确范围）

- ❌ 不写迁移脚本回填旧 annotation（用户选择「旧数据无框」）。
- ❌ 不按类别变色、不按置信度变色。
- ❌ 不做 hover/click 交互、不做框选中态。
- ❌ 不引入 canvas、不引入第三方库。
- ❌ 不做框溢出图片的防御性裁剪（除 left/top 裁到 0 外）。
- ❌ 不做图库缩略图上的框（详情页才有）。

这些都是有意识地推迟到「真有需求」再说，不在本次范围内。
