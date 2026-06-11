import { useEffect, useState } from 'react';
import { api, ImageDetail as ImageDetailType } from '../api/client';

export default function ImageDetail({ imageId, onBack }: { imageId: string; onBack: () => void }) {
  const [image, setImage] = useState<ImageDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recognizing, setRecognizing] = useState(false);
  const [recognitionError, setRecognitionError] = useState<string | null>(null);

  useEffect(() => {
    api.getImage(imageId).then(setImage).catch((err: Error) => setError(err.message));
  }, [imageId]);

  const handleRecognize = async () => {
    setRecognizing(true);
    setRecognitionError(null);

    try {
      const updatedImage = await api.recognizeImage(imageId);
      setImage(updatedImage);
    } catch (err) {
      setRecognitionError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setRecognizing(false);
    }
  };

  if (error && !image) return <div className="p-8 text-red-600">加载失败：{error}</div>;
  if (!image) return <div className="p-8">加载中……</div>;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <button onClick={onBack} className="mb-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">返回图库</button>
      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div className="relative inline-block w-full">
          <img src={image.image_url} alt={image.caption} className="block w-full rounded-xl bg-white object-contain shadow-sm" />
          {image.objects?.map((obj, idx) => {
            const o = obj as Record<string, unknown>;
            const x = o.x as number | undefined;
            const y = o.y as number | undefined;
            const w = o.w as number | undefined;
            const h = o.h as number | undefined;
            if (typeof x !== 'number' || typeof y !== 'number'
                || typeof w !== 'number' || typeof h !== 'number') {
              return null;
            }
            const name = (o.name as string | undefined) ?? (o.label as string | undefined) ?? '';
            const conf = o.confidence as number | undefined;
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
        </div>
        <aside className="rounded-xl bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">图片详情</h2>
            <button
              onClick={handleRecognize}
              disabled={recognizing}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {recognizing ? '识别中……' : '重新识别'}
            </button>
          </div>
          {recognitionError && <p className="mt-3 text-sm text-red-600">识别失败：{recognitionError}</p>}
          <p className="mt-4 text-slate-700">{image.caption}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {image.tags.map((tag) => <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-sm">{tag}</span>)}
          </div>
          {/* 检测到的物体 */}
          {image.objects && image.objects.length > 0 ? (
            <div className="mt-4">
              <p className="text-sm font-medium text-slate-900">检测到的物体</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {image.objects.map((obj, idx) => {
                  const name = (obj as Record<string, unknown>).name as string | undefined;
                  const label = (obj as Record<string, unknown>).label as string | undefined;
                  const confidence = (obj as Record<string, unknown>).confidence as number | undefined;
                  if (!label) return null;
                  const display = name && name !== label ? `${name}（${label}）` : label;
                  const pct = typeof confidence === 'number' ? `· 置信度 ${Math.round(confidence * 100)}%` : '';
                  return (
                    <span key={idx} className="rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700">
                      {display} {pct}
                    </span>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">未检测到物体</p>
          )}
          <dl className="mt-6 space-y-2 text-sm text-slate-600">
            <div><dt className="font-medium text-slate-900">尺寸</dt><dd>{image.width} × {image.height}</dd></div>
            <div><dt className="font-medium text-slate-900">格式</dt><dd>{image.format}</dd></div>
            <div><dt className="font-medium text-slate-900">文件大小</dt><dd>{image.file_size} 字节</dd></div>
            <div><dt className="font-medium text-slate-900">路径</dt><dd className="break-all">{image.file_path}</dd></div>
            <div><dt className="font-medium text-slate-900">模型</dt><dd>{image.model_used}</dd></div>
          </dl>
        </aside>
      </div>
    </main>
  );
}
