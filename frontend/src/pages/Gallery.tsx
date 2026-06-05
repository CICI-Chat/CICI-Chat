import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { api, ImageItem, ImageListParams, RecognitionBatch } from '../api/client';

const isBatchActive = (batch: RecognitionBatch | null) => batch?.status === 'pending' || batch?.status === 'running';
const isUnrecognizedImage = (image: ImageItem) => image.model_used === 'mock' && image.tags.includes('待分析');

type SortField = NonNullable<ImageListParams['sort']>;
type SortOrder = NonNullable<ImageListParams['order']>;

type GalleryFilters = {
  q: string;
  tag: string;
  format: string;
  sort: SortField;
  order: SortOrder;
};

const defaultFilters: GalleryFilters = {
  q: '',
  tag: '',
  format: '',
  sort: 'indexed_at',
  order: 'desc',
};

export default function Gallery({ onSelectImage }: { onSelectImage: (id: string) => void }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<GalleryFilters>(defaultFilters);
  const [draftQuery, setDraftQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [batch, setBatch] = useState<RecognitionBatch | null>(null);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const loadGallery = useCallback(() => {
    setError(null);
    api
      .listImages({
        q: filters.q || undefined,
        tag: filters.tag || undefined,
        format: filters.format || undefined,
        sort: filters.sort,
        order: filters.order,
      })
      .then((data) => {
        setImages(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message));
  }, [filters]);

  useEffect(() => {
    loadGallery();
  }, [loadGallery]);

  const tagOptions = useMemo(() => Array.from(new Set(images.flatMap((image) => image.tags))).sort(), [images]);
  const formatOptions = useMemo(() => Array.from(new Set(images.map((image) => image.format).filter(Boolean))).sort(), [images]);
  const hasActiveFilters = Boolean(
    filters.q || filters.tag || filters.format || filters.sort !== defaultFilters.sort || filters.order !== defaultFilters.order,
  );

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

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSelectedIds([]);
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
  };

  const updateFilter = <Key extends keyof GalleryFilters>(key: Key, value: GalleryFilters[Key]) => {
    setSelectedIds([]);
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const clearFilters = () => {
    setSelectedIds([]);
    setDraftQuery('');
    setFilters(defaultFilters);
  };

  const toggleSelected = (imageId: string, checked: boolean) => {
    setSelectedIds((current) => (checked ? (current.includes(imageId) ? current : [...current, imageId]) : current.filter((id) => id !== imageId)));
  };

  const selectAllImages = () => {
    setSelectedIds(images.map((image) => image.id));
  };

  const selectUnrecognizedImages = () => {
    setSelectedIds(images.filter(isUnrecognizedImage).map((image) => image.id));
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
      <div className="mb-6 rounded-xl bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">图库</h2>
            <p className="text-sm text-slate-500">共 {total} 张图片</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-slate-500">已选择 {selectedIds.length} 张</span>
            <button
              type="button"
              onClick={selectAllImages}
              disabled={images.length === 0 || batchActive}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              全选
            </button>
            <button
              type="button"
              onClick={selectUnrecognizedImages}
              disabled={!images.some(isUnrecognizedImage) || batchActive}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              全选尚未识别
            </button>
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

        <form onSubmit={submitSearch} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="search"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            placeholder="搜索文件名、标题或说明"
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
          <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800">
            搜索
          </button>
          <button
            type="button"
            onClick={clearFilters}
            disabled={!hasActiveFilters}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
          >
            清空筛选
          </button>
        </form>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-medium text-slate-600">
            标签筛选
            <select
              value={filters.tag}
              onChange={(event) => updateFilter('tag', event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="">全部标签</option>
              {tagOptions.map((tag) => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-600">
            格式筛选
            <select
              value={filters.format}
              onChange={(event) => updateFilter('format', event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="">全部格式</option>
              {formatOptions.map((format) => (
                <option key={format} value={format}>{format}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-600">
            排序字段
            <select
              value={filters.sort}
              onChange={(event) => updateFilter('sort', event.target.value as SortField)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="indexed_at">入库时间</option>
              <option value="modified_at">修改时间</option>
              <option value="file_size">文件大小</option>
              <option value="width">宽度</option>
              <option value="height">高度</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-600">
            排序方向
            <select
              value={filters.order}
              onChange={(event) => updateFilter('order', event.target.value as SortOrder)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </label>
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
        hasActiveFilters ? (
          <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">
            <p>没有匹配的图片</p>
            <button
              type="button"
              onClick={clearFilters}
              className="mt-4 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              清空筛选
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">暂无图片，请在设置的目录中添加图片后重新扫描。</div>
        )
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
