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
        <img src={image.image_url} alt={image.caption} className="w-full rounded-xl bg-white object-contain shadow-sm" />
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
