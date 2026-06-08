import { useCallback, useEffect, useRef, useState } from 'react';
import { api, RecognitionBatch, RecognitionBatchItemList, RecognitionBatchList } from '../api/client';

const pageSize = 20;
const failedItemPageSize = 50;
const activeBatchStatuses = ['queued', 'running', 'paused'];
const batchStatusFilters = [
  { value: 'all', label: '全部' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
] as const;
const itemStatusFilters = [
  { value: 'all', label: '全部' },
  { value: 'failed', label: '失败' },
  { value: 'completed', label: '完成' },
  { value: 'cancelled', label: '取消' },
] as const;

type BatchStatusFilter = (typeof batchStatusFilters)[number]['value'];
type ItemStatusFilter = (typeof itemStatusFilters)[number]['value'];

const statusClasses: Record<string, string> = {
  queued: 'bg-blue-100 text-blue-700',
  running: 'bg-blue-100 text-blue-700',
  paused: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
};

const emptyFailedItems: RecognitionBatchItemList = {
  items: [],
  total: 0,
  page: 1,
  size: failedItemPageSize,
};

function formatDate(value?: string) {
  if (!value) return '无';
  return new Date(value).toLocaleString();
}

function statusClass(status: string) {
  return statusClasses[status] ?? 'bg-slate-100 text-slate-700';
}

function failureCategoryLabel(category?: string | null) {
  if (category === 'file_missing') return '文件路径失效';
  if (category === 'configuration') return '服务配置问题';
  if (category === 'recognition_failed') return '模型识别失败';
  return '未知错误';
}

function failureHint(item: { failure_category?: string | null; failure_hint?: string | null }) {
  if (item.failure_hint) return item.failure_hint;
  if (item.failure_category === 'file_missing') return '可以先修复文件路径或重新索引后再重试。';
  return null;
}

export default function BatchHistory() {
  const [batches, setBatches] = useState<RecognitionBatchList>({ items: [], total: 0, page: 1, size: pageSize });
  const [page, setPage] = useState(1);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [failedItems, setFailedItems] = useState<RecognitionBatchItemList>(emptyFailedItems);
  const [batchStatusFilter, setBatchStatusFilter] = useState<BatchStatusFilter>('all');
  const [itemStatusFilter, setItemStatusFilter] = useState<ItemStatusFilter>('failed');
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [loadingFailedItems, setLoadingFailedItems] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pendingBatchId, setPendingBatchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const batchListRequestId = useRef(0);
  const selectedBatchIdRef = useRef<string | null>(null);
  const preferredBatchIdRef = useRef<string | null>(null);
  const failedItemsRequestId = useRef(0);

  useEffect(() => {
    selectedBatchIdRef.current = selectedBatchId;
  }, [selectedBatchId]);

  const loadBatches = useCallback((nextPage: number, preferredBatchId?: string) => {
    const requestId = batchListRequestId.current + 1;
    batchListRequestId.current = requestId;
    if (preferredBatchId) preferredBatchIdRef.current = preferredBatchId;
    setLoadingBatches(true);
    setError(null);
    api.listRecognitionBatches({ page: nextPage, size: pageSize, status: batchStatusFilter === 'all' ? undefined : batchStatusFilter })
      .then((data) => {
        if (requestId !== batchListRequestId.current) return;
        const currentBatchId = selectedBatchIdRef.current;
        const preferredBatchId = preferredBatchIdRef.current;
        const batchIdToSelect = preferredBatchId ?? (data.items.some((batch) => batch.batch_id === currentBatchId) ? currentBatchId : data.items[0]?.batch_id ?? null);
        setBatches(data);
        setSelectedBatchId(batchIdToSelect);
        if (batchIdToSelect !== currentBatchId) setFailedItems(emptyFailedItems);
        if (preferredBatchId) {
          preferredBatchIdRef.current = null;
          setPendingBatchId(null);
          setMessage(null);
        }
      })
      .catch((err: Error) => {
        if (requestId !== batchListRequestId.current) return;
        setError(err.message);
      })
      .finally(() => {
        if (requestId !== batchListRequestId.current) return;
        setLoadingBatches(false);
      });
  }, [batchStatusFilter]);

  useEffect(() => {
    loadBatches(page);
  }, [loadBatches, page]);

  const refreshCurrentBatchItems = useCallback((batchId: string | null, statusFilter: ItemStatusFilter) => {
    const requestId = failedItemsRequestId.current + 1;
    failedItemsRequestId.current = requestId;

    if (!batchId) {
      setFailedItems(emptyFailedItems);
      setLoadingFailedItems(false);
      return;
    }

    setFailedItems(emptyFailedItems);
    setLoadingFailedItems(true);
    setError(null);
    api.listRecognitionBatchItems(batchId, {
      page: 1,
      size: failedItemPageSize,
      status: statusFilter === 'all' ? undefined : statusFilter,
    })
      .then((data) => {
        if (requestId !== failedItemsRequestId.current) return;
        setFailedItems(data);
      })
      .catch((err: Error) => {
        if (requestId !== failedItemsRequestId.current) return;
        setError(err.message);
      })
      .finally(() => {
        if (requestId !== failedItemsRequestId.current) return;
        setLoadingFailedItems(false);
      });
  }, []);

  useEffect(() => {
    refreshCurrentBatchItems(selectedBatchId, itemStatusFilter);
  }, [refreshCurrentBatchItems, selectedBatchId, itemStatusFilter]);

  const retryFailedItems = () => {
    if (failedItems.items.length === 0 || retrying) return;

    setRetrying(true);
    setMessage(null);
    setError(null);
    api.createRecognitionBatch(failedItems.items.map((item) => item.image_id))
      .then((createdBatch) => {
        setPendingBatchId(createdBatch.batch_id);
        setMessage('已创建新的识别批次；如果图片本身仍无法识别，可能会再次失败');
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setRetrying(false));
  };

  const viewPendingBatch = () => {
    if (!pendingBatchId) return;
    setBatchStatusFilter('all');
    preferredBatchIdRef.current = pendingBatchId;
    setPage(1);
    setSelectedBatchId(pendingBatchId);
    if (batchStatusFilter === 'all') loadBatches(1, pendingBatchId);
  };

  const refreshBatchHistory = useCallback(() => {
    loadBatches(page, selectedBatchId ?? undefined);
    refreshCurrentBatchItems(selectedBatchId, itemStatusFilter);
  }, [itemStatusFilter, loadBatches, page, refreshCurrentBatchItems, selectedBatchId]);

  const selectedBatch = batches.items.find((batch) => batch.batch_id === selectedBatchId);

  useEffect(() => {
    if (!selectedBatch || !activeBatchStatuses.includes(selectedBatch.status)) return;

    const intervalId = window.setInterval(() => {
      refreshBatchHistory();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [refreshBatchHistory, selectedBatch]);

  const totalPages = Math.max(1, Math.ceil(batches.total / pageSize));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">批次历史</h2>
        <p className="mt-1 text-sm text-slate-500">查看识别批次状态，并重新识别失败图片。</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          <span>{message}</span>
          {pendingBatchId && (
            <button onClick={viewPendingBatch} className="rounded-md bg-green-700 px-3 py-1 text-white">
              查看新批次
            </button>
          )}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section className="rounded-xl border bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="font-semibold text-slate-900">识别批次</h3>
            <div className="flex items-center gap-3">
              {loadingBatches && <span className="text-sm text-slate-500">加载中...</span>}
              <button onClick={refreshBatchHistory} className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700 hover:bg-slate-200">
                刷新
              </button>
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {batchStatusFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => {
                  setBatchStatusFilter(filter.value);
                  setPage(1);
                  setMessage(null);
                }}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  batchStatusFilter === filter.value ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {batches.items.map((batch) => (
              <button
                key={batch.batch_id}
                onClick={() => {
                  setSelectedBatchId(batch.batch_id);
                  setMessage(null);
                }}
                className={`w-full rounded-lg border p-4 text-left transition ${
                  selectedBatchId === batch.batch_id ? 'border-slate-900 bg-slate-50' : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate font-medium text-slate-900">{batch.batch_id}</span>
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusClass(batch.status)}`}>{batch.status}</span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
                  <span>总数 {batch.total}</span>
                  <span>完成 {batch.completed}</span>
                  <span>失败 {batch.failed}</span>
                  <span>等待 {batch.pending}</span>
                  <span>运行 {batch.running}</span>
                  <span>取消 {batch.cancelled}</span>
                </div>
                <div className="mt-3 space-y-1 text-xs text-slate-500">
                  <p>创建：{formatDate(batch.created_at)}</p>
                  <p>更新：{formatDate(batch.updated_at)}</p>
                </div>
              </button>
            ))}
          </div>

          {batches.items.length === 0 && !loadingBatches && <p className="py-8 text-center text-sm text-slate-500">暂无识别批次</p>}

          <div className="mt-4 flex items-center justify-between text-sm">
            <button
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1}
              className="rounded-lg bg-slate-100 px-3 py-2 text-slate-700 disabled:opacity-50"
            >
              上一页
            </button>
            <span className="text-slate-500">
              第 {page} / {totalPages} 页
            </span>
            <button
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages}
              className="rounded-lg bg-slate-100 px-3 py-2 text-slate-700 disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </section>

        <section className="rounded-xl border bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-slate-900">批次图片</h3>
              <p className="text-sm text-slate-500">仅显示当前筛选前 {failedItemPageSize} 个图片项。</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {itemStatusFilters.map((filter) => (
                  <button
                    key={filter.value}
                    onClick={() => setItemStatusFilter(filter.value)}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      itemStatusFilter === filter.value ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
            {itemStatusFilter === 'failed' && failedItems.items.length > 0 && (
              <div className="text-right">
                <button
                  onClick={retryFailedItems}
                  disabled={retrying}
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
                >
                  {retrying ? '创建中...' : '重新识别失败项'}
                </button>
                <p className="mt-2 max-w-xs text-xs text-slate-500">
                  重新识别只会重新提交失败图片；如果原始失败原因未解决，图片可能仍会失败。
                </p>
              </div>
            )}
          </div>

          {loadingFailedItems && <p className="py-8 text-center text-sm text-slate-500">加载图片项中...</p>}

          {!loadingFailedItems && failedItems.items.length === 0 && (
            <p className="py-8 text-center text-sm text-slate-500">
              {itemStatusFilter === 'all' ? '这个批次没有图片项' : `这个批次没有${itemStatusFilters.find((filter) => filter.value === itemStatusFilter)?.label}图片`}
            </p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {failedItems.items.map((item) => {
              const hint = failureHint(item);
              return (
                <article key={item.id} className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                  <img src={item.image.image_url} alt={item.image.file_path} className="h-36 w-full object-cover" />
                  <div className="space-y-2 p-3">
                    <p className="break-all text-sm font-medium text-slate-900">{item.image.file_path}</p>
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusClass(item.status)}`}>{item.status}</span>
                    {item.error && (
                      <div className="space-y-1 rounded-md bg-red-50 p-2 text-xs text-red-700">
                        <p className="font-medium">{failureCategoryLabel(item.failure_category)}</p>
                        {hint && <p>{hint}</p>}
                        <p className="break-all text-red-600">{item.error}</p>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
