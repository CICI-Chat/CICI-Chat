type BoxObject = Record<string, unknown>;

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
        const name = (obj.name as string | undefined) ?? (obj.label as string | undefined) ?? '';
        const conf = obj.confidence as number | undefined;
        const pct = typeof conf === 'number' ? `${Math.round(conf * 100)}%` : '';
        return (
          <div
            key={idx}
            className="absolute border-2 border-red-500 pointer-events-none"
            style={{
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 rounded bg-red-500 px-1.5 py-0.5 text-xs text-white whitespace-nowrap">
              {name} {pct}
            </span>
          </div>
        );
      })}
    </>
  );
}
