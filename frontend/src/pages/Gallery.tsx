import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, ImageFolder, ImageItem, ImageListParams, RecognitionBatch } from '../api/client';

const activeBatchStorageKey = 'picmind-active-recognition-batch';
const activeBatchStatuses = new Set(['queued', 'running', 'paused']);
const terminalBatchStatuses = new Set(['completed', 'failed', 'cancelled']);

const isBatchActive = (batch: RecognitionBatch | null) => Boolean(batch && activeBatchStatuses.has(batch.status));
const isBatchTerminal = (batch: RecognitionBatch | null) => Boolean(batch && terminalBatchStatuses.has(batch.status));
const isUnrecognizedImage = (image: ImageItem) => image.model_used === 'mock' && image.tags.includes('待分析');

type SortField = NonNullable<ImageListParams['sort']>;
type SortOrder = NonNullable<ImageListParams['order']>;

type GalleryFilters = {
  q: string;
  tag: string;
  format: string;
  folder: string;
  sort: SortField;
  order: SortOrder;
};

type SelectionState =
  | { mode: 'ids'; ids: string[] }
  | { mode: 'query'; filters: GalleryFilters; unrecognizedOnly: boolean };

type Density = 'comfortable' | 'compact';

const defaultFilters: GalleryFilters = {
  q: '',
  tag: '',
  format: '',
  folder: '',
  sort: 'indexed_at',
  order: 'desc',
};

const pageSize = 50;

export default function Gallery({ onSelectImage }: { onSelectImage: (id: string) => void }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<GalleryFilters>(defaultFilters);
  const [draftQuery, setDraftQuery] = useState('');
  const [selection, setSelection] = useState<SelectionState>({ mode: 'ids', ids: [] });
  const [folders, setFolders] = useState<ImageFolder[]>([]);
  const [density, setDensity] = useState<Density>('comfortable');
  const [batch, setBatch] = useState<RecognitionBatch | null>(null);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const loadGallery = useCallback((nextPage = 1, append = false) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setError(null);
    setLoadingMore(append);
    api
      .listImages({
        page: nextPage,
        size: pageSize,
        q: filters.q || undefined,
        tag: filters.tag || undefined,
        format: filters.format || undefined,
        folder: filters.folder || undefined,
        sort: filters.sort,
        order: filters.order,
      })
      .then((data) => {
        if (requestId !== requestIdRef.current) return;

        if (append) {
          setImages((current) => [...current, ...data.items]);
        } else {
          setImages(data.items);
        }
        setTotal(data.total);
        setPage(data.page);
      })
      .catch((err: Error) => {
        if (requestId === requestIdRef.current) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (requestId === requestIdRef.current) {
          setLoadingMore(false);
        }
      });
  }, [filters]);

  useEffect(() => {
    loadGallery(1, false);
  }, [loadGallery]);

  useEffect(() => {
    api.getImageFolders().then(setFolders).catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    const activeBatchId = localStorage.getItem(activeBatchStorageKey);
    if (!activeBatchId) return;

    api
      .getRecognitionBatch(activeBatchId)
      .then((restoredBatch) => {
        if (isBatchTerminal(restoredBatch)) {
          localStorage.removeItem(activeBatchStorageKey);
          return;
        }
        setBatch(restoredBatch);
      })
      .catch(() => localStorage.removeItem(activeBatchStorageKey));
  }, []);

  const tagOptions = useMemo(() => Array.from(new Set(images.flatMap((image) => image.tags))).sort(), [images]);
  const formatOptions = useMemo(() => Array.from(new Set(images.map((image) => image.format).filter(Boolean))).sort(), [images]);
  const hasActiveFilters = Boolean(
    filters.q ||
      filters.tag ||
      filters.format ||
      filters.folder ||
      filters.sort !== defaultFilters.sort ||
      filters.order !== defaultFilters.order,
  );
  const selectedIds = selection.mode === 'ids' ? selection.ids : [];
  const selectedCount = selection.mode === 'ids' ? selection.ids.length : selection.unrecognizedOnly ? 1 : total;
  const selectedSummary = selection.mode === 'query'
    ? selection.unrecognizedOnly
      ? '已选择全部未识别匹配图片'
      : `已选择全部匹配图片（共 ${total} 张）`
    : `已选择 ${selectedCount} 张`;
  const selectionFilters = (nextFilters: GalleryFilters) => ({
    q: nextFilters.q || undefined,
    tag: nextFilters.tag || undefined,
    format: nextFilters.format || undefined,
    folder: nextFilters.folder || undefined,
  });
  const resetSelection = useCallback(() => setSelection({ mode: 'ids', ids: [] }), []);

  useEffect(() => {
    if (!batch) return;

    if (isBatchTerminal(batch)) {
      localStorage.removeItem(activeBatchStorageKey);
      return;
    }

    if (!isBatchActive(batch)) return;

    localStorage.setItem(activeBatchStorageKey, batch.batch_id);
    const timeoutId = window.setTimeout(() => {
      api
        .getRecognitionBatch(batch.batch_id)
        .then((nextBatch) => {
          setBatch(nextBatch);
          setPollAttempt(0);
          if (isBatchTerminal(nextBatch)) {
            localStorage.removeItem(activeBatchStorageKey);
            resetSelection();
            loadGallery(1, false);
          }
        })
        .catch((err: Error) => {
          if (err.message.includes('404')) {
            localStorage.removeItem(activeBatchStorageKey);
            setBatch(null);
            resetSelection();
            return;
          }
          setError(err.message);
          setPollAttempt((attempt) => attempt + 1);
        });
    }, 1000);

    return () => window.clearTimeout(timeoutId);
  }, [batch, loadGallery, pollAttempt, resetSelection]);

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    resetSelection();
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
  };

  const updateFilter = <Key extends keyof GalleryFilters>(key: Key, value: GalleryFilters[Key]) => {
    resetSelection();
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const clearFilters = () => {
    resetSelection();
    setDraftQuery('');
    setFilters(defaultFilters);
  };

  const toggleSelected = (imageId: string, checked: boolean) => {
    setSelection((current) => {
      const currentIds = current.mode === 'ids' ? current.ids : [];
      return {
        mode: 'ids',
        ids: checked
          ? currentIds.includes(imageId)
            ? currentIds
            : [...currentIds, imageId]
          : currentIds.filter((id) => id !== imageId),
      };
    });
  };

  const selectLoadedImages = () => {
    setSelection({ mode: 'ids', ids: images.map((image) => image.id) });
  };

  const selectAllMatchingImages = () => {
    setSelection({ mode: 'query', filters: { ...filters }, unrecognizedOnly: false });
  };

  const selectAllUnrecognizedImages = () => {
    setSelection({ mode: 'query', filters: { ...filters }, unrecognizedOnly: true });
  };

  const startBatchRecognition = () => {
    if (selectedCount === 0 || isBatchActive(batch) || batchSubmitting) return;

    setError(null);
    setBatchSubmitting(true);
    api
      .createRecognitionBatch(
        selection.mode === 'ids'
          ? selection.ids
          : { selection: { ...selectionFilters(selection.filters), unrecognized_only: selection.unrecognizedOnly } },
      )
      .then((createdBatch) => {
        setBatch(createdBatch);
        setPollAttempt(0);
        localStorage.setItem(activeBatchStorageKey, createdBatch.batch_id);
        if (isBatchTerminal(createdBatch)) {
          localStorage.removeItem(activeBatchStorageKey);
          resetSelection();
          loadGallery(1, false);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBatchSubmitting(false));
  };

  const pauseBatchRecognition = () => {
    if (!batch) return;

    api.pauseRecognitionBatch(batch.batch_id).then(setBatch).catch((err: Error) => setError(err.message));
  };

  const resumeBatchRecognition = () => {
    if (!batch) return;

    api.resumeRecognitionBatch(batch.batch_id).then(setBatch).catch((err: Error) => setError(err.message));
  };

  const cancelBatchRecognition = () => {
    if (!batch) return;

    api.cancelRecognitionBatch(batch.batch_id).then(setBatch).catch((err: Error) => setError(err.message));
  };

  const batchActive = isBatchActive(batch);
  const hasMoreImages = images.length < total;
  const galleryGridClass = density === 'compact'
    ? 'grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8'
    : 'grid gap-4 sm:grid-cols-2 lg:grid-cols-4';
  const imageClass = density === 'compact' ? 'h-24 w-full object-cover' : 'h-44 w-full object-cover';
  const cardBodyClass = density === 'compact' ? 'block w-full p-2 text-left' : 'block w-full p-3 text-left';
  const captionClass = density === 'compact' ? 'line-clamp-1 text-xs font-medium' : 'line-clamp-2 text-sm font-medium';
  const tagClass = density === 'compact'
    ? 'rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600'
    : 'rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600';

  const loadMoreImages = () => {
    if (loadingMore) return;

    const nextPage = page + 1;
    loadGallery(nextPage, true);
  };

  return (
    <section>
      <div className="mb-6 rounded-xl bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">图库</h2>
            <p className="text-sm text-slate-500">共 {total} 张图片</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-slate-500">{selectedSummary}</span>
            <button
              type="button"
              onClick={selectLoadedImages}
              disabled={images.length === 0 || batchActive}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              全选已加载
            </button>
            <button
              type="button"
              onClick={selectAllMatchingImages}
              disabled={total === 0 || batchActive}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              全选全部结果
            </button>
            <button
              type="button"
              onClick={selectAllUnrecognizedImages}
              disabled={total === 0 || batchActive}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
            >
              全选全部未识别
            </button>
            <button
              type="button"
              onClick={startBatchRecognition}
              disabled={selectedCount === 0 || batchActive || batchSubmitting}
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

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          <label className="text-sm font-medium text-slate-600">
            文件夹
            <select
              value={filters.folder}
              onChange={(event) => updateFilter('folder', event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="">全部文件夹</option>
              {folders.map((folder) => (
                <option key={folder.path} value={folder.path}>{folder.name}（{folder.image_count}）</option>
              ))}
            </select>
          </label>
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
          <label className="text-sm font-medium text-slate-600">
            显示大小
            <select
              value={density}
              onChange={(event) => setDensity(event.target.value as Density)}
              className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              <option value="comfortable">大图显示</option>
              <option value="compact">小图显示</option>
            </select>
          </label>
        </div>
      </div>

      {error && <p className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">操作失败：{error}</p>}

      {batch && (
        <div className="mb-4 rounded-xl bg-white p-4 text-sm text-slate-600 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium text-slate-900">批量识别进度</p>
              {batchActive && <p className="mt-1 text-xs text-slate-500">后台识别中，关闭或刷新页面也会继续。</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              {(batch.status === 'queued' || batch.status === 'running') && (
                <button
                  type="button"
                  onClick={pauseBatchRecognition}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  暂停
                </button>
              )}
              {batch.status === 'paused' && (
                <button
                  type="button"
                  onClick={resumeBatchRecognition}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  继续
                </button>
              )}
              {batchActive && (
                <button
                  type="button"
                  onClick={cancelBatchRecognition}
                  className="rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-red-600 transition hover:bg-red-50"
                >
                  取消
                </button>
              )}
            </div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
            <span>total: {batch.total}</span>
            <span>completed: {batch.completed}</span>
            <span>failed: {batch.failed}</span>
            <span>pending: {batch.pending}</span>
            <span>running: {batch.running}</span>
            <span>cancelled: {batch.cancelled}</span>
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
        <>
          <div className={galleryGridClass}>
            {images.map((image) => {
              const checkboxLabel = `选择图片 ${image.caption || image.file_path}`;
              const imageSelected = selection.mode === 'query' || selectedIds.includes(image.id);
              return (
                <article key={image.id} className="overflow-hidden rounded-xl bg-white text-left shadow-sm transition hover:shadow-md">
                  <div className="relative">
                    <button type="button" onClick={() => onSelectImage(image.id)} className="block w-full text-left">
                      <img src={image.image_url} alt={image.caption} className={imageClass} />
                    </button>
                    <label className="absolute left-3 top-3 rounded bg-white/90 px-2 py-1 text-xs font-medium text-slate-700 shadow-sm">
                      <input
                        type="checkbox"
                        checked={imageSelected}
                        onChange={(event) => toggleSelected(image.id, event.target.checked)}
                        disabled={selection.mode === 'query'}
                        className="mr-1 align-middle disabled:cursor-not-allowed"
                        aria-label={checkboxLabel}
                      />
                      选择
                    </label>
                  </div>
                  <button type="button" onClick={() => onSelectImage(image.id)} className={cardBodyClass}>
                    <p className={captionClass}>{image.caption}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {image.tags.map((tag) => (
                        <span key={tag} className={tagClass}>{tag}</span>
                      ))}
                    </div>
                  </button>
                </article>
              );
            })}
          </div>
          {hasMoreImages && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={loadMoreImages}
                disabled={batchActive || loadingMore}
                className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
              >
                {loadingMore ? '加载中...' : '加载更多'}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
