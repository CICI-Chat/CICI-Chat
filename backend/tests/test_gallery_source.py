from pathlib import Path


GALLERY_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Gallery.tsx"


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
