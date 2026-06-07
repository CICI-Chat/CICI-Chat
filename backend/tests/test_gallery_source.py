from pathlib import Path


GALLERY_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Gallery.tsx"
API_CLIENT_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "client.ts"
APP_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.tsx"
BATCH_HISTORY_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "BatchHistory.tsx"


def test_gallery_supports_loading_more_pages():
    source = GALLERY_SOURCE.read_text(encoding="utf-8")

    assert "const pageSize = 50" in source
    assert "loadGallery(1, false)" in source
    assert "loadGallery(nextPage, true)" in source
    assert "setImages((current) => [...current, ...data.items])" in source
    assert "const [loadingMore, setLoadingMore]" in source
    assert "requestIdRef.current" in source
    assert "加载更多" in source


def test_gallery_restores_and_controls_background_recognition_batches():
    source = GALLERY_SOURCE.read_text(encoding="utf-8")

    assert "picmind-active-recognition-batch" in source
    assert "localStorage.getItem(activeBatchStorageKey)" in source
    assert "localStorage.setItem(activeBatchStorageKey" in source
    assert "localStorage.removeItem(activeBatchStorageKey)" in source
    assert "queued" in source
    assert "running" in source
    assert "paused" in source
    assert "api.pauseRecognitionBatch" in source
    assert "api.resumeRecognitionBatch" in source
    assert "api.cancelRecognitionBatch" in source
    assert "暂停" in source
    assert "继续" in source
    assert "取消" in source
    assert "cancelled" in source
    assert "最多 200 张" not in source


def test_api_client_supports_batch_history_endpoints():
    source = API_CLIENT_SOURCE.read_text(encoding="utf-8")

    assert "export type RecognitionBatchList" in source
    assert "export type RecognitionBatchItemImage" in source
    assert "export type RecognitionBatchItem" in source
    assert "export type RecognitionBatchItemList" in source
    assert "created_at?: string" in source
    assert "updated_at?: string" in source
    assert "listRecognitionBatches" in source
    assert "listRecognitionBatchItems" in source
    assert "status=failed" not in source
    assert "searchParams.set('status', params.status)" in source


def test_batch_history_page_source_contains_required_behaviors():
    source = BATCH_HISTORY_SOURCE.read_text(encoding="utf-8")

    assert "批次历史" in source
    assert "api.listRecognitionBatches" in source
    assert "api.listRecognitionBatchItems" in source
    assert "itemStatusFilter" in source
    assert "status: itemStatusFilter === 'all' ? undefined : itemStatusFilter" in source
    assert "全部" in source
    assert "失败" in source
    assert "完成" in source
    assert "取消" in source
    assert "重新识别失败项" in source
    assert "api.createRecognitionBatch" in source
    assert "已创建新的识别批次" in source
    assert "这个批次没有${itemStatusFilters.find" in source
    assert "failedItems.items.map" in source
    assert "item.image.image_url" in source
    assert "item.image.file_path" in source
    assert "item.error" in source


def test_app_navigation_includes_batch_history_page():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "import BatchHistory from './pages/BatchHistory'" in source
    assert "batchHistory" in source
    assert "批次历史" in source
    assert "<BatchHistory />" in source
