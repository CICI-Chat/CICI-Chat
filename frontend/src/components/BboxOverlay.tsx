type BoxObject = Record<string, unknown>;

const TRACK_COLORS = [
  'border-red-500 bg-red-500',
  'border-sky-500 bg-sky-500',
  'border-emerald-500 bg-emerald-500',
  'border-fuchsia-500 bg-fuchsia-500',
  'border-orange-500 bg-orange-500',
  'border-violet-500 bg-violet-500',
];

function colorForTrack(trackId: number | undefined) {
  if (typeof trackId !== 'number') return 'border-red-500 bg-red-500';
  return TRACK_COLORS[Math.abs(trackId) % TRACK_COLORS.length];
}

export function BboxOverlay({ objects }: { objects?: BoxObject[] | null }) {
  if (!objects?.length) return null;
  return (
    <>
      {objects.map((obj, idx) => {
        const x = obj.x as number | undefined;
        const y = obj.y as number | undefined;
        const w = obj.w as number | undefined;
        const h = obj.h as number | undefined;
        if (typeof x !== 'number' || typeof y !== 'number'
            || typeof w !== 'number' || typeof h !== 'number') {
          return null;
        }
        const trackId = obj.track_id as number | undefined;
        const active = obj.is_active_target === true;
        const name = (obj.name as string | undefined) ?? (obj.label as string | undefined) ?? '';
        const conf = obj.confidence as number | undefined;
        const pct = typeof conf === 'number' ? `${Math.round(conf * 100)}%` : '';
        const color = colorForTrack(trackId);
        const [borderColor, bgColor] = color.split(' ');
        const dist = obj.distance_m as number | undefined;
        const distText = typeof dist === 'number' && dist > 0 ? ` ${dist.toFixed(1)}m` : '';
        const label = typeof trackId === 'number' ? `#${trackId} ${name} ${pct}${distText}` : `${name} ${pct}${distText}`;
        return (
          <div
            key={typeof trackId === 'number' ? `track-${trackId}` : `box-${idx}`}
            className={`absolute pointer-events-none ${borderColor} ${active ? 'border-4' : 'border-2'}`}
            style={{
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
            }}
          >
            <span className={`absolute -top-6 left-0 rounded px-1.5 py-0.5 text-xs text-white whitespace-nowrap ${active ? 'bg-yellow-500' : bgColor}`}>
              {active ? '锁定 ' : ''}{label}
            </span>
          </div>
        );
      })}
    </>
  );
}
