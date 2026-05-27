import { useCallback, useEffect, useState } from 'react';
import { api, ImageItem, RecognitionBatch } from '../api/client';

const isBatchActive = (batch: RecognitionBatch | null) => batch?.status === 'pending' || batch?.status === 'running';

export default function Gallery({ onSelectImage }: { onSelectImage: (id: string) => void }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [batch, setBatch] = useState<RecognitionBatch | null>(null);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const loadGallery = useCallback(() => {
    api
      .listImages()
      .then((data) => {
        setImages(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    loadGallery();
  }, [loadGallery]);

  useEffect(() => {
    if (!batch || !isBatchActive(batch)) return;

    const timeoutId = window.setTimeout(() => {
      api
        .getRecognitionBatch(batch.batch_id)
        .then((nextBatch) => {
          setBatch(nextBatch);
          setPollAttempt(0);
          if (!isBatchActive(nextBatch)) {
            setSelectedIds([]);
            loadGallery();
          }
        })
        .catch((err: Error) => {
          setError(err.message);
          setPollAttempt((attempt) => attempt + 1);
        });
    }, 1000);

    return () => window.clearTimeout(timeoutId);
  }, [batch, loadGallery, pollAttempt]);

  const toggleSelected = (imageId: string, checked: boolean) => {
    setSelectedIds((current) => (checked ? (current.includes(imageId) ? current : [...current, imageId]) : current.filter((id) => id !== imageId)));
  };

  const startBatchRecognition = () => {
    if (selectedIds.length === 0 || isBatchActive(batch) || batchSubmitting) return;

    setError(null);
    setBatchSubmitting(true);
    api
      .createRecognitionBatch(selectedIds)
      .then((createdBatch) => {
        setBatch(createdBatch);
        setPollAttempt(0);
        if (!isBatchActive(createdBatch)) {
          setSelectedIds([]);
          loadGallery();
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBatchSubmitting(false));
  };

  const batchActive = isBatchActive(batch);

  return (
    <section>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">图库</h2>
          <p className="text-sm text-slate-500">共 {total} 张图片</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">已选择 {selectedIds.length} 张</span>
          <button
            type="button"
            onClick={startBatchRecognition}
            disabled={selectedIds.length === 0 || batchActive || batchSubmitting}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            批量识别
          </button>
        </div>
      </div>

      {error && <p className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">操作失败：{error}</p>}

      {batch && (
        <div className="mb-4 rounded-xl bg-white p-4 text-sm text-slate-600 shadow-sm">
          <p className="font-medium text-slate-900">批量识别进度</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <span>total: {batch.total}</span>
            <span>completed: {batch.completed}</span>
            <span>failed: {batch.failed}</span>
            <span>pending: {batch.pending}</span>
            <span>running: {batch.running}</span>
            <span>status: {batch.status}</span>
          </div>
        </div>
      )}

      {images.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">暂无图片，请在设置的目录中添加图片后重新扫描。</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {images.map((image) => {
            const checkboxLabel = `选择图片 ${image.caption || image.file_path}`;
            return (
              <article key={image.id} className="overflow-hidden rounded-xl bg-white text-left shadow-sm transition hover:shadow-md">
                <div className="relative">
                  <button type="button" onClick={() => onSelectImage(image.id)} className="block w-full text-left">
                    <img src={image.image_url} alt={image.caption} className="h-44 w-full object-cover" />
                  </button>
                  <label className="absolute left-3 top-3 rounded bg-white/90 px-2 py-1 text-xs font-medium text-slate-700 shadow-sm">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(image.id)}
                      onChange={(event) => toggleSelected(image.id, event.target.checked)}
                      className="mr-1 align-middle"
                      aria-label={checkboxLabel}
                    />
                    选择
                  </label>
                </div>
                <button type="button" onClick={() => onSelectImage(image.id)} className="block w-full p-3 text-left">
                  <p className="line-clamp-2 text-sm font-medium">{image.caption}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {image.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{tag}</span>
                    ))}
                  </div>
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
