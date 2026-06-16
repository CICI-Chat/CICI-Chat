/**
 * H4: 中心点偏移 overlay 组件
 *
 * 职责：
 * - 绘制画面中心的青色十字准星
 * - 绘制目标中心点（黄色圆点）
 * - 用 SVG 绘制从中心到目标的偏移箭头
 * - 在左上角显示偏移数值
 *
 * 行为：只有检测到危险目标（人、车、动物）时才显示所有元素
 */

interface TargetOffset {
  target_index: number;
  label?: string;
  name?: string;
  confidence?: number;
  target_center: { x: number; y: number };
  dx: number;
  dy: number;
  dx_px: number;
  dy_px: number;
}

interface CenterOffsetOverlayProps {
  targetOffset?: TargetOffset | null;
}

export function CenterOffsetOverlay({ targetOffset }: CenterOffsetOverlayProps) {
  // 🔧 调试：先放宽校验，只要有 target_offset 就用它
  const safeOffset = targetOffset;

  // 🔧 调试信息 - 右上角（永远显示，方便调试）
  const debugInfo = (
    <div className="absolute right-3 top-3 rounded bg-blue-900/80 px-2 py-1 text-xs text-white z-50">
      <div>调试：targetOffset = {targetOffset ? '有值' : 'null/undefined'}</div>
      {targetOffset && (
        <>
          <div>label: {targetOffset.label}</div>
          <div>name: {targetOffset.name}</div>
          <div>center: {targetOffset.target_center?.x?.toFixed?.(3)}, {targetOffset.target_center?.y?.toFixed?.(3)}</div>
        </>
      )}
    </div>
  );

  // 没有有效目标时，只显示调试信息
  if (!safeOffset) {
    return debugInfo;
  }

  // 计算偏移距离，用于显示颜色
  const distance = Math.sqrt(safeOffset.dx * safeOffset.dx + safeOffset.dy * safeOffset.dy);

  const getOffsetColor = () => {
    if (distance < 0.05) return 'text-green-400'; // 已居中
    if (distance < 0.15) return 'text-yellow-400'; // 轻微偏移
    return 'text-red-400'; // 明显偏移
  };

  return (
    <div className="pointer-events-none absolute inset-0">
      {/* 🔧 调试信息 */}
      {debugInfo}

      {/* 中心十字准星 - 青色 */}
      <div className="absolute left-1/2 top-1/2 h-8 w-px -translate-x-1/2 -translate-y-1/2 bg-cyan-400/90 shadow-[0_0_4px_rgba(34,211,238,0.8)]" />
      <div className="absolute left-1/2 top-1/2 h-px w-8 -translate-x-1/2 -translate-y-1/2 bg-cyan-400/90 shadow-[0_0_4px_rgba(34,211,238,0.8)]" />

      {/* 偏移箭头 - SVG 画线 */}
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <defs>
          <marker
            id="offset-arrow"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="rgb(250, 204, 21)" />
          </marker>
        </defs>

        <line
          x1="50"
          y1="50"
          x2={safeOffset.target_center.x * 100}
          y2={safeOffset.target_center.y * 100}
          stroke="rgb(250, 204, 21)"
          strokeWidth="0.5"
          markerEnd="url(#offset-arrow)"
        />
      </svg>

      {/* 目标中心点 - 黄色圆点带白边 */}
      <div
        className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-yellow-400 shadow"
        style={{
          left: `${safeOffset.target_center.x * 100}%`,
          top: `${safeOffset.target_center.y * 100}%`,
        }}
      />

      {/* 偏移数值显示 - 左上角 */}
      <div className="absolute left-3 top-3 rounded bg-black/60 px-2 py-1 text-xs text-white">
        <div className="font-medium">
          目标：{safeOffset.name || safeOffset.label || '未知'}{' '}
          {safeOffset.confidence ? `${Math.round(safeOffset.confidence * 100)}%` : ''}
        </div>
        <div className={getOffsetColor()}>
          偏移：dx {safeOffset.dx_px}px，dy {safeOffset.dy_px}px
        </div>
      </div>
    </div>
  );
}
